"""Live dashboard-service tests over the same HydraDB graph as MCP."""

from __future__ import annotations

import pytest

from hydramind.db import HydraDB
from hydramind.tools import MemoryService
from hydramind.web import DashboardService

pytestmark = pytest.mark.integration


def test_dashboard_state_exposes_temporal_memories_and_revision_edges(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    _, scope, prefix = integration_context
    dashboard = DashboardService(live_db)
    old_id = dashboard.memories.remember(
        "The supported Python version is 3.12.",
        scope,
        [f"{prefix}:python"],
    )
    new_id = dashboard.memories.revise(
        old_id,
        "The supported Python version is 3.13.",
        scope,
        reason="The compatibility matrix changed.",
    )

    state = dashboard.state(scope)

    memories = {memory["id"]: memory for memory in state["memories"]}
    assert memories[old_id]["valid_to"] == memories[new_id]["valid_from"]
    assert memories[old_id]["status"] == "superseded"
    assert state["revisions"] == [
        {
            "source": old_id,
            "target": new_id,
            "revised_at": memories[new_id]["valid_from"],
            "reason": "The compatibility matrix changed.",
        }
    ]


def test_seed_demo_showcases_revision_history(
    live_db: HydraDB,
    integration_context: tuple[MemoryService, str, str],
) -> None:
    _, scope, _ = integration_context

    state = DashboardService(live_db).seed_demo(scope)

    assert len(state["revisions"]) == 1
    statuses = {memory["status"] for memory in state["memories"]}
    assert "superseded" in statuses
    assert any(
        memory["content"] == "Agent tooling runs on Python 3.13." for memory in state["memories"]
    )
