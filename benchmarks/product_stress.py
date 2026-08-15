"""Repeatable live stress gate for HydraMind's write, recall, and restart paths."""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from hydramind.db import HydraDB, HydraDBConfig
from hydramind.tools import MemoryService


@dataclass(frozen=True, slots=True)
class StressResult:
    """Machine-readable evidence from one isolated stress run."""

    generated_at: str
    environment: dict[str, str]
    writes_requested: int
    writes_succeeded: int
    unique_memory_ids: int
    write_duration_seconds: float
    writes_per_second: float
    write_p50_ms: float
    write_p95_ms: float
    write_max_ms: float
    recall_probes: int
    recall_targets_verified: int
    recall_p50_ms: float
    recall_p95_ms: float
    recall_max_ms: float
    restart_recall_succeeded: bool
    duration_seconds: float


def run_stress(*, writes: int, workers: int, recall_probes: int, keep: bool) -> StressResult:
    """Exercise concurrent writes, high-cardinality recall, and a fresh-driver restart."""

    if not 1 <= writes <= 10_000:
        raise ValueError("writes must be between 1 and 10000")
    if not 1 <= workers <= 64:
        raise ValueError("workers must be between 1 and 64")
    if not 1 <= recall_probes <= 1_000:
        raise ValueError("recall_probes must be between 1 and 1000")

    prefix = f"stress-{uuid4()}"
    scope = f"{prefix}:scope"
    started = time.perf_counter()
    write_latencies: list[float] = []
    memory_ids_by_index: dict[int, str] = {}

    try:
        with HydraDB() as db:
            db.verify_connection()
            db.setup_schema()
            service = MemoryService(db, source="stress")

            def write_one(index: int) -> tuple[int, str, float]:
                operation_started = time.perf_counter()
                memory_id = service.remember(
                    f"Durable stress memory number {index} survives agent restarts.",
                    scope,
                    [f"{prefix}:entity-{index}"],
                    idempotency_key=f"write-{index}",
                )
                return index, memory_id, (time.perf_counter() - operation_started) * 1_000

            write_phase_started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(write_one, index) for index in range(writes)]
                for future in as_completed(futures):
                    index, memory_id, latency = future.result()
                    memory_ids_by_index[index] = memory_id
                    write_latencies.append(latency)
            write_duration = time.perf_counter() - write_phase_started

            recall_latencies: list[float] = []
            recall_targets_verified = 0
            for probe in range(recall_probes):
                target = probe % writes
                operation_started = time.perf_counter()
                results = service.recall(
                    f"durable stress memory number {target} restarts",
                    scope,
                    limit=10,
                )
                recall_latencies.append((time.perf_counter() - operation_started) * 1_000)
                expected_id = memory_ids_by_index[target]
                if not any(result["id"] == expected_id for result in results):
                    raise AssertionError(
                        f"recall probe {probe} did not return target memory {expected_id}"
                    )
                recall_targets_verified += 1

        restart_target = writes - 1
        expected_restart_id = memory_ids_by_index[restart_target]
        with HydraDB() as restarted_db:
            restarted_db.verify_connection()
            restart_results = MemoryService(restarted_db, source="stress-restart").recall(
                f"durable stress memory number {restart_target} survives agent restarts",
                scope,
                limit=10,
            )
        restart_recall_succeeded = any(
            result["id"] == expected_restart_id for result in restart_results
        )
        if not restart_recall_succeeded:
            raise AssertionError(
                f"fresh-driver recall did not return target memory {expected_restart_id}"
            )

        return StressResult(
            generated_at=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            environment={
                "hydramind": version("hydramind"),
                "python": platform.python_version(),
                "platform": platform.platform(),
                "hydradb_uri": HydraDBConfig.from_env().uri,
                "hydradb_commit": os.getenv("HYDRAMIND_HYDRADB_COMMIT", "unspecified"),
            },
            writes_requested=writes,
            writes_succeeded=len(memory_ids_by_index),
            unique_memory_ids=len(set(memory_ids_by_index.values())),
            write_duration_seconds=write_duration,
            writes_per_second=round(len(memory_ids_by_index) / write_duration, 3),
            write_p50_ms=_percentile(write_latencies, 50),
            write_p95_ms=_percentile(write_latencies, 95),
            write_max_ms=max(write_latencies),
            recall_probes=recall_probes,
            recall_targets_verified=recall_targets_verified,
            recall_p50_ms=_percentile(recall_latencies, 50),
            recall_p95_ms=_percentile(recall_latencies, 95),
            recall_max_ms=max(recall_latencies),
            restart_recall_succeeded=restart_recall_succeeded,
            duration_seconds=time.perf_counter() - started,
        )
    finally:
        if not keep:
            with HydraDB() as cleanup_db:
                cleanup_db.execute_write(
                    "MATCH (memory:Memory) WHERE memory.scope = $scope DETACH DELETE memory",
                    {"scope": scope},
                )
                cleanup_db.execute_write(
                    "MATCH (entity:Entity) WHERE entity.name STARTS WITH $prefix "
                    "DETACH DELETE entity",
                    {"prefix": prefix},
                )


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 3)
    quantiles = statistics.quantiles(values, n=100, method="inclusive")
    return round(quantiles[percentile - 1], 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writes", type=int, default=250)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--recall-probes", type=int, default=50)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = run_stress(
        writes=args.writes,
        workers=args.workers,
        recall_probes=args.recall_probes,
        keep=args.keep,
    )
    rendered = json.dumps(asdict(result), indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
