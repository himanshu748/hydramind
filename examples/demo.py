"""Run HydraMind's graph-native trust story against a local HydraDB node."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from uuid import uuid4

from hydramind.db import HydraDB, HydraDBError
from hydramind.tools import MemoryService


def _print_step(title: str, value: Any) -> None:
    print(f"\n{title}")
    print(json.dumps(value, indent=2, sort_keys=True))


def _cleanup(db: HydraDB, scope: str, entity_prefix: str) -> None:
    db.execute_write(
        "MATCH (memory:Memory) WHERE memory.scope = $scope DETACH DELETE memory",
        {"scope": scope},
    )
    db.execute_write(
        "MATCH (entity:Entity) WHERE entity.name STARTS WITH $prefix DETACH DELETE entity",
        {"prefix": entity_prefix},
    )


def run_demo(*, keep: bool) -> None:
    """Show contradiction, revision chronology, native paths, and abstention."""

    run_id = uuid4().hex[:8]
    scope = f"hydramind-demo-{run_id}"
    entity_prefix = f"{scope}:"
    db = HydraDB()
    try:
        db.verify_connection()
        db.setup_schema()
        service = MemoryService(db, source="demo")

        root = service.remember(
            "Production deploys must always use direct routing.",
            scope,
            [f"{entity_prefix}routing-policy"],
        )
        checklist = service.remember(
            "The release checklist is based on the production routing policy.",
            scope,
            [f"{entity_prefix}release-checklist"],
            derived_from=[root],
        )
        runbook = service.remember(
            "The incident runbook is derived from the release checklist.",
            scope,
            [f"{entity_prefix}incident-runbook"],
            derived_from=[checklist],
        )
        _print_step(
            "1. Three durable memories form a two-hop DERIVED_FROM chain",
            {"root": root, "checklist": checklist, "runbook": runbook, "scope": scope},
        )

        revision = "Production deploys must not use direct routing."
        conflicts = service.check_conflict(
            revision,
            [f"{entity_prefix}routing-policy"],
            scope=scope,
        )
        _print_step("2. Pre-write conflict detection", conflicts)

        newest = service.remember(
            revision,
            scope,
            [f"{entity_prefix}routing-policy"],
        )
        trust_rows = db.query(
            """
MATCH (memory:Memory)
WHERE memory.scope = $scope
RETURN memory.id AS id,
    memory.content AS content,
    memory.trust_score AS trust_score,
    memory.status AS status
ORDER BY trust_score DESC
""",
            {"scope": scope},
        )
        _print_step(
            "3. The contradiction decays the source by 0.40 and dependents by hop",
            [dict(row) for row in trust_rows],
        )

        recalled = service.recall(
            "production deploy direct routing",
            scope,
            [f"{entity_prefix}routing-policy"],
        )
        _print_step("4. Recall ranks the new trusted claim above the stale one", recalled)
        _print_step(
            "5. Direct and propagated trust changes are explainable",
            {
                "contradicted_source": service.explain_trust(root, scope=scope),
                "two_hop_derivative": service.explain_trust(runbook, scope=scope),
            },
        )
        old_runtime = service.remember(
            "Agent tooling runs on Python 3.12.",
            scope,
            [f"{entity_prefix}agent-runtime"],
        )
        service.revise(
            old_runtime,
            "Agent tooling runs on Python 3.13.",
            scope,
            reason="The supported runtime was upgraded.",
        )
        _print_step(
            "6. Explicit revision preserves a dated fact timeline",
            service.timeline(scope, f"{entity_prefix}agent-runtime"),
        )
        trace = service.trace_memory(root, scope, max_hops=2, max_paths=20)
        _print_step(
            "7. HydraDB's native path engine hydrates the evidence neighborhood",
            {
                "engine": trace["engine"],
                "path_count": len(trace["paths"]),
                "relationship_types": sorted(
                    {edge["type"] for path in trace["paths"] for edge in path["relationships"]}
                ),
            },
        )
        _print_step(
            "8. Missing evidence produces an explicit abstention",
            service.recall("quantum sandwich compiler", scope),
        )
        print(f"\nNew active memory: {newest}")
        print(f"Demo scope: {scope}")
        if keep:
            print("Graph retained because --keep was supplied.")
        else:
            _cleanup(db, scope, entity_prefix)
            print("Demo graph cleaned up. Re-run with --keep to inspect it in HydraDB.")
    finally:
        db.close()


def main() -> int:
    """Parse demo options and report connection failures without a traceback."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="retain this run's isolated demo graph for inspection",
    )
    args = parser.parse_args()
    try:
        run_demo(keep=args.keep)
    except HydraDBError as exc:
        print(f"HydraMind demo failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
