"""Adversarial regression tests for product boundaries and multi-process writers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from hydramind.db import HydraDB, HydraDBConfig, HydraDBError
from hydramind.tools import (
    MAX_CONTENT_LENGTH,
    MAX_ENTITY_REFS,
    MAX_QUERY_LENGTH,
    MAX_SCOPE_LENGTH,
    MemoryService,
)


class _NeverDB:
    """Fail if validation accidentally reaches the database."""

    config = HydraDBConfig()

    def query(self, *_: object, **__: object) -> list[object]:
        raise AssertionError("invalid input reached HydraDB")

    def execute_write(self, *_: object, **__: object) -> list[object]:
        raise AssertionError("invalid input reached HydraDB")


class _FailingWriteDB:
    """Delegate to HydraDB but inject one pre-commit write failure."""

    def __init__(self, delegate: HydraDB, *, fail_at: int) -> None:
        self.config = delegate.config
        self._delegate = delegate
        self._fail_at = fail_at
        self._writes = 0

    def query(self, *args: object, **kwargs: object) -> list[object]:
        return self._delegate.query(*args, **kwargs)  # type: ignore[arg-type,return-value]

    def execute_write(self, *args: object, **kwargs: object) -> list[object]:
        self._writes += 1
        if self._writes == self._fail_at:
            raise HydraDBError("injected interrupted write")
        return self._delegate.execute_write(  # type: ignore[arg-type,return-value]
            *args, **kwargs
        )


def test_public_inputs_are_bounded_before_database_work() -> None:
    service = MemoryService(_NeverDB())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="content must be at most"):
        service.remember("x" * (MAX_CONTENT_LENGTH + 1), "scope", [])
    with pytest.raises(ValueError, match="scope must be at most"):
        service.remember("fact", "s" * (MAX_SCOPE_LENGTH + 1), [])
    with pytest.raises(ValueError, match="entity_refs must contain at most"):
        service.remember(
            "fact", "scope", [f"entity-{index}" for index in range(MAX_ENTITY_REFS + 1)]
        )
    with pytest.raises(ValueError, match="query must be at most"):
        service.recall("q" * (MAX_QUERY_LENGTH + 1), "scope")
    with pytest.raises(ValueError, match="query must not be empty"):
        service.recall("   ", "scope")


def test_invalid_uri_is_reported_as_a_hydramind_error() -> None:
    with pytest.raises(HydraDBError, match="Invalid HydraDB connection configuration"):
        HydraDB(HydraDBConfig(uri="http://not-a-bolt-endpoint"))


def test_invalid_write_backpressure_configuration_is_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HYDRAMIND_MAX_INFLIGHT_WRITES", "unbounded")

    with pytest.raises(ValueError, match="HYDRAMIND_MAX_INFLIGHT_WRITES must be an integer"):
        MemoryService(_NeverDB())  # type: ignore[arg-type]


def test_coordinated_write_deduplicates_colliding_lock_stripes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MemoryService(_NeverDB())  # type: ignore[arg-type]
    monkeypatch.setattr("hydramind.tools._lock_stripe", lambda _key, _count: 0)

    with service._coordinated_write("entity:scope:key", "trust-decay"):
        pass


@pytest.mark.integration
def test_idempotency_key_prevents_duplicate_memory_and_trust_decay(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:retry"
    old_id = service.remember("The agent must always use direct routing.", scope, [entity])

    first_id = service.remember(
        "The agent must not use direct routing.",
        scope,
        [entity],
        idempotency_key="network-retry-1",
    )
    retried_id = service.remember(
        "The agent must not use direct routing.",
        scope,
        [entity],
        idempotency_key="network-retry-1",
    )

    assert retried_id == first_id
    rows = live_db.query(
        """
