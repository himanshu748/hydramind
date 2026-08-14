"""MCP surface tests that do not require a running database."""

from __future__ import annotations

import anyio
import pytest

from hydramind.server import http_main, mcp


def test_server_registers_the_eight_documented_tools() -> None:
    tools = anyio.run(mcp.list_tools)
    by_name = {tool.name: tool for tool in tools}

    assert set(by_name) == {
        "remember",
        "recall",
        "revise",
        "timeline",
        "trace_memory",
        "check_conflict",
        "explain_trust",
        "forget",
    }
    assert all(tool.description for tool in by_name.values())
    assert by_name["remember"].input_schema["required"] == [
        "content",
        "scope",
        "entity_refs",
    ]
    assert "derived_from" in by_name["remember"].input_schema["properties"]
    assert by_name["revise"].input_schema["required"] == [
        "memory_id",
        "content",
        "scope",
    ]
    assert by_name["timeline"].input_schema["required"] == ["scope", "entity_ref"]
    assert by_name["trace_memory"].input_schema["required"] == ["memory_id", "scope"]


def test_http_entrypoint_forces_stateless_json_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def capture_run(*, transport: str, **kwargs: object) -> None:
        captured["transport"] = transport
        captured.update(kwargs)

    monkeypatch.setattr(mcp, "run", capture_run)
    monkeypatch.setenv("HYDRAMIND_MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("HYDRAMIND_MCP_PORT", "9876")

    http_main()

    assert captured == {
        "transport": "streamable-http",
        "host": "127.0.0.1",
        "port": 9876,
        "streamable_http_path": "/mcp",
        "json_response": True,
        "stateless_http": True,
        "max_request_body_size": 1_048_576,
    }
