from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.bot.state import bot_state
from app.main import app, bot_runtime

client = TestClient(app)


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer demo-bot-control-token"}


@pytest.fixture(autouse=True)
def reset_bot_state() -> Generator[None, None, None]:
    original_leadership = bot_runtime._runtime_leadership

    # API unit tests must not compete with a real/local backend process
    # for the cross-process execution leadership lock.
    bot_runtime._runtime_leadership = None
    bot_state.stop()

    yield

    bot_state.stop()
    bot_runtime._runtime_leadership = original_leadership


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_initial_status_is_stopped() -> None:
    response = client.get("/status")

    assert response.status_code == 200
    assert response.json() == {"bot_status": "stopped"}


def test_start_bot_and_get_running_status() -> None:
    start_response = client.post("/bot/start", headers=auth_headers())
    status_response = client.get("/status")

    assert start_response.status_code == 200
    assert start_response.json() == {"bot_status": "running"}
    assert status_response.status_code == 200
    assert status_response.json() == {"bot_status": "running"}


def test_start_bot_is_idempotent() -> None:
    client.post("/bot/start", headers=auth_headers())
    response = client.post("/bot/start", headers=auth_headers())

    assert response.status_code == 200
    assert response.json() == {"bot_status": "running"}


def test_stop_bot_and_get_stopped_status() -> None:
    client.post("/bot/start", headers=auth_headers())
    stop_response = client.post("/bot/stop", headers=auth_headers())
    status_response = client.get("/status")

    assert stop_response.status_code == 200
    assert stop_response.json() == {"bot_status": "stopped"}
    assert status_response.status_code == 200
    assert status_response.json() == {"bot_status": "stopped"}


def test_stop_bot_is_idempotent() -> None:
    client.post("/bot/stop", headers=auth_headers())
    response = client.post("/bot/stop", headers=auth_headers())

    assert response.status_code == 200
    assert response.json() == {"bot_status": "stopped"}
