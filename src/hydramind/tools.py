"""HydraMind's MCP tool implementations and graph-native trust logic."""

from __future__ import annotations

import hashlib
import re
import secrets
import threading
from datetime import UTC, datetime
from typing import TypedDict

from neo4j.graph import Node, Path, Relationship

from hydramind.conflict import detect_conflict_reason
from hydramind.db import HydraDB


class RecallResult(TypedDict):
    """A memory returned by recall after trust-weighted relevance ranking."""

    id: str
    content: str
    trust_score: float
    status: str
    created_at: str


class ConflictResult(TypedDict):
    """An existing memory that plausibly conflicts with proposed content."""

    id: str
    content: str
    trust_score: float
    reason: str


class TimelineResult(TypedDict):
    """One temporally ordered memory revision connected to an entity."""

    id: str
    content: str
    trust_score: float
    status: str
    created_at: str
    valid_from: str
    valid_to: str | None
    supersedes: str | None
    superseded_by: str | None
    revision_reason: str | None


class TraceNode(TypedDict):
    """A typed node included in a native HydraDB evidence path."""

    id: str
    kind: str
    label: str
    content: str | None
    scope: str | None
    status: str | None
    trust_score: float | None


class TraceRelationship(TypedDict):
    """A directed relationship included in a native HydraDB evidence path."""

    type: str
    source_id: str
    target_id: str
    properties: dict[str, object]


class TracePath(TypedDict):
    """One hydrated path returned by HydraDB's native path engine."""

    nodes: list[TraceNode]
    relationships: list[TraceRelationship]


class MemoryTrace(TypedDict):
    """Scope-safe native graph evidence surrounding a memory."""

    engine: str
    memory_id: str
    scope: str
    max_hops: int
    paths: list[TracePath]


_ID_PAYLOAD_BITS = 61
_ID_PAYLOAD_MASK = (1 << _ID_PAYLOAD_BITS) - 1
_MEMORY_ID_BASE = 1 << _ID_PAYLOAD_BITS
_ENTITY_ID_BASE = 2 << _ID_PAYLOAD_BITS
_RELATIONSHIP_ID_BASE = 3 << _ID_PAYLOAD_BITS

_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}

_UPSERT_MEMORY = """
UNWIND $rows AS row
MERGE (memory {id: row.vertex})
SET memory:Memory,
    memory.content = row.content,
    memory.source = row.source,
    memory.created_at = row.created_at,
    memory.valid_from = row.valid_from,
    memory.scope = row.scope,
    memory.trust_score = row.trust_score,
    memory.status = row.status
"""

_UPSERT_ENTITIES = """
UNWIND $rows AS row
MERGE (entity {id: row.vertex})
SET entity:Entity, entity.name = row.name, entity.kind = row.kind
"""

_MERGE_ABOUT = """
UNWIND $rows AS row
MATCH (memory:Memory {id: row.memory_id}), (entity:Entity {id: row.entity_id})
MERGE (memory)-[about:ABOUT {id: row.relationship_id}]->(entity)
"""

_MERGE_CONTRADICTIONS = """
UNWIND $rows AS row
MATCH (newer:Memory {id: row.newer_id}), (older:Memory {id: row.older_id})
MERGE (newer)-[conflict:CONTRADICTS {id: row.relationship_id}]->(older)
SET conflict.detected_at = row.detected_at,
    conflict.reason = row.reason,
    conflict.before_trust = row.before_trust,
    conflict.after_trust = row.after_trust
"""

_MERGE_DERIVATIONS = """
UNWIND $rows AS row
MATCH (derived:Memory {id: row.derived_id}), (source:Memory {id: row.source_id})
MERGE (derived)-[lineage:DERIVED_FROM {id: row.relationship_id}]->(source)
"""

_MERGE_SUPERSESSION = """
UNWIND $rows AS row
MATCH (older:Memory {id: row.older_id}), (newer:Memory {id: row.newer_id})
MERGE (older)-[revision:SUPERSEDED_BY {id: row.relationship_id}]->(newer)
SET revision.revised_at = row.revised_at, revision.reason = row.reason
"""

