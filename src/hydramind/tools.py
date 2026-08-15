"""HydraMind's MCP tool implementations and graph-native trust logic."""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
import secrets
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path as FilePath
from tempfile import gettempdir
from typing import BinaryIO, TypedDict, cast

from neo4j import Record
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

MAX_CONTENT_LENGTH = 32_768
MAX_QUERY_LENGTH = 4_096
MAX_SCOPE_LENGTH = 256
MAX_REASON_LENGTH = 2_048
MAX_ENTITY_REF_LENGTH = 256
MAX_IDEMPOTENCY_KEY_LENGTH = 256
MAX_ENTITY_REFS = 64
MAX_MEMORY_REFS = 64
MIN_RECALL_RELEVANCE = 0.8

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
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "whom",
    "whose",
    "with",
    "why",
}

_TERM_ALIASES = {
    "routed": "route",
    "routes": "route",
    "routing": "route",
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
    memory.request_fingerprint = row.request_fingerprint,
    memory.write_phase = row.write_phase,
    memory.trust_score = row.trust_score,
    memory.status = row.status
"""

_UPSERT_ENTITIES = """
UNWIND $rows AS row
MERGE (entity {id: row.vertex})
SET entity:Entity, entity.name = row.name, entity.kind = row.kind, entity.scope = row.scope
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
    conflict.after_trust = row.after_trust,
    conflict.apply_status = row.apply_status
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

_MERGE_DERIVED_DECAY_EVENTS = """
UNWIND $rows AS row
MATCH (dependent:Memory {id: row.dependent_id}), (source:Memory {id: row.source_id})
MERGE (dependent)-[event:TRUST_DECAY {id: row.event_id}]->(source)
SET event.detected_at = row.decayed_at,
    event.reason = row.reason,
    event.before_trust = row.before_trust,
    event.after_trust = row.after_trust,
    event.hop = row.hop,
    event.caused_by = row.caused_by,
    event.apply_status = row.apply_status
"""


class MemoryService:
    """Coordinates durable memory operations over HydraDB's OpenCypher subset."""

    def __init__(self, db: HydraDB, *, source: str = "mcp") -> None:
        self._db = db
        self._source = source
        self._write_locks = tuple(threading.RLock() for _ in range(64))
        self._write_slots = threading.BoundedSemaphore(
            _bounded_env_int("HYDRAMIND_MAX_INFLIGHT_WRITES", default=8, minimum=1, maximum=64)
        )
        self._write_slot_state = threading.local()
        lock_identity = f"{db.config.uri}\0{db.config.database}"
        lock_digest = hashlib.blake2b(lock_identity.encode("utf-8"), digest_size=10).hexdigest()
        self._write_lock_prefix = f"hydramind-write-{lock_digest}"

    def remember(
        self,
        content: str,
        scope: str,
        entity_refs: list[str],
        derived_from: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        """Persist graph memory, repairing an interrupted idempotent write on retry."""

        clean_content = _require_text(content, "content", maximum=MAX_CONTENT_LENGTH)
        clean_scope = _require_text(scope, "scope", maximum=MAX_SCOPE_LENGTH)
        entities = _normalize_entity_refs(entity_refs)
        source_ids = _normalize_memory_refs(derived_from or [])
        clean_key = (
            None
            if idempotency_key is None
            else _require_text(
                idempotency_key,
                "idempotency_key",
                maximum=MAX_IDEMPOTENCY_KEY_LENGTH,
            )
        )
        request_fingerprint = _request_fingerprint(
            clean_content,
            clean_scope,
            entities,
            source_ids,
        )

        coordination_keys = _entity_coordination_keys(clean_scope, entities)
        coordination_keys.append("trust-decay")
        if clean_key is not None:
            coordination_keys.append(f"idempotency:{clean_scope}:{clean_key}")
        with self._coordinated_write(*coordination_keys):
            existing: list[Record] = []
            memory_id = (
                _new_memory_id()
                if clean_key is None
                else _idempotent_memory_id(clean_scope, clean_key)
            )
            if clean_key is not None:
                existing = self._db.query(
                    """
MATCH (memory:Memory {id: $memory_id})
RETURN memory.scope AS scope,
    memory.request_fingerprint AS request_fingerprint,
    memory.created_at AS created_at,
    memory.write_phase AS write_phase
""",
                    {"memory_id": memory_id},
                )
                if existing:
                    if (
                        str(existing[0]["scope"]) != clean_scope
                        or str(existing[0]["request_fingerprint"] or "") != request_fingerprint
                    ):
                        raise ValueError("idempotency_key was already used for a different memory")
                    phase = existing[0]["write_phase"]
                    if phase is None or str(phase) == "complete":
                        return str(memory_id)
            self._validate_sources(source_ids, clean_scope)
            conflicts = self.check_conflict(clean_content, entities, clean_scope)
            if clean_key is not None and existing:
                created_at = str(existing[0]["created_at"])
            else:
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
                                "request_fingerprint": request_fingerprint,
                                "write_phase": ("created" if clean_key is not None else "complete"),
                                "trust_score": 1.0,
                                "status": "active",
                            }
                        ]
                    },
                )
            self._write_entities_and_about(memory_id, entities, clean_scope)
            self._write_derivations(memory_id, source_ids)
            self._resume_conflicts(
                newer_id=memory_id,
                detected_at=created_at,
                conflicts=conflicts,
            )
            if clean_key is not None:
                self._set_memory_write_phase(memory_id, "complete")
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
        clean_content = _require_text(content, "content", maximum=MAX_CONTENT_LENGTH)
        clean_scope = _require_text(scope, "scope", maximum=MAX_SCOPE_LENGTH)
        clean_reason = _require_text(reason, "reason", maximum=MAX_REASON_LENGTH)

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

        coordination_keys = [
            f"memory:{parsed_id}",
            "trust-decay",
            *_entity_coordination_keys(clean_scope, entities),
        ]
        with self._coordinated_write(*coordination_keys):
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

            conflicts = [
                conflict
                for conflict in self.check_conflict(clean_content, entities, clean_scope)
                if _parse_memory_id(conflict["id"]) != parsed_id
            ]
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
                            "request_fingerprint": "",
                            "write_phase": "complete",
                            "trust_score": 1.0,
                            "status": "active",
                        }
                    ]
                },
            )
            self._write_entities_and_about(new_id, entities, clean_scope)
            self._resume_conflicts(
                newer_id=new_id,
                detected_at=revised_at,
                conflicts=conflicts,
            )
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

        clean_query = _require_text(query, "query", maximum=MAX_QUERY_LENGTH)
        clean_scope = _require_text(scope, "scope", maximum=MAX_SCOPE_LENGTH)
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        entities = _normalize_entity_refs(entity_refs or [])
        parameters: dict[str, object] = {
            "scope": clean_scope,
            "forgotten": "forgotten",
            "superseded": "superseded",
        }
        if not _keywords(clean_query):
            return []

        if entities:
            entity_predicate = _entity_id_predicate(clean_scope, entities, parameters)
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
            relevance = keyword_overlap_score(clean_query, str(record["content"]))
            if relevance < MIN_RECALL_RELEVANCE:
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

        clean_scope = _require_text(scope, "scope", maximum=MAX_SCOPE_LENGTH)
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
ORDER BY created_at, id
""",
            {
                "entity_id": _entity_id(clean_scope, entity),
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
        clean_scope = _require_text(scope, "scope", maximum=MAX_SCOPE_LENGTH)
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

        fetch_limit = min(1_000, max_paths * 10)
        rows = self._db.query(
            """
