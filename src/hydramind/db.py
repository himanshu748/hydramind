"""HydraDB connection management and graph schema initialization."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from neo4j import Driver, GraphDatabase, Record
from neo4j.exceptions import ConfigurationError, Neo4jError, ServiceUnavailable

DEFAULT_HYDRADB_URI = "neo4j://127.0.0.1:7687"
DEFAULT_HYDRADB_USERNAME = "neo4j"
DEFAULT_HYDRADB_DATABASE = "default"
HYDRAMIND_SCHEMA_ID = 1 << 60


class HydraDBError(RuntimeError):
    """Raised when HydraMind cannot communicate with its HydraDB backend."""


@dataclass(frozen=True, slots=True)
class HydraDBConfig:
    """Connection settings for a HydraDB Bolt endpoint."""

    uri: str = DEFAULT_HYDRADB_URI
    username: str = DEFAULT_HYDRADB_USERNAME
    password: str | None = None
    database: str = DEFAULT_HYDRADB_DATABASE

    @classmethod
    def from_env(cls) -> HydraDBConfig:
        """Load connection settings from HYDRAMIND_* environment variables."""

        return cls(
            uri=os.getenv("HYDRAMIND_URI", DEFAULT_HYDRADB_URI),
            username=os.getenv("HYDRAMIND_USERNAME", DEFAULT_HYDRADB_USERNAME),
            password=os.getenv("HYDRAMIND_TOKEN") or os.getenv("HYDRAMIND_PASSWORD"),
            database=os.getenv("HYDRAMIND_DATABASE", DEFAULT_HYDRADB_DATABASE),
        )


class HydraDB:
    """Small wrapper around the official Neo4j driver for HydraDB."""

    _SCHEMA_MARKER_QUERY = (
        "UNWIND $rows AS row "
        "MERGE (schema {id: row.vertex}) "
        "SET schema:HydraMindSchema, schema.name = row.name, "
        "schema.version = row.version"
    )

    def __init__(
        self,
        config: HydraDBConfig | None = None,
        *,
        driver: Driver | None = None,
    ) -> None:
        self.config = config or HydraDBConfig.from_env()
        self._owns_driver = driver is None
        if driver is not None:
            self._driver = driver
            return

        auth = None
        if self.config.password is not None:
            auth = (self.config.username, self.config.password)
        try:
            self._driver = GraphDatabase.driver(self.config.uri, auth=auth)
        except (ConfigurationError, Neo4jError, ValueError) as exc:
            raise HydraDBError(
                f"Invalid HydraDB connection configuration for {self.config.uri}: {exc}"
            ) from exc

    def verify_connection(self) -> None:
        """Verify that the configured Bolt endpoint is reachable and responsive."""

        try:
            self._driver.verify_connectivity()
            self.query(
                "MATCH (schema:HydraMindSchema {id: $schema_id}) RETURN count(*) AS connected",
                {"schema_id": HYDRAMIND_SCHEMA_ID},
            )
        except (Neo4jError, ServiceUnavailable, OSError) as exc:
            auth_hint = (
                " Set HYDRAMIND_TOKEN to the graph-node auth token."
                if self.config.password is None
                else ""
            )
            raise HydraDBError(
                f"HydraDB is unreachable at {self.config.uri}: {exc}.{auth_hint}"
            ) from exc

    def setup_schema(self) -> None:
        """Initialize HydraMind's schema marker in HydraDB's schema-on-write model."""

        self.query(
            self._SCHEMA_MARKER_QUERY,
            {
                "rows": [
                    {
                        "vertex": HYDRAMIND_SCHEMA_ID,
                        "name": "hydramind",
                        "version": "1",
                    }
                ]
            },
        )

    def query(
        self,
        cypher: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[Record]:
        """Execute one Cypher statement and materialize its records."""

        try:
            with self._driver.session(database=self.config.database) as session:
                return list(session.run(cypher, dict(parameters or {})))
        except (Neo4jError, ServiceUnavailable, OSError) as exc:
            raise HydraDBError(f"HydraDB query failed at {self.config.uri}: {exc}") from exc

    def execute_write(
        self,
        cypher: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[Record]:
        """Execute one auto-commit mutation, as required by HydraDB's Bolt API."""

        return self.query(cypher, parameters)

    def close(self) -> None:
        """Close the underlying driver when this object created it."""

        if self._owns_driver:
            self._driver.close()

    def __enter__(self) -> HydraDB:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
