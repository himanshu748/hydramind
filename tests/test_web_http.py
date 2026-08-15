"""End-to-end checks for the packaged dashboard and same-origin JSON API."""

from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest

from hydramind.db import HydraDB
from hydramind.web import MAX_DASHBOARD_BODY_BYTES

pytestmark = pytest.mark.integration


def test_real_dashboard_http_api_handles_success_and_malformed_requests(live_db: HydraDB) -> None:
    scope = f"pytest-web-http-{uuid4()}"
    entity = f"{scope}:api"
    try:
        with _running_web_server() as (base_url, port):
            status, health = _json_request(f"{base_url}/api/health")
            assert status == 200
            assert health == {"connected": True}

            status, remembered = _json_request(
                f"{base_url}/api/remember",
                method="POST",
                payload={
                    "content": "The packaged dashboard writes through the real HTTP API.",
                    "scope": scope,
                    "entity_refs": [entity],
                },
            )
            assert status == 201
            memory_id = str(remembered["memory_id"])

            status, state = _json_request(f"{base_url}/api/state?scope={scope}")
            assert status == 200
            assert [memory["id"] for memory in state["memories"]] == [memory_id]

            status, error = _json_request(
                f"{base_url}/api/remember",
                method="POST",
                raw_body=b"not-json",
            )
            assert status == 400
            assert "Expecting value" in str(error["error"])

            wrong_type = Request(
                f"{base_url}/api/remember",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "text/plain"},
            )
            with pytest.raises(HTTPError) as wrong_type_error:
                urlopen(wrong_type, timeout=5)
            assert wrong_type_error.value.code == 400

            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            connection.putrequest("POST", "/api/remember")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(MAX_DASHBOARD_BODY_BYTES + 1))
            connection.endheaders()
            response = connection.getresponse()
            oversized = json.loads(response.read())
            connection.close()
            assert response.status == 400
            assert "at most" in oversized["error"]

            status, unknown = _json_request(
                f"{base_url}/api/not-a-route",
                method="POST",
                payload={"scope": scope},
            )
            assert status == 404
            assert unknown == {"error": "Unknown API route."}

            with urlopen(f"{base_url}/app", timeout=5) as page:
                html = page.read().decode("utf-8")
            assert "HydraMind" in html
            assert 'id="root"' in html
    finally:
        live_db.execute_write(
            "MATCH (memory:Memory) WHERE memory.scope = $scope DETACH DELETE memory",
            {"scope": scope},
        )
        live_db.execute_write(
            "MATCH (entity:Entity) WHERE entity.name = $name DETACH DELETE entity",
            {"name": entity},
        )


def _json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    raw_body: bytes | None = None,
) -> tuple[int, dict[str, object]]:
    body = (
        raw_body
        if raw_body is not None
        else None
        if payload is None
        else json.dumps(payload).encode()
    )
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if method == "POST" else {},
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


@contextmanager
def _running_web_server() -> Iterator[tuple[str, int]]:
    port = _unused_local_port()
    env = dict(os.environ)
    env["HYDRAMIND_UI_HOST"] = "127.0.0.1"
    env["HYDRAMIND_UI_PORT"] = str(port)
    process = subprocess.Popen(
        [sys.executable, "-c", "from hydramind.web import main; main()"],
        cwd=Path.cwd(),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_until_listening(process, port)
        yield f"http://127.0.0.1:{port}", port
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
            raise AssertionError(f"dashboard server exited early: {stderr}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError("dashboard server did not start within 10 seconds")
