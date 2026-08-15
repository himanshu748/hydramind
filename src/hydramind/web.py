"""Local web dashboard for inspecting and exercising HydraMind's live graph."""

from __future__ import annotations

import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlparse

from hydramind.db import HydraDB, HydraDBError
from hydramind.tools import MemoryService

MAX_DASHBOARD_BODY_BYTES = 1_048_576


class DashboardService:
    """Expose dashboard-shaped reads and writes over the existing memory service."""

    def __init__(self, db: HydraDB) -> None:
        self.db = db
        self.memories = MemoryService(db, source="ui")

    def state(self, scope: str) -> dict[str, object]:
        """Return memories, entities, and provenance edges for one scope."""

        clean_scope = _required_text(scope, "scope")
        memory_rows = self.db.query(
            """
MATCH (memory:Memory)
WHERE memory.scope = $scope AND memory.status <> $forgotten
RETURN memory.id AS id,
    memory.content AS content,
    memory.source AS source,
    memory.created_at AS created_at,
    memory.valid_from AS valid_from,
    memory.valid_to AS valid_to,
    memory.trust_score AS trust_score,
    memory.status AS status
ORDER BY created_at DESC
""",
            {"scope": clean_scope, "forgotten": "forgotten"},
        )
        memories: list[dict[str, object]] = [
            {
                "id": str(row["id"]),
                "content": str(row["content"]),
                "source": str(row["source"]),
                "created_at": str(row["created_at"]),
                "valid_from": str(row["valid_from"] or row["created_at"]),
                "valid_to": None if row["valid_to"] is None else str(row["valid_to"]),
                "trust_score": float(row["trust_score"]),
                "status": str(row["status"]),
                "entities": [],
            }
            for row in memory_rows
        ]
        by_id = {str(memory["id"]): memory for memory in memories}
        entity_rows = self.db.query(
            """
MATCH (memory:Memory)-[:ABOUT]->(entity:Entity)
WHERE memory.scope = $scope AND memory.status <> $forgotten
RETURN memory.id AS memory_id, entity.name AS entity_name
ORDER BY entity_name
""",
            {"scope": clean_scope, "forgotten": "forgotten"},
        )
        for row in entity_rows:
            memory = by_id.get(str(row["memory_id"]))
            if memory is not None:
                entities = memory["entities"]
                if isinstance(entities, list):
                    entities.append(str(row["entity_name"]))

        contradiction_rows = self.db.query(
            """
MATCH (newer:Memory)-[edge:CONTRADICTS]->(older:Memory)
WHERE newer.scope = $scope AND older.scope = $scope
RETURN newer.id AS source,
    older.id AS target,
    edge.detected_at AS detected_at,
    edge.reason AS reason
""",
            {"scope": clean_scope},
        )
        derivation_rows = self.db.query(
            """
MATCH (derived:Memory)-[edge:DERIVED_FROM]->(source:Memory)
WHERE derived.scope = $scope AND source.scope = $scope
RETURN derived.id AS source,
    source.id AS target,
    edge.decay_hop AS decay_hop,
    edge.last_decayed_at AS last_decayed_at
""",
            {"scope": clean_scope},
        )
        revision_rows = self.db.query(
            """
MATCH (older:Memory)-[edge:SUPERSEDED_BY]->(newer:Memory)
WHERE older.scope = $scope AND newer.scope = $scope
RETURN older.id AS source,
    newer.id AS target,
    edge.revised_at AS revised_at,
    edge.reason AS reason
ORDER BY revised_at
""",
            {"scope": clean_scope},
        )
        return {
            "scope": clean_scope,
            "memories": memories,
            "contradictions": [
                {
                    "source": str(row["source"]),
                    "target": str(row["target"]),
                    "detected_at": str(row["detected_at"]),
                    "reason": str(row["reason"]),
                }
                for row in contradiction_rows
            ],
            "derivations": [
                {
                    "source": str(row["source"]),
                    "target": str(row["target"]),
                    "decay_hop": int(row["decay_hop"]) if row["decay_hop"] is not None else None,
                    "last_decayed_at": (
                        str(row["last_decayed_at"]) if row["last_decayed_at"] is not None else None
                    ),
                }
                for row in derivation_rows
            ],
            "revisions": [
                {
                    "source": str(row["source"]),
                    "target": str(row["target"]),
                    "revised_at": str(row["revised_at"]),
                    "reason": str(row["reason"]),
                }
                for row in revision_rows
            ],
        }

    def seed_demo(self, scope: str) -> dict[str, object]:
        """Create a repeatable real graph when the selected scope is empty."""

        clean_scope = _required_text(scope, "scope")
        current = self.state(clean_scope)
        if current["memories"]:
            return current
        root = self.memories.remember(
            "Production deploys must always use direct routing.",
            clean_scope,
            ["deploy-policy"],
        )
        checklist = self.memories.remember(
            "The release checklist is based on the production routing policy.",
            clean_scope,
            ["release-checklist"],
            derived_from=[root],
        )
        self.memories.remember(
            "The incident runbook is derived from the release checklist.",
            clean_scope,
            ["incident-runbook"],
            derived_from=[checklist],
        )
        self.memories.remember(
            "Production deploys must not use direct routing.",
            clean_scope,
            ["deploy-policy"],
        )
        old_runtime = self.memories.remember(
            "Agent tooling runs on Python 3.12.",
            clean_scope,
            ["agent-runtime"],
        )
        self.memories.revise(
            old_runtime,
            "Agent tooling runs on Python 3.13.",
            clean_scope,
            reason="The supported runtime was upgraded.",
        )
        return self.state(clean_scope)


