"""Run a transparent six-case smoke evaluation for Hack Hydra Track 03."""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from hydramind.db import HydraDB
from hydramind.tools import MemoryService


class EvaluationCase(TypedDict):
    """One observable graph-memory behavior and its result."""

    name: str
    passed: bool
    detail: str


class EvaluationReport(TypedDict):
    """Aggregate result for the Track 03 smoke evaluation."""

    label: str
    passed: int
    total: int
    duration_ms: float
    generated_at: str
    environment: dict[str, str]
    cases: list[EvaluationCase]


def run_track03_evaluation(db: HydraDB) -> EvaluationReport:
    """Exercise continuity, change, abstention, trust, lineage, and native paths."""

    started = time.perf_counter()
    prefix = f"track03-eval-{uuid4()}"
    scope = f"{prefix}:scope"
    writer = MemoryService(db, source="evaluation-writer")
    cases: list[EvaluationCase] = []
    try:
        continuity_entity = f"{prefix}:continuity"
        continuity_id = writer.remember(
            "HydraMind memory survives independent agent service instances.",
            scope,
            [continuity_entity],
        )
        reader = MemoryService(db, source="evaluation-reader")
        continuity = reader.recall("independent agent service instances", scope)
        _record(
            cases,
            "cross_service_continuity",
            bool(continuity and continuity[0]["id"] == continuity_id),
            "A fresh MemoryService recalled a fact written by another instance.",
        )

        revision_entity = f"{prefix}:deploy-window"
        old_id = writer.remember("The deploy window is Tuesday.", scope, [revision_entity])
        new_id = writer.revise(
            old_id,
            "The deploy window is Wednesday.",
            scope,
            reason="The release calendar changed.",
        )
        history = reader.timeline(scope, revision_entity)
        old_recall = reader.recall("Tuesday", scope, [revision_entity])
        new_recall = reader.recall("Wednesday", scope, [revision_entity])
        chronology_passed = (
            [entry["id"] for entry in history] == [old_id, new_id]
            and history[0]["status"] == "superseded"
            and history[0]["valid_to"] == history[1]["valid_from"]
            and old_recall == []
            and bool(new_recall and new_recall[0]["id"] == new_id)
        )
        _record(
            cases,
            "explicit_revision_chronology",
            chronology_passed,
            "The old fact stayed auditable while only the Wednesday revision was recalled.",
        )

        abstention_entity = f"{prefix}:abstention-policy"
        abstention_id = writer.remember(
            "The production routing policy requires direct traffic.",
            scope,
            [abstention_entity],
        )
        missing = reader.recall("quasar lattice checksum", scope)
        hard_negative = reader.recall(
            "Who owns the production routing policy?",
            scope,
            [abstention_entity],
        )
        supported = reader.recall(
            "How should production traffic route?",
            scope,
            [abstention_entity],
        )
        _record(
            cases,
            "missing_information_abstention",
            missing == []
            and hard_negative == []
            and bool(supported and supported[0]["id"] == abstention_id),
            "Both a disjoint query and a domain-overlap owner hard negative returned "
            "empty evidence, while a supported natural-language question recalled its fact.",
        )

        policy_entity = f"{prefix}:routing-policy"
        root_id = writer.remember(
            "Production traffic must always use direct routing.",
            scope,
            [policy_entity],
        )
        child_id = writer.remember(
            "The release checklist derives from the routing policy.",
            scope,
            [f"{prefix}:release-checklist"],
            derived_from=[root_id],
        )
        grandchild_id = writer.remember(
            "The incident runbook derives from the release checklist.",
            scope,
            [f"{prefix}:incident-runbook"],
            derived_from=[child_id],
        )
        contradicting_id = writer.remember(
            "Production traffic must not use direct routing.",
            scope,
            [policy_entity],
        )
        trust = _trust_by_id(db, scope)
        contradiction_passed = trust[root_id] == 0.6 and any(
            "Contradicted by memory" in event for event in reader.explain_trust(root_id, scope)
        )
        _record(
            cases,
            "contradiction_trust_decay",
            contradiction_passed,
            "The older claim decayed from 1.0 to 0.6 and retained its contradiction edge.",
        )

        propagation_passed = trust[child_id] == 0.85 and trust[grandchild_id] == 0.7
        _record(
            cases,
            "two_hop_provenance_decay",
            propagation_passed,
            "One-hop and two-hop dependent memories decayed to 0.85 and 0.70.",
        )

        other_scope_id = writer.remember(
            "This shared-entity fact belongs to another scope.",
            f"{prefix}:other-scope",
            [policy_entity],
        )
        trace = reader.trace_memory(root_id, scope, max_hops=2, max_paths=40)
        traced_memory_ids = {
            node["id"]
            for path in trace["paths"]
            for node in path["nodes"]
            if node["kind"] == "Memory"
        }
        traced_relationships = {
            edge["type"] for path in trace["paths"] for edge in path["relationships"]
        }
        trace_passed = (
            trace["engine"] == "HydraDB algo.SSpaths"
            and root_id in traced_memory_ids
            and contradicting_id in traced_memory_ids
            and "CONTRADICTS" in traced_relationships
            and "DERIVED_FROM" in traced_relationships
            and other_scope_id not in traced_memory_ids
        )
        _record(
            cases,
            "native_evidence_trace",
            trace_passed,
            "HydraDB hydrated bounded paths while scoped entity IDs and path filtering "
            "blocked a graph bridge.",
        )
    finally:
        db.execute_write(
            "MATCH (memory:Memory) WHERE memory.scope STARTS WITH $prefix DETACH DELETE memory",
            {"prefix": prefix},
        )
        db.execute_write(
            "MATCH (entity:Entity) WHERE entity.name STARTS WITH $prefix DETACH DELETE entity",
            {"prefix": prefix},
        )

    passed = sum(case["passed"] for case in cases)
    return {
        "label": "Hack Hydra Track 03 smoke evaluation",
        "passed": passed,
        "total": len(cases),
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "environment": {
            "hydramind": version("hydramind"),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "hydradb_uri": db.config.uri,
            "hydradb_commit": os.getenv("HYDRAMIND_HYDRADB_COMMIT", "unspecified"),
        },
        "cases": cases,
    }


def _record(cases: list[EvaluationCase], name: str, passed: bool, detail: str) -> None:
    cases.append({"name": name, "passed": passed, "detail": detail})


def _trust_by_id(db: HydraDB, scope: str) -> dict[str, float]:
    rows = db.query(
        """
MATCH (memory:Memory)
WHERE memory.scope = $scope
RETURN memory.id AS id, memory.trust_score AS trust_score
""",
        {"scope": scope},
    )
    return {str(row["id"]): float(row["trust_score"]) for row in rows}


def main() -> None:
    """Run the live evaluation and print machine-readable JSON."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with HydraDB() as db:
        db.verify_connection()
        db.setup_schema()
        report = run_track03_evaluation(db)
    rendered = json.dumps(report, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
