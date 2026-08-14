"""Live HydraDB integration tests for HydraMind's memory tools."""

from __future__ import annotations

import pytest

from hydramind.db import HydraDB
from hydramind.tools import MemoryService

pytestmark = pytest.mark.integration


def test_remember_writes_memory_entity_and_about_edge(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:hydradb"
    memory_id = service.remember("HydraDB stores durable graph memory over Bolt.", scope, [entity])

    rows = live_db.query(
        """
MATCH (memory:Memory {id: $memory_id})-[:ABOUT]->(entity:Entity)
RETURN memory.content AS content,
    memory.trust_score AS trust_score,
    memory.status AS status,
    entity.name AS entity_name
""",
        {"memory_id": int(memory_id)},
    )

    assert [dict(row) for row in rows] == [
        {
            "content": "HydraDB stores durable graph memory over Bolt.",
            "trust_score": 1.0,
            "status": "active",
            "entity_name": entity,
        }
    ]


def test_recall_is_scoped_entity_filtered_ranked_and_can_abstain(
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:testing"
    wanted_id = service.remember(
        "Use pytest integration tests for the HydraDB Bolt adapter.", scope, [entity]
    )
    service.remember("Document the command line flags.", scope, [f"{prefix}:cli"])
    service.remember("Use pytest for a different repository.", f"{prefix}:other-scope", [entity])

    recalled = service.recall("pytest testing Bolt", scope, [entity], limit=5)

    assert [memory["id"] for memory in recalled] == [wanted_id]
    assert service.recall("quantum sandwich", scope, [entity]) == []
    assert service.recall("the and to", scope, [entity]) == []


def test_conflicting_remember_decays_old_memory_and_explains_trust(
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:routing"
    old_id = service.remember("The agent must always use direct routing.", scope, [entity])
    proposed = "The agent must not use direct routing."

    conflicts = service.check_conflict(proposed, [entity], scope=scope)
    new_id = service.remember(proposed, scope, [entity])
    recalled = service.recall("agent direct routing", scope, [entity])
    explanation = service.explain_trust(old_id)

    assert conflicts[0]["id"] == old_id
    assert [memory["id"] for memory in recalled] == [new_id, old_id]
    assert recalled[1]["trust_score"] == 0.6
    assert recalled[1]["status"] == "contradicted"
    assert any("decayed from 1.00 to 0.60" in event for event in explanation)


def test_remember_conflict_detection_is_scope_isolated(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    other_scope = f"{prefix}:other-scope"
    entity = f"{prefix}:shared-policy"
    old_id = service.remember("The policy must always use direct routing.", scope, [entity])

    service.remember("The policy must not use direct routing.", other_scope, [entity])

    rows = live_db.query(
        """
MATCH (memory:Memory {id: $memory_id})
RETURN memory.trust_score AS trust_score, memory.status AS status
""",
        {"memory_id": int(old_id)},
    )
    assert dict(rows[0]) == {"trust_score": 1.0, "status": "active"}
    assert (
        service.check_conflict(
            "The policy must not use direct routing.",
            [entity],
            scope=other_scope,
        )
        == []
    )


def test_conflict_decay_propagates_two_derived_hops(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:policy"
    root = service.remember(
        "The deployment policy must always use direct routing.", scope, [entity]
    )
    child = service.remember(
        "The release checklist derives from deployment policy.",
        scope,
        [f"{prefix}:checklist"],
        derived_from=[root],
    )
    grandchild = service.remember(
        "The runbook derives from the release checklist.",
        scope,
        [f"{prefix}:runbook"],
        derived_from=[child],
    )

    service.remember("The deployment policy must not use direct routing.", scope, [entity])
    rows = live_db.query(
        """
MATCH (memory:Memory)
WHERE memory.scope = $scope
RETURN memory.id AS id, memory.trust_score AS trust_score
""",
        {"scope": scope},
    )
    trust_by_id = {str(row["id"]): float(row["trust_score"]) for row in rows}

    assert trust_by_id[root] == 0.6
    assert trust_by_id[child] == 0.85
    assert trust_by_id[grandchild] == 0.7
    assert any("Derived trust decayed" in event for event in service.explain_trust(child))
    assert any("propagated 2 hop(s)" in event for event in service.explain_trust(grandchild))

    edges = live_db.query(
        """
MATCH (grandchild:Memory {id: $grandchild})-[:DERIVED_FROM]->
    (child:Memory {id: $child})-[:DERIVED_FROM]->(root:Memory {id: $root})
RETURN count(*) AS path_count
""",
        {"grandchild": int(grandchild), "child": int(child), "root": int(root)},
    )
    assert edges[0]["path_count"] == 1


def test_revise_supersedes_old_memory_and_inherits_entities(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:deploy-window"
    old_id = service.remember("The deploy window is Tuesday.", scope, [entity])

    new_id = service.revise(
        old_id,
        "The deploy window is Wednesday.",
        scope,
        reason="The release calendar changed.",
    )

    rows = live_db.query(
        """
MATCH (older:Memory {id: $old_id})-[revision:SUPERSEDED_BY]->
    (newer:Memory {id: $new_id})-[:ABOUT]->(entity:Entity)
RETURN older.status AS old_status,
    older.trust_score AS old_trust,
    older.valid_to AS valid_to,
    newer.status AS new_status,
    newer.trust_score AS new_trust,
    newer.valid_from AS valid_from,
    entity.name AS entity_name,
    revision.revised_at AS revised_at,
    revision.reason AS reason
""",
        {"old_id": int(old_id), "new_id": int(new_id)},
    )

    assert [dict(row) for row in rows] == [
        {
            "old_status": "superseded",
            "old_trust": 1.0,
            "valid_to": rows[0]["revised_at"],
            "new_status": "active",
            "new_trust": 1.0,
            "valid_from": rows[0]["revised_at"],
            "entity_name": entity,
            "revised_at": rows[0]["revised_at"],
            "reason": "The release calendar changed.",
        }
    ]
    assert service.recall("Tuesday", scope, [entity]) == []
    assert [memory["id"] for memory in service.recall("Wednesday deploy window", scope)] == [new_id]
    assert any("The release calendar changed." in event for event in service.explain_trust(old_id))


def test_timeline_returns_revision_history_in_chronological_order(
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:runtime"
    old_id = service.remember("The runtime is Python 3.12.", scope, [entity])
    new_id = service.revise(
        old_id,
        "The runtime is Python 3.13.",
        scope,
        reason="The toolchain was upgraded.",
    )

    history = service.timeline(scope, entity)

    assert [entry["id"] for entry in history] == [old_id, new_id]
    assert history[0]["status"] == "superseded"
    assert history[0]["superseded_by"] == new_id
    assert history[0]["valid_to"] == history[1]["valid_from"]
    assert history[1]["status"] == "active"
    assert history[1]["supersedes"] == old_id
    assert history[1]["revision_reason"] == "The toolchain was upgraded."


def test_trace_memory_uses_native_paths_without_leaking_other_scopes(
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:shared-entity"
    root_id = service.remember("The shared runtime uses Bolt.", scope, [entity])
    child_id = service.remember(
        "The agent can therefore use the Neo4j driver.",
        scope,
        [entity],
        derived_from=[root_id],
    )
    other_scope_id = service.remember(
        "This fact belongs to a different project.",
        f"{prefix}:other-scope",
        [entity],
    )

    trace = service.trace_memory(root_id, scope, max_hops=2, max_paths=20)

    assert trace["engine"] == "HydraDB algo.SSpaths"
    assert trace["memory_id"] == root_id
    memory_ids = {
        node["id"] for path in trace["paths"] for node in path["nodes"] if node["kind"] == "Memory"
    }
    relationship_types = {
        relationship["type"] for path in trace["paths"] for relationship in path["relationships"]
    }
    assert {root_id, child_id} <= memory_ids
    assert other_scope_id not in memory_ids
    assert "DERIVED_FROM" in relationship_types


def test_derived_from_rejects_unknown_or_cross_scope_sources_before_write(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    other_scope_id = service.remember(
        "A memory in another scope.",
        f"{prefix}:other-scope",
        [f"{prefix}:other"],
    )

    with pytest.raises(ValueError, match="same scope"):
        service.remember(
            "This invalid derivation must never be written.",
            scope,
            [f"{prefix}:invalid"],
            derived_from=[other_scope_id],
        )

    rows = live_db.query(
        "MATCH (memory:Memory) WHERE memory.scope = $scope RETURN count(*) AS count",
        {"scope": scope},
    )
    assert rows[0]["count"] == 0


def test_explain_trust_walks_both_sides_of_supersession(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    old_id = service.remember("The original migration plan.", scope, [f"{prefix}:old"])
    new_id = service.remember("The replacement migration plan.", scope, [f"{prefix}:new"])
    live_db.execute_write(
        """
UNWIND $rows AS row
MATCH (older:Memory {id: row.old_id}), (newer:Memory {id: row.new_id})
MERGE (older)-[supersession:SUPERSEDED_BY {id: row.edge_id}]->(newer)
""",
        {
            "rows": [
                {
                    "old_id": int(old_id),
                    "new_id": int(new_id),
                    "edge_id": 7100000000000000001,
                }
            ]
        },
    )

    assert any(f"Superseded by memory {new_id}" in event for event in service.explain_trust(old_id))
    assert any(
        f"Superseded older memory {old_id}" in event for event in service.explain_trust(new_id)
    )


def test_forget_tombstones_without_breaking_provenance(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    entity = f"{prefix}:forget"
    old_id = service.remember("Always retain the audit trail.", scope, [entity])
    new_id = service.remember("Never retain the audit trail.", scope, [entity])

    assert service.forget(new_id) is True
    assert service.forget("42") is False
    assert all(memory["id"] != new_id for memory in service.recall("audit trail", scope))
    edges = live_db.query(
        """
MATCH (newer:Memory {id: $new_id})-[:CONTRADICTS]->(older:Memory {id: $old_id})
RETURN count(*) AS edge_count
""",
        {"new_id": int(new_id), "old_id": int(old_id)},
    )
    assert edges[0]["edge_count"] == 1


def test_memory_id_operations_accept_an_optional_scope_guard(
    integration_context: tuple[MemoryService, str, str],
) -> None:
    service, scope, prefix = integration_context
    memory_id = service.remember("Keep scope guards explicit.", scope, [f"{prefix}:guard"])

    with pytest.raises(ValueError, match="was not found"):
        service.explain_trust(memory_id, scope=f"{prefix}:wrong")
    assert service.forget(memory_id, scope=f"{prefix}:wrong") is False
    assert service.forget(memory_id, scope=scope) is True