class HydraMindRequestHandler(BaseHTTPRequestHandler):
    """Serve the built React app and its small same-origin JSON API."""

    dashboard: ClassVar[DashboardService]
    static_root: ClassVar[Path]

    def do_GET(self) -> None:  # noqa: N802
        """Serve dashboard state, trust explanations, or static assets."""

        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/health":
                self.dashboard.db.verify_connection()
                self._send_json({"connected": True})
                return
            if parsed.path == "/api/state":
                scope = _query_value(parsed.query, "scope", "acme-platform")
                self._send_json(self.dashboard.state(scope))
                return
            if parsed.path == "/api/explain":
                memory_id = _query_value(parsed.query, "memory_id")
                scope = _query_value(parsed.query, "scope")
                self._send_json(
                    {"chain": self.dashboard.memories.explain_trust(memory_id, scope=scope)}
                )
                return
            if parsed.path == "/api/timeline":
                scope = _query_value(parsed.query, "scope")
                entity_ref = _query_value(parsed.query, "entity_ref")
                limit = int(_query_value(parsed.query, "limit", "20"))
                self._send_json(
                    {"timeline": self.dashboard.memories.timeline(scope, entity_ref, limit)}
                )
                return
            if parsed.path == "/api/trace":
                memory_id = _query_value(parsed.query, "memory_id")
                scope = _query_value(parsed.query, "scope")
                max_hops = int(_query_value(parsed.query, "max_hops", "2"))
                max_paths = int(_query_value(parsed.query, "max_paths", "20"))
                self._send_json(
                    self.dashboard.memories.trace_memory(
                        memory_id,
                        scope,
                        max_hops=max_hops,
                        max_paths=max_paths,
                    )
                )
                return
            self._serve_static(parsed.path)
        except (HydraDBError, ValueError) as exc:
            self._send_error(exc)

    def do_POST(self) -> None:  # noqa: N802
        """Handle real remember, revise, recall, conflict, forget, and demo operations."""

        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            scope = _payload_text(payload, "scope")
            if parsed.path == "/api/demo":
                self._send_json(self.dashboard.seed_demo(scope))
                return
            if parsed.path == "/api/recall":
                results = self.dashboard.memories.recall(
                    _payload_text(payload, "query"),
                    scope,
                    _payload_string_list(payload, "entity_refs", required=False),
                    int(payload.get("limit", 10)),
                )
                self._send_json({"results": results})
                return
            if parsed.path == "/api/conflicts":
                conflicts = self.dashboard.memories.check_conflict(
                    _payload_text(payload, "content"),
                    _payload_string_list(payload, "entity_refs"),
                    scope=scope,
                )
                self._send_json({"conflicts": conflicts})
                return
            if parsed.path == "/api/remember":
                memory_id = self.dashboard.memories.remember(
                    _payload_text(payload, "content"),
                    scope,
                    _payload_string_list(payload, "entity_refs"),
                    _payload_string_list(payload, "derived_from", required=False),
                )
                self._send_json({"memory_id": memory_id}, status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/revise":
                entity_refs = (
                    _payload_string_list(payload, "entity_refs")
                    if "entity_refs" in payload
                    else None
                )
                memory_id = self.dashboard.memories.revise(
                    _payload_text(payload, "memory_id"),
                    _payload_text(payload, "content"),
                    scope,
                    reason=_payload_text_default(payload, "reason", "Explicit revision."),
                    entity_refs=entity_refs,
                )
                self._send_json({"memory_id": memory_id}, status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/forget":
                success = self.dashboard.memories.forget(
                    _payload_text(payload, "memory_id"),
                    scope=scope,
                )
                self._send_json({"success": success})
                return
            self._send_json({"error": "Unknown API route."}, status=HTTPStatus.NOT_FOUND)
        except (HydraDBError, ValueError, json.JSONDecodeError) as exc:
            self._send_error(exc)

    def _read_json(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").partition(";")[0].strip().casefold()
        if content_type != "application/json":
            raise ValueError("Content-Type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length must be an integer") from exc
        if not 0 <= length <= MAX_DASHBOARD_BODY_BYTES:
            raise ValueError(f"JSON body must be at most {MAX_DASHBOARD_BODY_BYTES} bytes")
        try:
            body = self.rfile.read(length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("JSON body must be valid UTF-8") from exc
        value = json.loads(body or "{}")
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        candidate = (self.static_root / relative).resolve()
        if self.static_root not in candidate.parents and candidate != self.static_root:
            self._send_json({"error": "Invalid path."}, status=HTTPStatus.BAD_REQUEST)
            return
        if not candidate.is_file():
            candidate = self.static_root / "index.html"
        content = candidate.read_bytes()
        mime_type, _ = mimetypes.guess_type(candidate.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, value: object, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_error(self, exc: Exception) -> None:
        status = (
            HTTPStatus.SERVICE_UNAVAILABLE
            if isinstance(exc, HydraDBError)
            else HTTPStatus.BAD_REQUEST
        )
        self._send_json({"error": str(exc)}, status=status)

    def log_message(self, format_string: str, *args: object) -> None:
        """Keep useful access logs on stderr without writing to protocol stdout."""

        print(f"HydraMind UI: {format_string % args}", file=sys.stderr)


def _query_value(query: str, name: str, default: str | None = None) -> str:
    values = parse_qs(query).get(name)
    if values:
        return _required_text(values[0], name)
    if default is not None:
        return default
    raise ValueError(f"missing query parameter: {name}")


def _payload_text(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return _required_text(value, name)


def _payload_text_default(payload: dict[str, Any], name: str, default: str) -> str:
    value = payload.get(name, default)
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return _required_text(value, name)


def _payload_string_list(
    payload: dict[str, Any],
    name: str,
    *,
    required: bool = True,
) -> list[str]:
    value = payload.get(name)
    if value is None and not required:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a list of strings")
    return [item for item in value if item.strip()]


def _required_text(value: str, name: str) -> str:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value.strip()


def main() -> None:
    """Verify HydraDB and serve the built dashboard on a local HTTP endpoint."""

    module_root = Path(__file__).resolve().parent
    source_static_root = module_root.parents[1] / "ui" / "dist"
    packaged_static_root = module_root / "ui"
    static_root = source_static_root if source_static_root.is_dir() else packaged_static_root
    if not static_root.is_dir():
        print(
            "HydraMind UI is not built. Run: cd ui && npm install && npm run build", file=sys.stderr
        )
        raise SystemExit(1)
    host = os.getenv("HYDRAMIND_UI_HOST", "127.0.0.1")
    port = _bounded_env_int("HYDRAMIND_UI_PORT", default=8787, minimum=1, maximum=65535)
    db: HydraDB | None = None
    try:
        db = HydraDB()
        db.verify_connection()
        db.setup_schema()
        dashboard = DashboardService(db)
    except (HydraDBError, ValueError) as exc:
        if db is not None:
            db.close()
        print(f"HydraMind UI startup failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    assert db is not None
    HydraMindRequestHandler.dashboard = dashboard
    HydraMindRequestHandler.static_root = static_root
    try:
        server = ThreadingHTTPServer((host, port), HydraMindRequestHandler)
    except OSError as exc:
        db.close()
        print(
            f"HydraMind UI startup failed: cannot listen on {host}:{port}: {exc}", file=sys.stderr
        )
        raise SystemExit(1) from exc
    print(f"HydraMind UI: http://{host}:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        db.close()


def _bounded_env_int(name: str, *, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise SystemExit(f"{name} must be between {minimum} and {maximum}")
    return value


if __name__ == "__main__":
    main()
