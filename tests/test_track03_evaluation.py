"""Reproducibility check for the small Track 03 evaluation harness."""

from __future__ import annotations

import pytest

from benchmarks.track03_eval import run_track03_evaluation
from hydramind.db import HydraDB

pytestmark = pytest.mark.integration


def test_track03_evaluation_passes_every_graph_memory_case(live_db: HydraDB) -> None:
    report = run_track03_evaluation(live_db)

    assert report["passed"] == report["total"] == 6
    assert {case["name"] for case in report["cases"]} == {
        "cross_service_continuity",
        "explicit_revision_chronology",
        "missing_information_abstention",
        "contradiction_trust_decay",
        "two_hop_provenance_decay",
        "native_evidence_trace",
    }
    assert all(case["passed"] for case in report["cases"])
