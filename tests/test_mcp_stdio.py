"""End-to-end test through the official MCP stdio client transport."""

from __future__ import annotations

import os
import sys
from uuid import uuid4

import anyio
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from hydramind.db import HydraDB

pytestmark = pytest.mark.integration


def test_real_mcp_client_can_remember_recall_and_forget(live_db: HydraDB) -> None:
    scope = f"pytest-mcp-{uuid4()}"
    entity = f"{scope}:hydradb"

    async def exercise_server() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "hydramind"],
            env=dict(os.environ),
            cwd=os.getcwd(),
        )
        async with Client(stdio_client(parameters)) as client:
            assert client.protocol_version == "2026-07-28"
            tool_names = {tool.name for tool in (await client.list_tools()).tools}
            assert tool_names == {
                "remember",
                "recall",
                "revise",
                "timeline",
                "trace_memory",
                "check_conflict",
                "explain_trust",
                "forget",
            }
            remembered = await client.call_tool(
                "remember",
                {
                    "content": "HydraMind persists memory through real MCP stdio.",
                    "scope": scope,
                    "entity_refs": [entity],
                },
            )
            assert not remembered.is_error
            assert remembered.structured_content is not None
            memory_id = str(remembered.structured_content["result"])

            recalled = await client.call_tool(
                "recall",
                {
                    "query": "real MCP stdio",
                    "scope": scope,
                    "entity_refs": [entity],
                    "limit": 3,
                },
            )
            assert not recalled.is_error
            assert recalled.structured_content is not None
            results = recalled.structured_content["result"]
            assert isinstance(results, list)
            assert results[0]["id"] == memory_id

            revised = await client.call_tool(
                "revise",
                {
                    "memory_id": memory_id,
                    "content": "HydraMind persists revised memory through real MCP stdio.",
                    "scope": scope,
                    "reason": "The E2E scenario changed the fact.",
                },
            )
            assert not revised.is_error
            assert revised.structured_content is not None
            revised_id = str(revised.structured_content["result"])

            timeline = await client.call_tool(
                "timeline",
                {"scope": scope, "entity_ref": entity},
            )
            assert not timeline.is_error
            assert timeline.structured_content is not None
            history = timeline.structured_content["result"]
            assert [entry["id"] for entry in history] == [memory_id, revised_id]

            trace = await client.call_tool(
                "trace_memory",
                {"memory_id": revised_id, "scope": scope, "max_hops": 2},
            )
            assert not trace.is_error
            assert trace.structured_content is not None
            assert trace.structured_content["engine"] == "HydraDB algo.SSpaths"
            assert trace.structured_content["paths"]

            forgotten = await client.call_tool(
                "forget",
                {"memory_id": revised_id, "scope": scope},
            )
            assert not forgotten.is_error
            assert forgotten.structured_content == {"result": True}

    try:
        anyio.run(exercise_server)
    finally:
        live_db.execute_write(
            "MATCH (memory:Memory) WHERE memory.scope = $scope DETACH DELETE memory",
            {"scope": scope},
        )
        live_db.execute_write(
            "MATCH (node:Entity) WHERE node.name = $name DETACH DELETE node",
            {"name": entity},
        )


def test_memory_survives_fresh_stateless_stdio_processes(live_db: HydraDB) -> None:
    scope = f"pytest-stateless-{uuid4()}"
    entity = f"{scope}:restart"

    async def remember_in_first_process() -> str:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "hydramind"],
            env=dict(os.environ),
            cwd=os.getcwd(),
        )
        async with Client(stdio_client(parameters)) as client:
            assert client.protocol_version == "2026-07-28"
            result = await client.call_tool(
                "remember",
                {
                    "content": "Stateless MCP restarts retain durable HydraDB memory.",
                    "scope": scope,
                    "entity_refs": [entity],
                },
            )
            assert result.structured_content is not None
            return str(result.structured_content["result"])

    async def recall_in_fresh_process(memory_id: str) -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "hydramind"],
            env=dict(os.environ),
            cwd=os.getcwd(),
        )
        async with Client(stdio_client(parameters)) as client:
            assert client.protocol_version == "2026-07-28"
            result = await client.call_tool(
                "recall",
                {
                    "query": "stateless restarts durable memory",
                    "scope": scope,
                    "entity_refs": [entity],
                },
            )
            assert result.structured_content is not None
            memories = result.structured_content["result"]
            assert isinstance(memories, list)
            assert memories[0]["id"] == memory_id

    try:
        memory_id = anyio.run(remember_in_first_process)
        anyio.run(recall_in_fresh_process, memory_id)
    finally:
        live_db.execute_write(
            "MATCH (memory:Memory) WHERE memory.scope = $scope DETACH DELETE memory",
            {"scope": scope},
        )
        live_db.execute_write(
            "MATCH (node:Entity) WHERE node.name = $name DETACH DELETE node",
            {"name": entity},
        )
