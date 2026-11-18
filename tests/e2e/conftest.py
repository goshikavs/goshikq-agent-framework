"""One goshikq-server + embedded/Postgres cluster for the v1 E2E package."""

from __future__ import annotations

import pytest

from tests.helpers import find_server, free_port, start_server, stop, wait_ready


@pytest.fixture(scope="session")
def runtime_url():
    if find_server() is None:
        pytest.skip("goshikq-server binary not found")
    port = free_port()
    proc = start_server(port)
    url = f"http://127.0.0.1:{port}"
    try:
        wait_ready(url, timeout=120.0, proc=proc)
        yield url
    finally:
        stop(proc)
