"""Connection-layer tests, including clear unreachable-HydraDB failures."""

from __future__ import annotations

from typing import Any

import pytest
from neo4j.exceptions import ServiceUnavailable

from hydramind.db import HydraDB, HydraDBConfig, HydraDBError


class UnreachableDriver:
    """Minimal driver double that fails its connectivity check."""

    def verify_connectivity(self) -> None:
        raise ServiceUnavailable("connection refused")


class FakeResult:
    """Iterable result used to prove the wrapper selects auto-commit RUN."""

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter([{"connected": 1}])


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def run(self, cypher: str, parameters: dict[str, Any]) -> FakeResult:
        self.calls.append((cypher, parameters))
        return FakeResult()


class AutoCommitDriver:
    def __init__(self) -> None:
        self.fake_session = FakeSession()

    def session(self, *, database: str) -> FakeSession:
        assert database == "default"
        return self.fake_session


def test_unreachable_database_has_a_clear_uri_and_auth_hint() -> None:
    config = HydraDBConfig(uri="neo4j://127.0.0.1:19999")
    db = HydraDB(config, driver=UnreachableDriver())  # type: ignore[arg-type]

    with pytest.raises(HydraDBError) as error:
        db.verify_connection()

    message = str(error.value)
    assert "HydraDB is unreachable at neo4j://127.0.0.1:19999" in message
    assert "HYDRAMIND_TOKEN" in message


def test_query_uses_hydradb_compatible_autocommit_run() -> None:
    driver = AutoCommitDriver()
    db = HydraDB(driver=driver)  # type: ignore[arg-type]

    rows = db.query("MATCH (n) RETURN count(*) AS connected", {"value": 1})

    assert rows == [{"connected": 1}]
    assert driver.fake_session.calls == [("MATCH (n) RETURN count(*) AS connected", {"value": 1})]