_UPDATE_MEMORY_TRUST = """
UNWIND $rows AS row
MERGE (memory {id: row.vertex})
SET memory:Memory, memory.trust_score = row.trust_score, memory.status = row.status
"""

_UPDATE_DERIVATION_DECAY = """
UNWIND $rows AS row
MATCH (dependent:Memory {id: row.dependent_id}), (source:Memory {id: row.source_id})
MERGE (dependent)-[lineage:DERIVED_FROM {id: row.relationship_id}]->(source)
SET lineage.last_decayed_at = row.decayed_at,
    lineage.last_decay_reason = row.reason,
    lineage.before_trust = row.before_trust,
    lineage.after_trust = row.after_trust,
    lineage.decay_hop = row.hop,
    lineage.caused_by = row.caused_by
"""


class MemoryService:
    """Coordinates durable memory operations over HydraDB's OpenCypher subset."""

    def __init__(self, db: HydraDB, *, source: str = "mcp") -> None:
        self._db = db
        self._source = source
        self._write_lock = threading.RLock()

    def remember(
        self,
        content: str,
        scope: str,
        entity_refs: list[str],
        derived_from: list[str] | None = None,
    ) -> str:
        """Persist memory, entity links, and optional provenance after conflict checks."""

        clean_content = _require_text(content, "content")
        clean_scope = _require_text(scope, "scope")
        entities = _normalize_entity_refs(entity_refs)
        source_ids = _normalize_memory_refs(derived_from or [])

        with self._write_lock:
            self._validate_sources(source_ids, clean_scope)
            conflicts = self.check_conflict(clean_content, entities, scope=clean_scope)
            memory_id = _new_memory_id()
            created_at = _utc_now()
            self._db.execute_write(
                _UPSERT_MEMORY,
                {
                    "rows": [
                        {
                            "vertex": memory_id,
                            "content": clean_content,
                            "source": self._source,
                            "created_at": created_at,
                            "valid_from": created_at,
                            "scope": clean_scope,
                            "trust_score": 1.0,
                            "status": "active",
                        }
                    ]
                },
            )
            self._write_entities_and_about(memory_id, entities)
            self._write_derivations(memory_id, source_ids)
            for conflict in conflicts:
                self._apply_conflict(
                    newer_id=memory_id,
                    older_id=_parse_memory_id(conflict["id"]),
                    reason=conflict["reason"],
                    detected_at=created_at,
                )
            return str(memory_id)

    def revise(
        self,
        memory_id: str,
        content: str,
        scope: str,
        *,
        reason: str = "Explicit revision.",
        entity_refs: list[str] | None = None,
    ) -> str:
        """Replace an active fact while preserving its temporal history in the graph."""

        parsed_id = _parse_memory_id(memory_id)
        clean_content = _require_text(content, "content")
        clean_scope = _require_text(scope, "scope")
        clean_reason = _require_text(reason, "reason")

        with self._write_lock:
            existing = self._db.query(
                """
MATCH (memory:Memory {id: $memory_id})
WHERE memory.scope = $scope
RETURN memory.status AS status
""",
                {"memory_id": parsed_id, "scope": clean_scope},
            )
            if not existing:
                raise ValueError(f"memory {memory_id} was not found in scope {clean_scope}")
            if str(existing[0]["status"]) != "active":
                raise ValueError("only active memories can be revised")

            if entity_refs is None:
                entity_rows = self._db.query(
                    """
MATCH (memory:Memory {id: $memory_id})-[:ABOUT]->(entity:Entity)
WHERE memory.scope = $scope
RETURN DISTINCT entity.name AS name
ORDER BY name
""",
                    {"memory_id": parsed_id, "scope": clean_scope},
                )
                entities = _normalize_entity_refs([str(row["name"]) for row in entity_rows])
            else:
                entities = _normalize_entity_refs(entity_refs)

            new_id = _new_memory_id()
            revised_at = _utc_now()
            self._db.execute_write(
                _UPSERT_MEMORY,
                {
                    "rows": [
                        {
                            "vertex": new_id,
                            "content": clean_content,
                            "source": self._source,
                            "created_at": revised_at,
                            "valid_from": revised_at,
                            "scope": clean_scope,
                            "trust_score": 1.0,
                            "status": "active",
                        }
                    ]
                },
            )
            self._write_entities_and_about(new_id, entities)
            self._db.execute_write(
                _MERGE_SUPERSESSION,
                {
                    "rows": [
                        {
                            "older_id": parsed_id,
                            "newer_id": new_id,
                            "relationship_id": _relationship_id("SUPERSEDED_BY", parsed_id, new_id),
                            "revised_at": revised_at,
                            "reason": clean_reason,
                        }
                    ]
                },
            )
            self._db.execute_write(
                """
MATCH (memory:Memory {id: $memory_id})
WHERE memory.scope = $scope
SET memory.status = $status, memory.valid_to = $valid_to
""",
                {
                    "memory_id": parsed_id,
                    "scope": clean_scope,
                    "status": "superseded",
                    "valid_to": revised_at,
                },
            )
            return str(new_id)

    def recall(
        self,
        query: str,
        scope: str,
        entity_refs: list[str] | None = None,
        limit: int = 10,
    ) -> list[RecallResult]:
        """Retrieve scoped memories ranked by trust times keyword relevance."""

        clean_scope = _require_text(scope, "scope")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        entities = _normalize_entity_refs(entity_refs or [])
        parameters: dict[str, object] = {
            "scope": clean_scope,
            "forgotten": "forgotten",
            "superseded": "superseded",
        }
        if not _keywords(query):
            return []

        if entities:
            entity_predicate = _entity_id_predicate(entities, parameters)
            cypher = f"""
MATCH (memory:Memory)-[:ABOUT]->(entity:Entity)
WHERE memory.scope = $scope
  AND memory.status <> $forgotten
  AND memory.status <> $superseded
  AND ({entity_predicate})
RETURN DISTINCT memory.id AS id,
    memory.content AS content,
    memory.trust_score AS trust_score,
    memory.status AS status,
    memory.created_at AS created_at
ORDER BY created_at DESC
"""
        else:
            cypher = """
MATCH (memory:Memory)
WHERE memory.scope = $scope
  AND memory.status <> $forgotten
  AND memory.status <> $superseded
RETURN memory.id AS id,
    memory.content AS content,
    memory.trust_score AS trust_score,
    memory.status AS status,
    memory.created_at AS created_at
ORDER BY created_at DESC
"""

        ranked: list[tuple[float, float, str, RecallResult]] = []
        for record in self._db.query(cypher, parameters):
            relevance = keyword_overlap_score(query, str(record["content"]))
            if relevance == 0.0:
                continue
            trust = float(record["trust_score"])
            memory: RecallResult = {
                "id": str(record["id"]),
                "content": str(record["content"]),
                "trust_score": trust,
                "status": str(record["status"]),
                "created_at": str(record["created_at"]),
            }
            ranked.append((trust * relevance, trust, memory["created_at"], memory))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return [item[3] for item in ranked[:limit]]

    def timeline(
        self,
        scope: str,
        entity_ref: str,
        limit: int = 20,
    ) -> list[TimelineResult]:
        """Return an entity's dated fact history so agents can reason about change."""

        clean_scope = _require_text(scope, "scope")
        entity = _normalize_entity_refs([entity_ref])[0]
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        rows = self._db.query(
            """
MATCH (memory:Memory)-[:ABOUT]->(entity:Entity {id: $entity_id})
WHERE memory.scope = $scope AND memory.status <> $forgotten
RETURN DISTINCT memory.id AS id,
    memory.content AS content,
    memory.trust_score AS trust_score,
    memory.status AS status,
    memory.created_at AS created_at,
    memory.valid_from AS valid_from,
    memory.valid_to AS valid_to
ORDER BY created_at
""",
            {
                "entity_id": _entity_id(entity),
                "scope": clean_scope,
                "forgotten": "forgotten",
            },
        )
        selected = rows[-limit:]
        history: dict[int, TimelineResult] = {}
        for row in selected:
            row_id = int(row["id"])
            created_at = str(row["created_at"])
            history[row_id] = {
                "id": str(row_id),
                "content": str(row["content"]),
                "trust_score": float(row["trust_score"]),
                "status": str(row["status"]),
                "created_at": created_at,
                "valid_from": str(row["valid_from"] or created_at),
                "valid_to": None if row["valid_to"] is None else str(row["valid_to"]),
                "supersedes": None,
                "superseded_by": None,
                "revision_reason": None,
            }
        if not history:
            return []

        revisions = self._db.query(
            """
MATCH (older:Memory)-[revision:SUPERSEDED_BY]->(newer:Memory)
WHERE older.scope = $scope AND newer.scope = $scope
RETURN older.id AS older_id,
    newer.id AS newer_id,
    revision.reason AS reason
""",
            {"scope": clean_scope},
        )
        for revision in revisions:
            older_id = int(revision["older_id"])
            newer_id = int(revision["newer_id"])
            reason = None if revision["reason"] is None else str(revision["reason"])
            if older_id in history:
                history[older_id]["superseded_by"] = str(newer_id)
                history[older_id]["revision_reason"] = reason
            if newer_id in history:
                history[newer_id]["supersedes"] = str(older_id)
                history[newer_id]["revision_reason"] = reason
        return list(history.values())

    def trace_memory(
        self,
        memory_id: str,
        scope: str,
        *,
        max_hops: int = 2,
        max_paths: int = 20,
    ) -> MemoryTrace:
        """Trace scope-safe evidence with HydraDB's native bounded path procedure."""

        parsed_id = _parse_memory_id(memory_id)
        clean_scope = _require_text(scope, "scope")
        if not 1 <= max_hops <= 3:
            raise ValueError("max_hops must be between 1 and 3")
        if not 1 <= max_paths <= 100:
            raise ValueError("max_paths must be between 1 and 100")
        exists = self._db.query(
            """
MATCH (memory:Memory {id: $memory_id})
WHERE memory.scope = $scope
RETURN memory.id AS id
""",
            {"memory_id": parsed_id, "scope": clean_scope},
        )
        if not exists:
            raise ValueError(f"memory {memory_id} was not found in scope {clean_scope}")

        rows = self._db.query(
            """
CALL algo.SSpaths({
  sourceNode: $source,
  relTypes: ['ABOUT', 'CONTRADICTS', 'DERIVED_FROM', 'SUPERSEDED_BY'],
  relDirection: 'both',
  maxLen: $max_hops,
  pathCount: $max_paths,
  resultLimit: $max_paths
})
YIELD path
RETURN path
""",
            {
                "source": parsed_id,
                "max_hops": max_hops,
                "max_paths": max_paths,
            },
        )
        paths: list[TracePath] = []
        for row in rows:
            path = row["path"]
            if not isinstance(path, Path) or not _path_is_in_scope(path, clean_scope):
                continue
            paths.append(_serialize_path(path))
        return {
            "engine": "HydraDB algo.SSpaths",
            "memory_id": str(parsed_id),
            "scope": clean_scope,
            "max_hops": max_hops,
            "paths": paths,
        }

    def check_conflict(
        self,
        content: str,
        entity_refs: list[str],
        scope: str | None = None,
    ) -> list[ConflictResult]:
        """Find active same-entity memories with plausibly opposite polarity."""

        clean_content = _require_text(content, "content")
        entities = _normalize_entity_refs(entity_refs)
        if not entities:
            return []
        parameters: dict[str, object] = {"active": "active"}
        entity_predicate = _entity_id_predicate(entities, parameters)
        scope_predicate = ""
        if scope is not None:
            parameters["scope"] = _require_text(scope, "scope")
            scope_predicate = "AND memory.scope = $scope"
        records = self._db.query(
            f"""
MATCH (memory:Memory)-[:ABOUT]->(entity:Entity)
WHERE memory.status = $active
  {scope_predicate}
  AND ({entity_predicate})
RETURN DISTINCT memory.id AS id,
    memory.content AS content,
    memory.trust_score AS trust_score,
    memory.created_at AS created_at
ORDER BY created_at DESC
""",
            parameters,
        )
        conflicts: list[ConflictResult] = []
        for record in records:
            reason = detect_conflict_reason(clean_content, str(record["content"]))
            if reason is not None:
                conflicts.append(
                    {
                        "id": str(record["id"]),
                        "content": str(record["content"]),
                        "trust_score": float(record["trust_score"]),
                        "reason": reason,
                    }
                )
        return conflicts

    def explain_trust(self, memory_id: str, scope: str | None = None) -> list[str]:
        """Explain trust through contradiction, supersession, and derived decay edges."""

        parsed_id = _parse_memory_id(memory_id)
        parameters: dict[str, object] = {"memory_id": parsed_id}
        scope_predicate = ""
        if scope is not None:
            parameters["scope"] = _require_text(scope, "scope")
            scope_predicate = "WHERE memory.scope = $scope"
        rows = self._db.query(
            f"""
MATCH (memory:Memory {{id: $memory_id}})
{scope_predicate}
RETURN memory.created_at AS created_at,
    memory.trust_score AS trust_score,
    memory.status AS status
""",
            parameters,
        )
        if not rows:
            raise ValueError(f"memory {memory_id} was not found")
        memory = rows[0]
        created_at = str(memory["created_at"])
        events: list[tuple[str, str]] = [(created_at, f"Created at trust 1.0 on {created_at}.")]
        events.extend(self._contradiction_events(parsed_id))
        events.extend(self._supersession_events(parsed_id))
        events.extend(self._derived_decay_events(parsed_id))
        events.sort(key=lambda event: event[0])
        chain = [description for _, description in events]
        chain.append(
            f"Current trust is {float(memory['trust_score']):.2f}; status is {memory['status']}."
        )
        return chain

    def forget(self, memory_id: str, scope: str | None = None) -> bool:
        """Tombstone a memory while preserving every provenance relationship."""

        parsed_id = _parse_memory_id(memory_id)
        parameters: dict[str, object] = {"memory_id": parsed_id}
        scope_predicate = ""
        if scope is not None:
            parameters["scope"] = _require_text(scope, "scope")
            scope_predicate = "WHERE memory.scope = $scope"
        records = self._db.query(
            f"MATCH (memory:Memory {{id: $memory_id}}) {scope_predicate} RETURN memory.id AS id",
            parameters,
        )
        if not records:
            return False
        self._db.execute_write(
            f"MATCH (memory:Memory {{id: $memory_id}}) {scope_predicate} "
            "SET memory.status = $status",
            {**parameters, "status": "forgotten"},
        )
        return True

    def _write_entities_and_about(self, memory_id: int, entities: list[str]) -> None:
        if not entities:
            return
        self._db.execute_write(
            _UPSERT_ENTITIES,
            {
                "rows": [
                    {"vertex": _entity_id(entity), "name": entity, "kind": "reference"}
                    for entity in entities
                ]
            },
        )
        self._db.execute_write(
            _MERGE_ABOUT,
            {
                "rows": [
                    {
                        "memory_id": memory_id,
                        "entity_id": _entity_id(entity),
                        "relationship_id": _relationship_id("ABOUT", memory_id, _entity_id(entity)),
                    }
                    for entity in entities
                ]
            },
        )

    def _validate_sources(self, source_ids: list[int], scope: str) -> None:
        if not source_ids:
            return
        parameters: dict[str, object] = {"scope": scope}
        predicates: list[str] = []
        for index, source_id in enumerate(source_ids):
            parameter = f"source_id_{index}"
            parameters[parameter] = source_id
            predicates.append(f"source.id = ${parameter}")
        rows = self._db.query(
            f"""
MATCH (source:Memory)
WHERE source.scope = $scope AND ({" OR ".join(predicates)})
RETURN source.id AS id
""",
            parameters,
        )
        found = {int(row["id"]) for row in rows}
        missing = [str(source_id) for source_id in source_ids if source_id not in found]
        if missing:
            raise ValueError(
                "derived_from must reference memories in the same scope; missing: "
                + ", ".join(missing)
            )

    def _write_derivations(self, memory_id: int, source_ids: list[int]) -> None:
        if not source_ids:
            return
        self._db.execute_write(
            _MERGE_DERIVATIONS,
            {
                "rows": [
                    {
                        "derived_id": memory_id,
                        "source_id": source_id,
                        "relationship_id": _relationship_id("DERIVED_FROM", memory_id, source_id),
                    }
                    for source_id in source_ids
                ]
            },
        )

    def _apply_conflict(
        self,
        *,
        newer_id: int,
        older_id: int,
        reason: str,
        detected_at: str,
    ) -> None:
        rows = self._db.query(
            """
MATCH (memory:Memory {id: $memory_id})
RETURN memory.trust_score AS trust_score, memory.status AS status
""",
            {"memory_id": older_id},
        )
        if not rows:
            return
        before_trust = float(rows[0]["trust_score"])
        after_trust = _decay(before_trust, 0.4)
        self._db.execute_write(
            _MERGE_CONTRADICTIONS,
            {
                "rows": [
                    {
                        "newer_id": newer_id,
                        "older_id": older_id,
                        "relationship_id": _relationship_id("CONTRADICTS", newer_id, older_id),
                        "detected_at": detected_at,
                        "reason": reason,
                        "before_trust": before_trust,
                        "after_trust": after_trust,
                    }
                ]
            },
        )
        self._db.execute_write(
            _UPDATE_MEMORY_TRUST,
            {
                "rows": [
                    {
                        "vertex": older_id,
                        "trust_score": after_trust,
                        "status": "contradicted",
                    }
                ]
            },
        )
        self._propagate_derived_decay(older_id)

    def _propagate_derived_decay(self, source_id: int) -> None:
        dependents: dict[int, tuple[int, float, str, int]] = {}
        first_hop = self._direct_dependents(source_id)
        for dependent_id, trust, status in first_hop:
            if dependent_id != source_id:
                dependents[dependent_id] = (1, trust, status, source_id)
        for first_hop_id, _, _ in first_hop:
            for dependent_id, trust, status in self._direct_dependents(first_hop_id):
                if dependent_id == source_id or dependent_id in dependents:
                    continue
                dependents[dependent_id] = (2, trust, status, first_hop_id)
        if not dependents:
            return
        decayed_at = _utc_now()
        decay_rows = [
            {
                "dependent_id": dependent_id,
                "source_id": parent_id,
                "relationship_id": _relationship_id("DERIVED_FROM", dependent_id, parent_id),
                "before_trust": trust,
                "after_trust": _decay(trust, 0.15 * hop),
                "hop": hop,
                "caused_by": source_id,
                "decayed_at": decayed_at,
                "reason": (f"Source memory {source_id} was contradicted; propagated {hop} hop(s)."),
                "status": status,
            }
            for dependent_id, (hop, trust, status, parent_id) in dependents.items()
        ]
        self._db.execute_write(
            _UPDATE_MEMORY_TRUST,
            {
                "rows": [
                    {
                        "vertex": row["dependent_id"],
                        "trust_score": row["after_trust"],
                        "status": row["status"],
                    }
                    for row in decay_rows
                ]
            },
        )
        self._db.execute_write(_UPDATE_DERIVATION_DECAY, {"rows": decay_rows})

    def _direct_dependents(self, source_id: int) -> list[tuple[int, float, str]]:
        records = self._db.query(
            """
MATCH (dependent:Memory)-[:DERIVED_FROM]->(source:Memory {id: $source_id})
WHERE dependent.status <> $forgotten
RETURN DISTINCT dependent.id AS id,
    dependent.trust_score AS trust_score,
    dependent.status AS status
""",
            {"source_id": source_id, "forgotten": "forgotten"},
        )
        return [
            (int(record["id"]), float(record["trust_score"]), str(record["status"]))
            for record in records
        ]

    def _contradiction_events(self, memory_id: int) -> list[tuple[str, str]]:
        events: list[tuple[str, str]] = []
        incoming = self._db.query(
            """
MATCH (newer:Memory)-[conflict:CONTRADICTS]->(memory:Memory {id: $memory_id})
RETURN newer.id AS other_id,
    conflict.detected_at AS detected_at,
    conflict.reason AS reason,
    conflict.before_trust AS before_trust,
    conflict.after_trust AS after_trust
""",
            {"memory_id": memory_id},
        )
        for record in incoming:
            detected_at = str(record["detected_at"])
            events.append(
                (
                    detected_at,
                    f"Contradicted by memory {record['other_id']} on {detected_at}: "
                    f"{record['reason']} Trust decayed from "
                    f"{float(record['before_trust']):.2f} to "
                    f"{float(record['after_trust']):.2f}.",
                )
            )
        outgoing = self._db.query(
            """
MATCH (memory:Memory {id: $memory_id})-[conflict:CONTRADICTS]->(older:Memory)
RETURN older.id AS other_id,
    conflict.detected_at AS detected_at,
    conflict.reason AS reason
""",
            {"memory_id": memory_id},
        )
        for record in outgoing:
            detected_at = str(record["detected_at"])
            events.append(
                (
                    detected_at,
                    f"Contradicted older memory {record['other_id']} on {detected_at}: "
                    f"{record['reason']} This memory's trust did not decay.",
                )
            )
        return events

    def _supersession_events(self, memory_id: int) -> list[tuple[str, str]]:
        events: list[tuple[str, str]] = []
        outgoing = self._db.query(
            """
MATCH (memory:Memory {id: $memory_id})-[revision:SUPERSEDED_BY]->(newer:Memory)
RETURN newer.id AS other_id,
    newer.created_at AS fallback_at,
    revision.revised_at AS revised_at,
    revision.reason AS reason
""",
            {"memory_id": memory_id},
        )
        for record in outgoing:
            event_at = str(record["revised_at"] or record["fallback_at"])
            reason = "" if record["reason"] is None else f" {record['reason']}"
            events.append(
                (event_at, f"Superseded by memory {record['other_id']} on {event_at}.{reason}")
            )
        incoming = self._db.query(
            """
MATCH (older:Memory)-[revision:SUPERSEDED_BY]->(memory:Memory {id: $memory_id})
RETURN older.id AS other_id,
    memory.created_at AS fallback_at,
    revision.revised_at AS revised_at,
    revision.reason AS reason
""",
            {"memory_id": memory_id},
        )
        for record in incoming:
            event_at = str(record["revised_at"] or record["fallback_at"])
            reason = "" if record["reason"] is None else f" {record['reason']}"
            events.append(
                (
                    event_at,
                    f"Superseded older memory {record['other_id']} on {event_at}.{reason}",
                )
            )
        return events

    def _derived_decay_events(self, memory_id: int) -> list[tuple[str, str]]:
        events: list[tuple[str, str]] = []
        rows = self._db.query(
            """
MATCH (memory:Memory {id: $memory_id})
    -[lineage:DERIVED_FROM]->(source:Memory)
RETURN source.id AS source_id,
    lineage.last_decayed_at AS decayed_at,
    lineage.last_decay_reason AS reason,
    lineage.before_trust AS before_trust,
    lineage.after_trust AS after_trust
""",
            {"memory_id": memory_id},
        )
        for row in rows:
            if row["decayed_at"] is None:
                continue
            decayed_at = str(row["decayed_at"])
            events.append(
                (
                    decayed_at,
                    f"Derived trust decayed on {decayed_at} through memory "
                    f"{row['source_id']}: {row['reason']} Trust decayed from "
                    f"{float(row['before_trust']):.2f} to "
                    f"{float(row['after_trust']):.2f}.",
                )
            )
        return events


