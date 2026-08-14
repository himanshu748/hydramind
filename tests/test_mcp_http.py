"""Live checks for HydraMind's stateless Streamable HTTP transport."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import anyio
import pytest
from mcp import Client

from hydramind.db import HydraDB

pytestmark = pytest.mark.integration


def test_fresh_http_clients_share_only_durable_hydradb_state(live_db: HydraDB) -> None:
    scope = f"pytest-http-stateless-{uuid4()}"
    entity = f"{scope}:transport"

    async def exercise(url: str) -> None:
        async with Client(url) as first_client:
            assert first_client.protocol_version == "2026-07-28"
            remembered = await first_client.call_tool(
                "remember",
                {
                    "content": "Stateless HTTP stores every durable fact in HydraDB.",
                    "scope": scope,
                    "entity_refs": [entity],
                },
            )
            assert remembered.structured_content is not None
            memory_id = str(remembered.structured_content["result"])

        async with Client(url) as second_client:
            assert second_client.protocol_version == "2026-07-28"
            recalled = await second_client.call_tool(
                "recall",
                {
                    "query": "stateless HTTP durable fact",
                    "scope": scope,
                    "entity_refs": [entity],
                },
            )
            assert recalled.structured_content is not None
            memories = recalled.structured_content["result"]
            assert isinstance(memories, list)
            assert memories[0]["id"] == memory_id

        concurrent_ids: set[str] = set()

        async def write_concurrently(index: int) -> None:
            async with Client(url) as client:
                result = await client.call_tool(
                    "remember",
                    {
                        "content": f"Concurrent request {index} writes independent memory.",
                        "scope": scope,
                        "entity_refs": [entity],
                    },
                )
                assert result.structured_content is not None
                concurrent_ids.add(str(result.structured_content["result"]))

        async with anyio.create_task_group() as tasks:
            for index in range(4):
                tasks.start_soon(write_concurrently, index)

        async with Client(url) as verification_client:
            recalled = await verification_client.call_tool(
                "recall",
                {
                    "query": "concurrent request independent memory",
                    "scope": scope,
                    "entity_refs": [entity],
                    "limit": 10,
                },
            )
            assert recalled.structured_content is not None
            memories = recalled.structured_content["result"]
            assert isinstance(memories, list)
            recalled_ids = {str(memory["id"]) for memory in memories}
            assert len(concurrent_ids) == 4
            assert concurrent_ids <= recalled_ids

    try:
        with _running_http_server() as url:
            anyio.run(exercise, url)
    finally:
        live_db.execute_write(
            "MATCH (memory:Memory) WHERE memory.scope = $scope DETACH DELETE memory",
            {"scope": scope},
        )
        live_db.execute_write(
            "MATCH (node:Entity) WHERE node.name = $name DETACH DELETE node",
            {"name": entity},
        )


@contextmanager
def _running_http_server() -> Iterator[str]:
    port = _unused_local_port()
    env = dict(os.environ)
    env["HYDRAMIND_MCP_HOST"] = "127.0.0.1"
    env["HYDRAMIND_MCP_PORT"] = str(port)
    process = subprocess.Popen(
        [sys.executable, "-c", "from hydramind.server import http_main; http_main()"],
        cwd=Path.cwd(),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_until_listening(process, port)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _unused_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_until_listening(process: subprocess.Popen[str], port: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr is not None else ""
            raise AssertionError(f"stateless MCP server exited early: {stderr}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError("stateless MCP server did not start within 10 seconds")