MATCH (memory:Memory)
WHERE memory.scope = $scope
RETURN memory.id AS id, memory.trust_score AS trust_score, memory.status AS status
ORDER BY memory.created_at
""",
        {"scope": scope},
    )
    assert len(rows) == 2
    by_id = {str(row["id"]): (float(row["trust_score"]), str(row["status"])) for row in rows}
    assert by_id[old_id] == (0.6, "contradicted")
    assert by_id[first_id] == (1.0, "active")

    with pytest.raises(ValueError, match="already used"):
        service.remember(
            "A different payload cannot reuse the same key.",
            scope,
            [entity],
            idempotency_key="network-retry-1",
        )


@pytest.mark.integration
@pytest.mark.parametrize("fail_at", [2, 5, 8, 10, 12])
def test_idempotent_retry_repairs_interrupted_graph_write(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
    fail_at: int,
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:repairable-retry-{fail_at}"
    old_id = service.remember("The agent must always use direct routing.", scope, [entity])
    child_id = service.remember(
        "The checklist derives from the routing rule.",
        scope,
        [f"{entity}:child"],
        derived_from=[old_id],
    )
    interrupted = MemoryService(
        _FailingWriteDB(live_db, fail_at=fail_at),  # type: ignore[arg-type]
        source="interrupted-test",
    )

    with pytest.raises(HydraDBError, match="injected interrupted write"):
        interrupted.remember(
            "The agent must not use direct routing.",
            scope,
            [entity],
            idempotency_key=f"repair-{fail_at}",
        )

    repaired_id = service.remember(
        "The agent must not use direct routing.",
        scope,
        [entity],
        idempotency_key=f"repair-{fail_at}",
    )
    rows = live_db.query(
        """
MATCH (newer:Memory {id: $newer_id})-[conflict:CONTRADICTS]->(older:Memory {id: $old_id})
MATCH (newer)-[:ABOUT]->(entity:Entity)
MATCH (child:Memory {id: $child_id})-[event:TRUST_DECAY]->(older)
RETURN newer.write_phase AS write_phase,
    conflict.apply_status AS conflict_status,
    event.apply_status AS event_status,
    older.trust_score AS old_trust,
    child.trust_score AS child_trust,
    count(*) AS matches
""",
        {
            "newer_id": int(repaired_id),
            "old_id": int(old_id),
            "child_id": int(child_id),
        },
    )
    assert dict(rows[0]) == {
        "write_phase": "complete",
        "conflict_status": "complete",
        "event_status": "complete",
        "old_trust": 0.6,
        "child_trust": 0.85,
        "matches": 1,
    }


@pytest.mark.integration
def test_repeated_two_hop_decays_keep_every_trust_event(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    first_entity = f"{prefix}:root-a"
    second_entity = f"{prefix}:root-b"
    first_root = service.remember("Root A must always be enabled.", scope, [first_entity])
    second_root = service.remember("Root B must always be enabled.", scope, [second_entity])
    parent = service.remember(
        "The parent decision follows both roots.",
        scope,
        [f"{prefix}:parent"],
        derived_from=[first_root, second_root],
    )
    child = service.remember(
        "The child decision follows the parent.",
        scope,
        [f"{prefix}:child"],
        derived_from=[parent],
    )

    service.remember("Root A must not be enabled.", scope, [first_entity])
    service.remember("Root B must not be enabled.", scope, [second_entity])

    event_rows = live_db.query(
        """
MATCH (memory:Memory {id: $memory_id})-[event:TRUST_DECAY]->(source:Memory)
RETURN event.before_trust AS before_trust,
    event.after_trust AS after_trust,
    source.id AS source_id
ORDER BY event.detected_at
""",
        {"memory_id": int(child)},
    )
    assert [(float(row["before_trust"]), float(row["after_trust"])) for row in event_rows] == [
        (1.0, 0.7),
        (0.7, 0.4),
    ]
    assert {str(row["source_id"]) for row in event_rows} == {parent}

    chain = service.explain_trust(child, scope)
    assert sum("Derived trust decayed" in event for event in chain) == 2


@pytest.mark.integration
def test_shared_entity_names_do_not_bridge_scopes_or_consume_trace_budget(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:shared-name"
    root_id = service.remember("The scoped root uses Bolt.", scope, [entity])
    service.remember(
        "The scoped child derives from the root.",
        scope,
        [entity],
        derived_from=[root_id],
    )
    for index in range(24):
        service.remember(
            f"Foreign scope fact {index}.",
            f"{prefix}:foreign-{index}",
            [entity],
        )

    entity_rows = live_db.query(
        "MATCH (entity:Entity) WHERE entity.name = $name RETURN count(*) AS count",
        {"name": entity},
    )
    assert int(entity_rows[0]["count"]) == 25

    trace = service.trace_memory(root_id, scope, max_hops=2, max_paths=2)
    assert trace["paths"]
    assert all(node["scope"] in {None, scope} for path in trace["paths"] for node in path["nodes"])


@pytest.mark.integration
def test_revision_conflict_checks_other_active_claims(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:revision-conflict"
    revision_target = service.remember("The policy is under review.", scope, [entity])
    stale_id = service.remember(
        "The policy must always use direct routing.",
        scope,
        [entity],
    )

    service.revise(
        revision_target,
        "The policy must not use direct routing.",
        scope,
        reason="The review completed.",
    )

    rows = live_db.query(
        "MATCH (memory:Memory {id: $memory_id}) "
        "RETURN memory.trust_score AS trust_score, memory.status AS status",
        {"memory_id": int(stale_id)},
    )
    assert dict(rows[0]) == {"trust_score": 0.6, "status": "contradicted"}


@pytest.mark.integration
def test_separate_processes_serialize_conflicting_writes(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
    tmp_path: Path,
) -> None:
    _, scope, prefix = integration_context
    entity = f"{prefix}:process-race"
    start_file = tmp_path / "start"
    processes = [
        _start_memory_process(
            start_file,
            scope,
            entity,
            "The process must always use direct routing.",
        ),
        _start_memory_process(
            start_file,
            scope,
            entity,
            "The process must not use direct routing.",
        ),
    ]
    start_file.write_text("go", encoding="utf-8")
    outputs = [process.communicate(timeout=20) for process in processes]

    assert all(process.returncode == 0 for process in processes), outputs
    rows = live_db.query(
        """
