# HydraMind - Track 03 judge guide

HydraMind is a persistent memory layer for coding agents that treats uncertainty,
revisions, and provenance as graph data. This page maps the working product to the
Hack Hydra Track 03 brief and gives judges a short, reproducible path through it.

## The 90-second path

1. Start a source-built HydraDB `graph-node`; Docker is not required.
2. Export the same local token as `HYDRAMIND_TOKEN` and run `.venv/bin/hydramind-ui`.
3. Open `http://127.0.0.1:8787/app`, select **Create demo graph**, and inspect the
   `CONTRADICTS`, `DERIVED_FROM`, and `SUPERSEDED_BY` relationships.
4. Recall the production routing policy. The newer trust-1.0 fact ranks above the
   contradicted trust-0.6 fact.
5. Explain the older fact's trust. The UI narrates the dated contradiction and each
   persisted decay event.
6. Open the entity timeline to see the old runtime fact superseded by its revision.
7. Trace evidence to exercise HydraDB's native `algo.SSpaths` traversal, then recall
   an absent fact and observe the explicit empty result.

For a terminal-only version of the same story:

```bash
HYDRAMIND_TOKEN=local-development-token-32-bytes \
  .venv/bin/python examples/demo.py
```

## Track 03 proof map

| What strong work shows | HydraMind behavior | Reproducible proof |
|---|---|---|
| Cross-session continuity | Durable state lives in HydraDB, not in an MCP session or client process. | The stdio restart test and stateless HTTP fresh-client test write through one process/client and recall through another. |
| Time and revisions are explicit | `revise` preserves both versions, closes `valid_to`, and writes a dated, reasoned `SUPERSEDED_BY` edge. | Run `timeline`, or use the dashboard's entity timeline after seeding the demo. |
| Overwrites remain auditable | New contradictions never erase the old claim. HydraMind writes `CONTRADICTS`, changes trust, and keeps immutable `TRUST_DECAY` events. | Run `explain_trust` on the older routing policy and inspect the graph. |
| Abstention is first-class | Recall conservatively requires 0.80 lexical evidence and returns `[]` instead of forcing a weak match. | The Track 03 evaluation checks both a disjoint query and an unsupported owner question that shares `production`, `routing`, and `policy`, plus a supported positive control. |
| Retrieval uses graph structure | Entity links, revision edges, contradictions, lineage, and trust events shape the evidence graph; traces call HydraDB's native `algo.SSpaths`. | Run `trace_memory` or the dashboard's native evidence trace. |
| Read/write cost survives real use | The retrieval path has no embedding or hosted-model call; writes use bounded two-hop propagation and explicit backpressure. | Run the repeatable 250-write stress gate and inspect its throughput, p50/p95 recall, uniqueness, and fresh-driver restart result. |

## Why HydraDB is essential

HydraDB is the system of record, not an interchangeable logging sink. Removing it
would remove the connected memory model, cross-process continuity, contradiction
and revision topology, provenance-aware decay, durable trust receipts, and native
evidence traversal. The integration uses the official Neo4j Python driver over
Bolt and stays inside HydraDB's supported OpenCypher surface.

The design is deliberately graph-native:

```text
(Memory)-[:ABOUT]->(Entity)
(Memory)-[:CONTRADICTS]->(Memory)
(Memory)-[:SUPERSEDED_BY]->(Memory)
(Memory)-[:DERIVED_FROM]->(Memory)
(Memory)-[:TRUST_DECAY]->(Memory)
```

This is the project's Best Use of HydraDB argument: trust is propagated across
relationships, chronology remains traversable, and an agent can retrieve both an
answer and the graph receipts behind it.

## Verification commands

With the local Bolt endpoint running:

```bash
HYDRAMIND_TOKEN=local-development-token-32-bytes .venv/bin/pytest
HYDRAMIND_TOKEN=local-development-token-32-bytes \
  .venv/bin/python -m benchmarks.track03_eval
HYDRAMIND_TOKEN=local-development-token-32-bytes \
  .venv/bin/python benchmarks/product_stress.py \
  --writes 250 --workers 8 --recall-probes 50
```

The August 15 verification baseline is 48 passing tests: 18 database-independent
and 30 against a live source-built HydraDB node. Three tests exercise real MCP
transports. The six-case Track 03 smoke evaluation passes 6/6, and regenerated
coverage for the MCP/HydraDB core is 91%. These are named verification categories,
not a claim that every test is transport end-to-end or that the project has run
LongMemEval.

## Honest boundaries

- Conflict detection and relevance are transparent lexical heuristics, not semantic
  models. The abstention gate is intentionally conservative but is not a benchmark-grade
  entailment classifier.
- Recall currently scores all eligible candidates in a scope, so very large scopes
  need their own capacity benchmark.
- Scope is a required data/query partition, not an authorization boundary.
- HydraDB's current Bolt surface is auto-commit only. HydraMind coordinates local
  writers and gives keyed `remember` operations durable repair phases, but does not
  claim distributed transactions or crash-atomic revisions.
- The repeatable stress result is a local hardware measurement, not an unlimited
  throughput claim.

Those limits are explicit so judges can distinguish the working guarantees from
future work.