def keyword_overlap_score(query: str, content: str) -> float:
    """Score content by the fraction of meaningful query keywords it contains."""

    query_terms = _keywords(query)
    if not query_terms:
        return 0.0
    content_terms = _keywords(content)
    return len(query_terms & content_terms) / len(query_terms)


def _path_is_in_scope(path: Path, scope: str) -> bool:
    return all(not ("Memory" in node.labels and node.get("scope") != scope) for node in path.nodes)


def _serialize_path(path: Path) -> TracePath:
    return {
        "nodes": [_serialize_node(node) for node in path.nodes],
        "relationships": [
            _serialize_relationship(relationship) for relationship in path.relationships
        ],
    }


def _serialize_node(node: Node) -> TraceNode:
    labels = sorted(node.labels)
    kind = "Memory" if "Memory" in node.labels else "Entity" if "Entity" in node.labels else "Node"
    content = node.get("content")
    scope = node.get("scope")
    status = node.get("status")
    trust_score = node.get("trust_score")
    label_value = content if kind == "Memory" else node.get("name")
    return {
        "id": _node_id(node),
        "kind": kind,
        "label": str(label_value or (labels[0] if labels else "Node")),
        "content": None if content is None else str(content),
        "scope": None if scope is None else str(scope),
        "status": None if status is None else str(status),
        "trust_score": None if trust_score is None else float(trust_score),
    }


