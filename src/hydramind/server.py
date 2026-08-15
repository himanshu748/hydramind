"""Stateless MCP entrypoints backed by durable HydraDB graph memory."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from hydramind.db import HydraDB, HydraDBError
from hydramind.tools import (
    ConflictResult,
    MemoryService,
    MemoryTrace,
    RecallResult,
    TimelineResult,
)

LOGGER = logging.getLogger("hydramind")
HYDRAMIND_VERSION = "0.3.0"


@dataclass(frozen=True, slots=True)
class RuntimeState:
    """Process resources shared by requests without storing MCP session data."""

    service: MemoryService


@asynccontextmanager
async def hydramind_lifespan(_: MCPServer[RuntimeState]) -> AsyncIterator[RuntimeState]:
    """Verify Bolt before serving and keep only the reusable driver pool in memory."""

    db: HydraDB | None = None
    try:
        db = HydraDB()
        db.verify_connection()
        db.setup_schema()
    except HydraDBError as exc:
        if db is not None:
            db.close()
        LOGGER.error("HydraMind startup failed: %s", exc)
        raise RuntimeError(f"HydraMind startup failed: {exc}") from exc
    assert db is not None
    try:
        try:
            source = os.getenv("HYDRAMIND_SOURCE") or "mcp"
            service = MemoryService(db, source=source)
        except ValueError as exc:
            LOGGER.error("HydraMind startup failed: invalid configuration: %s", exc)
            raise RuntimeError(f"HydraMind startup failed: invalid configuration: {exc}") from exc
        yield RuntimeState(service=service)
    finally:
        db.close()


mcp = MCPServer[RuntimeState](
    "HydraMind",
    title="HydraMind",
    description="Persistent, trust-weighted graph memory backed by HydraDB.",
    instructions=(
        "Stateless MCP tools backed exclusively by durable HydraDB graph state. "
        "Recall can return an empty list when evidence is absent; treat that as "
        "an instruction to abstain."
    ),
    version=HYDRAMIND_VERSION,
    lifespan=hydramind_lifespan,
)


@mcp.tool()
def remember(
    content: str,
    scope: str,
    entity_refs: list[str],
    ctx: Context[RuntimeState],
    derived_from: list[str] | None = None,
    idempotency_key: str | None = None,
) -> str:
    """Store durable memory, with optional retry deduplication for fallible agent calls."""

    return ctx.request_context.lifespan_context.service.remember(
        content,
        scope,
        entity_refs,
        derived_from,
        idempotency_key,
    )


@mcp.tool()
def recall(
    query: str,
    scope: str,
    ctx: Context[RuntimeState],
    entity_refs: list[str] | None = None,
    limit: int = 10,
) -> list[RecallResult]:
    """Recall scoped evidence ranked by transparent text relevance and durable trust."""

    return ctx.request_context.lifespan_context.service.recall(
        query,
        scope,
        entity_refs,
        limit,
    )


@mcp.tool()
def revise(
    memory_id: str,
    content: str,
    scope: str,
    ctx: Context[RuntimeState],
    reason: str = "Explicit revision.",
    entity_refs: list[str] | None = None,
) -> str:
    """Replace a fact explicitly while preserving its dated revision chain for agents."""

    return ctx.request_context.lifespan_context.service.revise(
        memory_id,
        content,
        scope,
        reason=reason,
        entity_refs=entity_refs,
    )


@mcp.tool()
def timeline(
    scope: str,
    entity_ref: str,
    ctx: Context[RuntimeState],
    limit: int = 20,
) -> list[TimelineResult]:
    """Read an entity's chronology so agents can distinguish current facts from history."""

    return ctx.request_context.lifespan_context.service.timeline(scope, entity_ref, limit)


@mcp.tool()
def trace_memory(
    memory_id: str,
    scope: str,
    ctx: Context[RuntimeState],
    max_hops: int = 2,
    max_paths: int = 20,
) -> MemoryTrace:
    """Expose native HydraDB evidence paths so agents can inspect graph reasoning."""

    return ctx.request_context.lifespan_context.service.trace_memory(
        memory_id,
        scope,
        max_hops=max_hops,
        max_paths=max_paths,
    )


@mcp.tool()
def check_conflict(
    content: str,
    entity_refs: list[str],
    scope: str,
    ctx: Context[RuntimeState],
) -> list[ConflictResult]:
    """Flag plausible contradictions inside one explicit scope before an agent writes."""

    return ctx.request_context.lifespan_context.service.check_conflict(
        content,
        entity_refs,
        scope,
    )


@mcp.tool()
def explain_trust(
    memory_id: str,
    scope: str,
    ctx: Context[RuntimeState],
) -> list[str]:
    """Explain persisted trust changes while enforcing a scoped direct-ID lookup."""

    return ctx.request_context.lifespan_context.service.explain_trust(memory_id, scope)


@mcp.tool()
def forget(
    memory_id: str,
    scope: str,
    ctx: Context[RuntimeState],
) -> bool:
    """Tombstone one scoped memory without deleting its durable graph provenance."""

    return ctx.request_context.lifespan_context.service.forget(memory_id, scope)


def main() -> None:
    """Serve modern sessionless MCP and legacy-compatible MCP over local stdio."""

    _configure_logging()
    mcp.run(transport="stdio")


def http_main() -> None:
    """Serve stateless Streamable HTTP for modern and legacy MCP clients."""

    _configure_logging()
    host = os.getenv("HYDRAMIND_MCP_HOST", "127.0.0.1")
    port = _bounded_int("HYDRAMIND_MCP_PORT", default=8788, minimum=1, maximum=65535)
    max_body = _bounded_int(
        "HYDRAMIND_MCP_MAX_BODY_BYTES",
        default=1_048_576,
        minimum=1024,
        maximum=4_194_304,
    )
    LOGGER.info("HydraMind stateless MCP: http://%s:%s/mcp", host, port)
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        max_request_body_size=max_body,
    )


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)


def _bounded_int(name: str, *, default: int, minimum: int, maximum: int) -> int:
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
