import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.bot.runtime import BotRuntime
from app.bot.state import BotState
from app.main import app


def ws_token_url() -> str:
    return "/ws/live?token=demo-bot-control-token"


class FakeStrategyService:
    async def evaluate(self, symbol: str):
        return SimpleNamespace(
            evaluation_time=datetime.now(timezone.utc),
            signal=None,
            reason_codes=(),
        )


class RecordingHub:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    async def publish(self, event: str, data: object) -> None:
        self.events.append((event, data))


def test_ws_live_endpoint_accepts_connection_and_emits_system_event() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            message = websocket.receive_json()
            assert message["event"] == "system_event"
            assert message["data"]["message"] == "Live WebSocket connected"
            assert message["event_id"].startswith("ws-")


def test_runtime_publishes_running_and_stopped_status() -> None:
    async def scenario() -> None:
        hub = RecordingHub()
        runtime = BotRuntime(
            FakeStrategyService(),
            realtime_hub=hub,  # type: ignore[arg-type]
            state=BotState(),
            symbols=("BTCUSDT",),
            poll_interval_seconds=1,
        )
        await runtime.start()
        await runtime.stop()
        statuses = [data["status"] for event, data in hub.events if event == "bot_status"]  # type: ignore[index]
        assert statuses == ["RUNNING", "STOPPED"]

    asyncio.run(scenario())