def _serialize_relationship(relationship: Relationship) -> TraceRelationship:
    source = relationship.start_node
    target = relationship.end_node
    if source is None or target is None:
        raise ValueError("HydraDB returned an unhydrated path relationship")
    return {
        "type": relationship.type,
        "source_id": _node_id(source),
        "target_id": _node_id(target),
        "properties": {str(key): _json_scalar(value) for key, value in relationship.items()},
    }


def _node_id(node: Node) -> str:
    property_id = node.get("id")
    return str(node.element_id if property_id is None else property_id)


def _json_scalar(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _keywords(value: str) -> set[str]:
    return {
        _stem(token)
        for token in _TOKEN_PATTERN.findall(value.casefold())
        if token not in _STOPWORDS
    }


def _stem(token: str) -> str:
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _normalize_entity_refs(entity_refs: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for reference in entity_refs:
        entity = " ".join(_require_text(reference, "entity reference").split()).casefold()
        if entity not in seen:
            seen.add(entity)
            normalized.append(entity)
    return normalized


def _normalize_memory_refs(memory_refs: list[str]) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()
    for reference in memory_refs:
        memory_id = _parse_memory_id(reference)
        if memory_id not in seen:
            seen.add(memory_id)
            normalized.append(memory_id)
    return normalized


def _entity_id_predicate(entities: list[str], parameters: dict[str, object]) -> str:
    predicates: list[str] = []
    for index, entity in enumerate(entities):
        parameter = f"entity_id_{index}"
        parameters[parameter] = _entity_id(entity)
        predicates.append(f"entity.id = ${parameter}")
    return " OR ".join(predicates)


def _new_memory_id() -> int:
    payload = secrets.randbits(_ID_PAYLOAD_BITS) or 1
    return _MEMORY_ID_BASE | payload


def _entity_id(entity: str) -> int:
    return _stable_id(_ENTITY_ID_BASE, f"entity:{entity}")


def _relationship_id(kind: str, source_id: int, target_id: int) -> int:
    return _stable_id(_RELATIONSHIP_ID_BASE, f"{kind}:{source_id}:{target_id}")


def _stable_id(base: int, value: str) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    payload = int.from_bytes(digest, "big") & _ID_PAYLOAD_MASK
    return base | (payload or 1)


def _parse_memory_id(memory_id: str) -> int:
    try:
        parsed = int(memory_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("memory_id must be a non-negative integer string") from exc
    if parsed < 0 or parsed >= 1 << 63:
        raise ValueError("memory_id must be a non-negative 63-bit integer string")
    return parsed


def _require_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value.strip()


def _decay(score: float, amount: float) -> float:
    return round(max(0.05, score - amount), 6)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