CALL algo.SSpaths({
  sourceNode: $source,
  relTypes: ['ABOUT', 'CONTRADICTS', 'DERIVED_FROM', 'SUPERSEDED_BY'],
  relDirection: 'both',
  maxLen: $max_hops,
  pathCount: $fetch_limit,
  resultLimit: $fetch_limit
})
YIELD path
RETURN path
""",
            {
                "source": parsed_id,
                "max_hops": max_hops,
                "fetch_limit": fetch_limit,
            },
        )
        paths: list[TracePath] = []
        for row in rows:
            path = row["path"]
            if not isinstance(path, Path) or not _path_is_in_scope(path, clean_scope):
                continue
            paths.append(_serialize_path(path))
            if len(paths) == max_paths:
                break
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
        scope: str,
    ) -> list[ConflictResult]:
        """Find plausible conflicts only inside the caller's explicit memory scope."""

        clean_content = _require_text(content, "content", maximum=MAX_CONTENT_LENGTH)
        clean_scope = _require_text(scope, "scope", maximum=MAX_SCOPE_LENGTH)
        entities = _normalize_entity_refs(entity_refs)
        if not entities:
            return []
        parameters: dict[str, object] = {"active": "active", "scope": clean_scope}
        entity_predicate = _entity_id_predicate(clean_scope, entities, parameters)
        records = self._db.query(
            f"""
MATCH (memory:Memory)-[:ABOUT]->(entity:Entity)
WHERE memory.status = $active
  AND memory.scope = $scope
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

    def explain_trust(self, memory_id: str, scope: str) -> list[str]:
        """Explain trust events without permitting an unscoped direct-ID lookup."""

        parsed_id = _parse_memory_id(memory_id)
        clean_scope = _require_text(scope, "scope", maximum=MAX_SCOPE_LENGTH)
        parameters: dict[str, object] = {"memory_id": parsed_id, "scope": clean_scope}
        rows = self._db.query(
            """
MATCH (memory:Memory {id: $memory_id})
WHERE memory.scope = $scope
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

    def forget(self, memory_id: str, scope: str) -> bool:
        """Tombstone one scoped memory while preserving every provenance relationship."""

        parsed_id = _parse_memory_id(memory_id)
        clean_scope = _require_text(scope, "scope", maximum=MAX_SCOPE_LENGTH)
        parameters: dict[str, object] = {"memory_id": parsed_id, "scope": clean_scope}
        with self._coordinated_write(f"memory:{parsed_id}", "trust-decay"):
            records = self._db.query(
                "MATCH (memory:Memory {id: $memory_id}) WHERE memory.scope = $scope "
                "RETURN memory.id AS id",
                parameters,
            )
            if not records:
                return False
            self._db.execute_write(
                "MATCH (memory:Memory {id: $memory_id}) WHERE memory.scope = $scope "
                "SET memory.status = $status",
                {**parameters, "status": "forgotten"},
            )
            return True

    @contextmanager
    def _coordinated_write(self, *keys: str) -> Iterator[None]:
        """Serialize only graph keys that can race across local MCP writer processes."""

        with self._write_slot():
            normalized = sorted(set(keys))
            stripe_indexes = sorted(
                {_lock_stripe(key, len(self._write_locks)) for key in normalized}
            )
            local_locks = [self._write_locks[index] for index in stripe_indexes]
            lock_files: list[BinaryIO] = []
            for lock in local_locks:
                lock.acquire()
            try:
                for stripe_index in stripe_indexes:
                    lock_path = FilePath(gettempdir()) / (
                        f"{self._write_lock_prefix}-stripe-{stripe_index:02d}.lock"
                    )
                    lock_file = lock_path.open("a+b")
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                    lock_files.append(lock_file)
                yield
            finally:
                for cleanup_file in reversed(lock_files):
                    fcntl.flock(cleanup_file.fileno(), fcntl.LOCK_UN)
                    cleanup_file.close()
                for lock in reversed(local_locks):
                    lock.release()

    @contextmanager
    def _write_slot(self) -> Iterator[None]:
        """Apply per-process backpressure while allowing nested trust-decay coordination."""

        depth = int(getattr(self._write_slot_state, "depth", 0))
        if depth == 0:
            self._write_slots.acquire()
        self._write_slot_state.depth = depth + 1
        try:
            yield
        finally:
            self._write_slot_state.depth = depth
            if depth == 0:
                self._write_slots.release()

    def _write_entities_and_about(
        self,
        memory_id: int,
        entities: list[str],
        scope: str,
    ) -> None:
        if not entities:
            return
        self._db.execute_write(
            _UPSERT_ENTITIES,
            {
                "rows": [
                    {
                        "vertex": _entity_id(scope, entity),
                        "name": entity,
                        "kind": "reference",
                        "scope": scope,
                    }
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
                        "entity_id": _entity_id(scope, entity),
                        "relationship_id": _relationship_id(
                            "ABOUT", memory_id, _entity_id(scope, entity)
                        ),
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

    def _set_memory_write_phase(self, memory_id: int, phase: str) -> None:
        self._db.execute_write(
            "MATCH (memory:Memory {id: $memory_id}) SET memory.write_phase = $phase",
            {"memory_id": memory_id, "phase": phase},
        )

    def _resume_conflicts(
        self,
        *,
        newer_id: int,
        detected_at: str,
        conflicts: list[ConflictResult],
    ) -> None:
        pending: dict[int, tuple[str, str]] = {}
        existing = self._db.query(
            """
MATCH (newer:Memory {id: $newer_id})-[conflict:CONTRADICTS]->(older:Memory)
RETURN older.id AS older_id,
    conflict.reason AS reason,
    conflict.detected_at AS detected_at
""",
            {"newer_id": newer_id},
        )
        for row in existing:
            pending[int(row["older_id"])] = (
                str(row["reason"] or "Previously detected contradiction."),
                str(row["detected_at"] or detected_at),
            )
        for conflict in conflicts:
            pending.setdefault(
                _parse_memory_id(conflict["id"]),
                (conflict["reason"], detected_at),
            )
        for older_id, (reason, event_at) in pending.items():
            self._apply_conflict(
                newer_id=newer_id,
                older_id=older_id,
                reason=reason,
                detected_at=event_at,
            )

    def _apply_conflict(
        self,
        *,
        newer_id: int,
        older_id: int,
        reason: str,
        detected_at: str,
    ) -> None:
        relationship_id = _relationship_id("CONTRADICTS", newer_id, older_id)
        existing = self._db.query(
            """
MATCH (newer:Memory {id: $newer_id})-[conflict:CONTRADICTS]->(older:Memory {id: $older_id})
RETURN conflict.detected_at AS detected_at,
    conflict.reason AS reason,
    conflict.before_trust AS before_trust,
    conflict.after_trust AS after_trust,
    conflict.apply_status AS apply_status
""",
            {"newer_id": newer_id, "older_id": older_id},
        )
        if existing:
            phase_value = existing[0]["apply_status"]
            if phase_value is None or str(phase_value) == "complete":
                return
            phase = str(phase_value)
            detected_at = str(existing[0]["detected_at"] or detected_at)
            reason = str(existing[0]["reason"] or reason)
            before_trust = float(existing[0]["before_trust"])
            after_trust = float(existing[0]["after_trust"])
        else:
            rows = self._db.query(
                """
MATCH (memory:Memory {id: $memory_id})
RETURN memory.trust_score AS trust_score
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
                            "relationship_id": relationship_id,
                            "detected_at": detected_at,
                            "reason": reason,
                            "before_trust": before_trust,
                            "after_trust": after_trust,
                            "apply_status": "recorded",
                        }
                    ]
                },
            )
            phase = "recorded"

        if phase == "recorded":
            status_rows = self._db.query(
                "MATCH (memory:Memory {id: $memory_id}) RETURN memory.status AS status",
                {"memory_id": older_id},
            )
            if not status_rows:
                return
            current_status = str(status_rows[0]["status"])
            self._db.execute_write(
                _UPDATE_MEMORY_TRUST,
                {
                    "rows": [
                        {
                            "vertex": older_id,
                            "trust_score": after_trust,
                            "status": (
                                "forgotten" if current_status == "forgotten" else "contradicted"
                            ),
                        }
                    ]
                },
            )
            self._set_conflict_phase(newer_id, older_id, "root_decayed")
            phase = "root_decayed"

        if phase != "root_decayed":
            raise RuntimeError(f"unexpected contradiction apply phase: {phase}")
        self._propagate_derived_decay(older_id, detected_at=detected_at)
        self._set_conflict_phase(newer_id, older_id, "complete")

    def _set_conflict_phase(self, newer_id: int, older_id: int, phase: str) -> None:
        self._db.execute_write(
            """
MATCH (newer:Memory {id: $newer_id})-[conflict:CONTRADICTS]->(older:Memory {id: $older_id})
SET conflict.apply_status = $phase
""",
            {"newer_id": newer_id, "older_id": older_id, "phase": phase},
        )

    def _propagate_derived_decay(self, source_id: int, *, detected_at: str) -> None:
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
        decay_rows = [
            {
                "dependent_id": dependent_id,
                "source_id": parent_id,
                "relationship_id": _relationship_id("DERIVED_FROM", dependent_id, parent_id),
                "event_id": _trust_decay_event_id(
                    dependent_id,
                    parent_id,
                    source_id,
                    detected_at,
                ),
                "before_trust": trust,
                "after_trust": _decay(trust, 0.15 * hop),
                "hop": hop,
                "caused_by": source_id,
                "decayed_at": detected_at,
                "reason": (f"Source memory {source_id} was contradicted; propagated {hop} hop(s)."),
                "status": status,
                "apply_status": "recorded",
            }
            for dependent_id, (hop, trust, status, parent_id) in dependents.items()
        ]
        for row in decay_rows:
            self._apply_derived_decay_event(row)

    def _apply_derived_decay_event(self, proposed: dict[str, object]) -> None:
        event_id = cast(int, proposed["event_id"])
        dependent_id = cast(int, proposed["dependent_id"])
        source_id = cast(int, proposed["source_id"])
        event_rows = self._db.query(
            """
MATCH (dependent:Memory {id: $dependent_id})-[event:TRUST_DECAY]->
    (source:Memory {id: $source_id})
RETURN dependent.id AS dependent_id,
    source.id AS source_id,
    event.detected_at AS decayed_at,
    event.reason AS reason,
    event.before_trust AS before_trust,
    event.after_trust AS after_trust,
    event.hop AS hop,
    event.caused_by AS caused_by,
    event.apply_status AS apply_status
""",
            {"dependent_id": dependent_id, "source_id": source_id},
        )
        expected_caused_by = cast(int, proposed["caused_by"])
        expected_decayed_at = cast(str, proposed["decayed_at"])
        existing = [
            row
            for row in event_rows
            if int(row["caused_by"]) == expected_caused_by
            and str(row["decayed_at"]) == expected_decayed_at
        ]
        if existing:
            phase_value = existing[0]["apply_status"]
            if phase_value is None or str(phase_value) == "complete":
                return
            row: dict[str, object] = {
                "dependent_id": int(existing[0]["dependent_id"]),
                "source_id": int(existing[0]["source_id"]),
                "relationship_id": _relationship_id(
                    "DERIVED_FROM",
                    int(existing[0]["dependent_id"]),
                    int(existing[0]["source_id"]),
                ),
                "event_id": event_id,
                "decayed_at": str(existing[0]["decayed_at"]),
                "reason": str(existing[0]["reason"]),
                "before_trust": float(existing[0]["before_trust"]),
                "after_trust": float(existing[0]["after_trust"]),
                "hop": int(existing[0]["hop"]),
                "caused_by": int(existing[0]["caused_by"]),
                "apply_status": "recorded",
            }
        else:
            row = proposed
            self._db.execute_write(_MERGE_DERIVED_DECAY_EVENTS, {"rows": [row]})

        status_rows = self._db.query(
            "MATCH (memory:Memory {id: $memory_id}) RETURN memory.status AS status",
            {"memory_id": row["dependent_id"]},
        )
        if not status_rows:
            return
        current_status = str(status_rows[0]["status"])
        row["status"] = "forgotten" if current_status == "forgotten" else current_status
        self._db.execute_write(
            _UPDATE_MEMORY_TRUST,
            {
                "rows": [
                    {
                        "vertex": row["dependent_id"],
                        "trust_score": row["after_trust"],
                        "status": row["status"],
                    }
                ]
            },
        )
        self._db.execute_write(_UPDATE_DERIVATION_DECAY, {"rows": [row]})
        completed = {**row, "apply_status": "complete"}
        self._db.execute_write(_MERGE_DERIVED_DECAY_EVENTS, {"rows": [completed]})

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
    -[event:TRUST_DECAY]->(source:Memory)
RETURN source.id AS source_id,
    event.detected_at AS decayed_at,
    event.reason AS reason,
    event.before_trust AS before_trust,
    event.after_trust AS after_trust
""",
            {"memory_id": memory_id},
        )
        durable_keys = {
            (
                str(row["source_id"]),
                str(row["decayed_at"]),
                float(row["before_trust"]),
                float(row["after_trust"]),
            )
            for row in rows
        }
        legacy_rows = self._db.query(
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
        for row in legacy_rows:
            if row["decayed_at"] is None:
                continue
            key = (
                str(row["source_id"]),
                str(row["decayed_at"]),
                float(row["before_trust"]),
                float(row["after_trust"]),
            )
            if key not in durable_keys:
                rows.append(row)
        for row in rows:
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
    aliased = _TERM_ALIASES.get(token)
    if aliased is not None:
        return aliased
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _normalize_entity_refs(entity_refs: list[str]) -> list[str]:
    if len(entity_refs) > MAX_ENTITY_REFS:
        raise ValueError(f"entity_refs must contain at most {MAX_ENTITY_REFS} items")
    normalized: list[str] = []
    seen: set[str] = set()
    for reference in entity_refs:
        entity = " ".join(
            _require_text(
                reference,
                "entity reference",
                maximum=MAX_ENTITY_REF_LENGTH,
            ).split()
        ).casefold()
        if entity not in seen:
            seen.add(entity)
            normalized.append(entity)
    return normalized


def _normalize_memory_refs(memory_refs: list[str]) -> list[int]:
    if len(memory_refs) > MAX_MEMORY_REFS:
        raise ValueError(f"derived_from must contain at most {MAX_MEMORY_REFS} items")
    normalized: list[int] = []
    seen: set[int] = set()
    for reference in memory_refs:
        memory_id = _parse_memory_id(reference)
        if memory_id not in seen:
            seen.add(memory_id)
            normalized.append(memory_id)
    return normalized


def _entity_id_predicate(
    scope: str,
    entities: list[str],
    parameters: dict[str, object],
) -> str:
    predicates: list[str] = []
    for index, entity in enumerate(entities):
        parameter = f"entity_id_{index}"
        parameters[parameter] = _entity_id(scope, entity)
        predicates.append(f"entity.id = ${parameter}")
    return " OR ".join(predicates)


def _entity_coordination_keys(scope: str, entities: list[str]) -> list[str]:
    return [f"entity:{scope}:{entity}" for entity in entities]


def _lock_stripe(key: str, stripe_count: int) -> int:
    digest = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % stripe_count


def _bounded_env_int(name: str, *, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _new_memory_id() -> int:
    payload = secrets.randbits(_ID_PAYLOAD_BITS) or 1
    return _MEMORY_ID_BASE | payload


def _idempotent_memory_id(scope: str, key: str) -> int:
    return _stable_id(_MEMORY_ID_BASE, f"memory:{scope}:{key}")


def _entity_id(scope: str, entity: str) -> int:
    return _stable_id(_ENTITY_ID_BASE, f"entity:{scope}:{entity}")


def _relationship_id(kind: str, source_id: int, target_id: int) -> int:
    return _stable_id(_RELATIONSHIP_ID_BASE, f"{kind}:{source_id}:{target_id}")


def _trust_decay_event_id(
    dependent_id: int,
    source_id: int,
    caused_by: int,
    detected_at: str,
) -> int:
    identity = f"TRUST_DECAY:{dependent_id}:{source_id}:{caused_by}:{detected_at}"
    return _stable_id(_RELATIONSHIP_ID_BASE, identity)


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


def _request_fingerprint(
    content: str,
    scope: str,
    entities: list[str],
    source_ids: list[int],
) -> str:
    payload = "\0".join(
        [content, scope, *entities, "derived", *(str(source_id) for source_id in source_ids)]
    )
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=16).hexdigest()


def _require_text(value: str, name: str, *, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    cleaned = value.strip()
    if maximum is not None and len(cleaned) > maximum:
        raise ValueError(f"{name} must be at most {maximum} characters")
    return cleaned


def _decay(score: float, amount: float) -> float:
    return round(max(0.05, score - amount), 6)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