MATCH (memory:Memory)
WHERE memory.scope = $scope
RETURN memory.trust_score AS trust_score, memory.status AS status
""",
        {"scope": scope},
    )
    states = sorted((float(row["trust_score"]), str(row["status"])) for row in rows)
    assert states == [(0.6, "contradicted"), (1.0, "active")]
    edges = live_db.query(
        """
MATCH (newer:Memory)-[:CONTRADICTS]->(older:Memory)
WHERE newer.scope = $scope AND older.scope = $scope
RETURN count(*) AS count
""",
        {"scope": scope},
    )
    assert int(edges[0]["count"]) == 1


@pytest.mark.integration
def test_separate_processes_cannot_fork_one_revision(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
    tmp_path: Path,
) -> None:
    service, scope, prefix = integration_context
    old_id = service.remember(
        "The runtime is Python 3.12.",
        scope,
        [f"{prefix}:double-revision"],
    )
    start_file = tmp_path / "revise-start"
    processes = [
        _start_revision_process(start_file, scope, old_id, "The runtime is Python 3.13."),
        _start_revision_process(start_file, scope, old_id, "The runtime is Python 3.14."),
    ]
    start_file.write_text("go", encoding="utf-8")
    outputs = [process.communicate(timeout=20) for process in processes]

    assert all(process.returncode == 0 for process in processes), outputs
    lines = sorted(stdout.strip().partition(":")[0] for stdout, _ in outputs)
    assert lines == ["ERROR", "OK"]
    rows = live_db.query(
        """
MATCH (older:Memory {id: $old_id})-[:SUPERSEDED_BY]->(newer:Memory)
RETURN older.status AS old_status, count(*) AS revisions
""",
        {"old_id": int(old_id)},
    )
    assert dict(rows[0]) == {"old_status": "superseded", "revisions": 1}


def _start_memory_process(
    start_file: Path,
    scope: str,
    entity: str,
    content: str,
) -> subprocess.Popen[str]:
    code = """
import sys
import time
from pathlib import Path
from hydramind.db import HydraDB
from hydramind.tools import MemoryService

start_file, scope, entity, content = sys.argv[1:]
while not Path(start_file).exists():
    time.sleep(0.005)
with HydraDB() as db:
    db.verify_connection()
    print(MemoryService(db, source="process-stress").remember(content, scope, [entity]))
"""
    return subprocess.Popen(
        [sys.executable, "-c", code, str(start_file), scope, entity, content],
        cwd=Path.cwd(),
        env=dict(os.environ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _start_revision_process(
    start_file: Path,
    scope: str,
    memory_id: str,
    content: str,
) -> subprocess.Popen[str]:
    code = """
import sys
import time
from pathlib import Path
from hydramind.db import HydraDB
from hydramind.tools import MemoryService

start_file, scope, memory_id, content = sys.argv[1:]
while not Path(start_file).exists():
    time.sleep(0.005)
with HydraDB() as db:
    db.verify_connection()
    try:
        revised_id = MemoryService(db, source="process-stress").revise(
            memory_id,
            content,
            scope,
            reason="Concurrent revision stress.",
        )
        print(f"OK:{revised_id}")
    except ValueError as exc:
        print(f"ERROR:{exc}")
"""
    return subprocess.Popen(
        [sys.executable, "-c", code, str(start_file), scope, memory_id, content],
        cwd=Path.cwd(),
        env=dict(os.environ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
