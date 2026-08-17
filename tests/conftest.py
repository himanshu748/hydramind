"""Shared pytest fixtures for HydraMind tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest

from hydramind.db import HydraDB, HydraDBError
from hydramind.tools import MemoryService


@pytest.fixture()
def live_db() -> Iterator[HydraDB]:
    """Connect to a live local HydraDB or skip integration tests clearly."""

    if not os.getenv("HYDRAMIND_TOKEN") and not os.getenv("HYDRAMIND_PASSWORD"):
        pytest.skip("set HYDRAMIND_TOKEN to run live HydraDB integration tests")
    db = HydraDB()
    try:
        db.verify_connection()
        db.setup_schema()
    except HydraDBError as exc:
        db.close()
        pytest.skip(f"local HydraDB is unavailable: {exc}")
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def integration_context(live_db: HydraDB) -> Iterator[tuple[MemoryService, str, str]]:
    """Provide an isolated scope/entity prefix and clean its graph after a test."""

    prefix = f"pytest-{uuid4()}"
    scope = f"{prefix}:scope"
    service = MemoryService(live_db, source="pytest")
    try:
        yield service, scope, prefix
    finally:
        other_scope = f"{prefix}:other-scope"
        live_db.execute_write(
            "MATCH (memory:Memory) "
            "WHERE memory.scope = $scope OR memory.scope = $other_scope "
            "DETACH DELETE memory",
            {"scope": scope, "other_scope": other_scope},
        )
        live_db.execute_write(
            "MATCH (entity:Entity) "
            "WHERE entity.scope = $scope OR entity.scope = $other_scope "
            "DETACH DELETE entity",
            {"scope": scope, "other_scope": other_scope},
        )
