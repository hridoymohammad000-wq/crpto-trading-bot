import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings
from app.exchange.bybit import BybitDemoClient, NormalizedOrderValues, OrderAcknowledgement
from app.execution import ExecutionService
from app.exchange.bybit.exceptions import BybitConnectionError
from app.persistence import PersistenceDatabase
from app.models.risk import RiskDecision, RiskDecisionStatus
from app.models.signal import SignalSide


def settings() -> Settings:
    return Settings(
        _env_file=None,
        BYBIT_API_KEY="fake-key",
        BYBIT_API_SECRET="fake-secret",
        BYBIT_DEMO=True,
    )


def instrument_response() -> dict[str, object]:
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "list": [
                {
                    "symbol": "BTCUSDT",
                    "lotSizeFilter": {
                        "qtyStep": "0.001",
                        "minOrderQty": "0.001",
                        "maxMktOrderQty": "100",
                        "minNotionalValue": "5",
                    },
                    "priceFilter": {"tickSize": "0.10"},
                    "leverageFilter": {"maxLeverage": "100"},
                }
            ]
        },
    }


def test_normalize_order_values_is_side_aware_and_step_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v5/market/instruments-info"
        return httpx.Response(200, json=instrument_response())

    client = BybitDemoClient(settings(), transport=httpx.MockTransport(handler))
    try:
        buy = asyncio.run(
            client.normalize_order_values(
                symbol="BTCUSDT",
                side="Buy",
                quantity=Decimal("0.0019"),
                reference_entry_price=Decimal("100000"),
                stop_loss=Decimal("99123.47"),
                take_profit=Decimal("101753.43"),
            )
        )
        sell = asyncio.run(
            client.normalize_order_values(
                symbol="BTCUSDT",
                side="Sell",
                quantity=Decimal("0.0019"),
                reference_entry_price=Decimal("100000"),
                stop_loss=Decimal("100876.53"),
                take_profit=Decimal("98246.57"),
            )
        )
    finally:
        asyncio.run(client.disconnect())

    assert buy.quantity == Decimal("0.001")
    assert buy.stop_loss == Decimal("99123.40")
    assert buy.take_profit == Decimal("101753.50")
    assert sell.stop_loss == Decimal("100876.60")
    assert sell.take_profit == Decimal("98246.50")


def test_place_order_posts_demo_market_order_with_full_tpsl() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api-demo.bybit.com"
        assert request.url.path == "/v5/order/create"
        assert request.method == "POST"
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {"orderId": "demo-order-1", "orderLinkId": "sig-123"},
            },
        )

    client = BybitDemoClient(settings(), transport=httpx.MockTransport(handler))
    try:
        result = asyncio.run(
            client.place_order(
                symbol="BTCUSDT",
                side="Buy",
                quantity=Decimal("0.001"),
                stop_loss=Decimal("99000.1"),
                take_profit=Decimal("102000.2"),
                order_link_id="sig-123",
            )
        )
    finally:
        asyncio.run(client.disconnect())

    body = captured["body"]
    assert isinstance(body, dict)
    assert body["category"] == "linear"
    assert body["orderType"] == "Market"
    assert body["reduceOnly"] is False
    assert body["stopLoss"] == "99000.1"
    assert body["takeProfit"] == "102000.2"
    assert body["tpslMode"] == "Full"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers.get("x-bapi-api-key") == "fake-key"
    assert headers.get("x-bapi-sign")
    assert result.order_id == "demo-order-1"


def test_close_position_uses_reduce_only_opposite_market_order() -> None:
    requests: list[tuple[str, dict[str, object] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode()) if request.content else None
        requests.append((request.url.path, body))
        if request.url.path == "/v5/position/list":
            return httpx.Response(
                200,
                json={
                    "retCode": 0,
                    "result": {
                        "list": [
                            {"symbol": "BTCUSDT", "side": "Buy", "size": "0.02"}
                        ]
                    },
                },
            )
        if request.url.path == "/v5/order/create":
            return httpx.Response(
                200,
                json={"retCode": 0, "result": {"orderId": "close-1"}},
            )
        raise AssertionError(request.url.path)

    client = BybitDemoClient(settings(), transport=httpx.MockTransport(handler))
    try:
        result = asyncio.run(client.close_position("BTCUSDT"))
    finally:
        asyncio.run(client.disconnect())

    order_body = next(body for path, body in requests if path == "/v5/order/create")
    assert order_body is not None
    assert order_body["side"] == "Sell"
    assert order_body["qty"] == "0.02"
    assert order_body["reduceOnly"] is True
    assert "stopLoss" not in order_body
    assert result.order_id == "close-1"


class FakeExecutionExchange:
    def __init__(self) -> None:
        self.leverage_calls: list[tuple[str, Decimal]] = []
        self.order_calls: list[dict[str, object]] = []

    async def normalize_order_values(self, **kwargs: object) -> NormalizedOrderValues:
        return NormalizedOrderValues(
            quantity=Decimal("0.01"),
            stop_loss=Decimal("99"),
            take_profit=Decimal("102"),
        )

    async def set_leverage(self, symbol: str, leverage: Decimal) -> None:
        self.leverage_calls.append((symbol, leverage))

    async def place_order(self, **kwargs: object) -> OrderAcknowledgement:
        self.order_calls.append(kwargs)
        return OrderAcknowledgement(order_id="order-42", order_link_id=str(kwargs["order_link_id"]))


def ready_decision() -> RiskDecision:
    return RiskDecision(
        status=RiskDecisionStatus.READY,
        signal_id="abc123",
        symbol="BTCUSDT",
        side=SignalSide.BUY,
        evaluated_at=datetime.now(timezone.utc),
        entry=Decimal("100"),
        quantity=Decimal("0.0109"),
        stop_loss=Decimal("99"),
        take_profit=Decimal("102"),
        risk_reward_ratio=Decimal("2"),
        leverage=Decimal("3"),
        account_equity=Decimal("1000"),
        available_balance=Decimal("1000"),
        risk_amount=Decimal("10"),
    )


def test_execution_service_submits_only_ready_decision(tmp_path) -> None:
    exchange = FakeExecutionExchange()
    db = PersistenceDatabase(str(tmp_path / "execution.sqlite3"))
    service = ExecutionService(exchange, db)  # type: ignore[arg-type]
    result = asyncio.run(service.execute(ready_decision()))

    assert result.status.value == "ACKNOWLEDGED"
    assert result.order_id == "order-42"
    assert exchange.leverage_calls == [("BTCUSDT", Decimal("3"))]
    assert exchange.order_calls[0]["side"] == "Buy"
    assert exchange.order_calls[0]["quantity"] == Decimal("0.01")

from types import SimpleNamespace

from app.bot.runtime import BotRuntime
from app.bot.state import BotState
from app.models.execution import ExecutionResult, ExecutionStatus
from app.models.risk import RiskDecision
from app.models.signal import StrategyName, StrategySignal


class FakeStrategyWithSignal:
    def __init__(self, signal: StrategySignal) -> None:
        self.signal = signal

    async def evaluate(self, symbol: str):
        return SimpleNamespace(
            evaluation_time=datetime.now(timezone.utc),
            signal=self.signal,
            reason_codes=(),
        )


class FakeRiskReady:
    def __init__(self, decision: RiskDecision) -> None:
        self.decision = decision
        self.calls = 0

    async def evaluate(self, signal: StrategySignal) -> RiskDecision:
        self.calls += 1
        return self.decision


class FakeExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, decision: RiskDecision) -> ExecutionResult:
        self.calls += 1
        return ExecutionResult(
            status=ExecutionStatus.SUBMITTED,
            signal_id=decision.signal_id,
            symbol=decision.symbol,
            side=decision.side,
            submitted_at=datetime.now(timezone.utc),
            order_id="runtime-order",
            quantity=decision.quantity,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
            leverage=decision.leverage,
        )


def runtime_signal() -> StrategySignal:
    return StrategySignal(
        signal_id="runtime-signal-1",
        symbol="BTCUSDT",
        strategy=StrategyName.EMA_RSI_ADX_MOMENTUM,
        side=SignalSide.BUY,
        entry_timeframe="5m",
        trend_timeframe="15m",
        signal_time=datetime.now(timezone.utc),
        reference_entry_price=Decimal("100"),
        ema_fast=Decimal("101"),
        ema_slow=Decimal("99"),
        rsi=Decimal("60"),
        adx=Decimal("30"),
        volume=Decimal("120"),
        average_volume=Decimal("100"),
        higher_tf_ema_fast=Decimal("102"),
        higher_tf_ema_slow=Decimal("98"),
        higher_tf_ema_fast_previous=Decimal("101"),
        crossover_age_candles=0,
        confidence=90,
    )


def test_runtime_executes_ready_signal_once_per_runtime_session() -> None:
    async def scenario() -> None:
        signal = runtime_signal()
        decision = ready_decision().model_copy(update={"signal_id": signal.signal_id})
        risk = FakeRiskReady(decision)
        executor = FakeExecutor()
        runtime = BotRuntime(
            FakeStrategyWithSignal(signal),
            risk_service=risk,  # type: ignore[arg-type]
            execution_service=executor,  # type: ignore[arg-type]
            state=BotState(),
            symbols=("BTCUSDT",),
            poll_interval_seconds=0.01,
        )
        await runtime.start()
        await asyncio.sleep(0.035)
        snap = runtime.snapshot()
        await runtime.stop()

        assert risk.calls >= 1
        assert executor.calls == 1
        assert snap["execution_enabled"] is True
        assert snap["submitted_signal_count"] == 1
        assert snap["latest_results"]["BTCUSDT"]["execution"] is None or snap["latest_results"]["BTCUSDT"]["execution"]["status"] == "SUBMITTED"

    asyncio.run(scenario())


class PersistAwareExecutionExchange(FakeExecutionExchange):
    def __init__(self, db: PersistenceDatabase) -> None:
        super().__init__()
        self.db = db
        self.persisted_before_post = False

    async def place_order(self, **kwargs: object) -> OrderAcknowledgement:
        row = self.db.get_execution("abc123")
        self.persisted_before_post = (
            row is not None
            and row.status is ExecutionStatus.SUBMITTED
            and row.order_link_id == kwargs["order_link_id"]
            and row.execution_intent_id is not None
            and row.request_hash is not None
        )
        return await super().place_order(**kwargs)


class AmbiguousExecutionExchange(FakeExecutionExchange):
    async def place_order(self, **kwargs: object) -> OrderAcknowledgement:
        self.order_calls.append(kwargs)
        raise BybitConnectionError("timeout after request send")


class RecoveryExchange(FakeExecutionExchange):
    def __init__(self, row: dict[str, object] | None) -> None:
        super().__init__()
        self.row = row
        self.lookup_calls: list[tuple[str, str]] = []

    async def get_order_by_link_id(
        self, *, symbol: str, order_link_id: str
    ) -> dict[str, object] | None:
        self.lookup_calls.append((symbol, order_link_id))
        return self.row


def test_execution_intent_is_durable_before_bybit_post(tmp_path) -> None:
    db = PersistenceDatabase(str(tmp_path / "bot.sqlite3"))
    exchange = PersistAwareExecutionExchange(db)
    service = ExecutionService(exchange, db)  # type: ignore[arg-type]

    result = asyncio.run(service.execute(ready_decision()))

    assert exchange.persisted_before_post is True
    assert result.status is ExecutionStatus.ACKNOWLEDGED
    stored = db.get_execution("abc123")
    assert stored is not None
    assert stored.status is ExecutionStatus.ACKNOWLEDGED
    assert stored.execution_intent_id == result.execution_intent_id
    assert stored.order_link_id == result.order_link_id
    assert stored.request_hash == result.request_hash


def test_execute_is_idempotent_for_existing_durable_intent(tmp_path) -> None:
    db = PersistenceDatabase(str(tmp_path / "bot.sqlite3"))
    exchange = FakeExecutionExchange()
    service = ExecutionService(exchange, db)  # type: ignore[arg-type]

    first = asyncio.run(service.execute(ready_decision()))
    second = asyncio.run(service.execute(ready_decision()))

    assert first.status is ExecutionStatus.ACKNOWLEDGED
    assert second.status is ExecutionStatus.ACKNOWLEDGED
    assert first.execution_intent_id == second.execution_intent_id
    assert first.order_link_id == second.order_link_id
    assert len(exchange.order_calls) == 1


def test_ambiguous_submit_is_persisted_and_never_blind_retried(tmp_path) -> None:
    db = PersistenceDatabase(str(tmp_path / "bot.sqlite3"))
    exchange = AmbiguousExecutionExchange()
    service = ExecutionService(exchange, db)  # type: ignore[arg-type]

    first = asyncio.run(service.execute(ready_decision()))
    second = asyncio.run(service.execute(ready_decision()))

    assert first.status is ExecutionStatus.UNKNOWN_RECONCILING
    assert second.status is ExecutionStatus.UNKNOWN_RECONCILING
    assert len(exchange.order_calls) == 1
    assert db.submitted_signal_ids() == {"abc123"}


def test_restart_recovery_resolves_filled_order_by_order_link_id(tmp_path) -> None:
    path = str(tmp_path / "bot.sqlite3")
    db = PersistenceDatabase(path)
    initial_exchange = AmbiguousExecutionExchange()
    initial_service = ExecutionService(initial_exchange, db)  # type: ignore[arg-type]
    ambiguous = asyncio.run(initial_service.execute(ready_decision()))
    assert ambiguous.status is ExecutionStatus.UNKNOWN_RECONCILING

    reopened = PersistenceDatabase(path)
    recovery_exchange = RecoveryExchange(
        {
            "orderId": "order-recovered",
            "orderLinkId": ambiguous.order_link_id,
            "orderStatus": "Filled",
            "cumExecQty": "0.01",
            "avgPrice": "100.5",
        }
    )
    recovery_service = ExecutionService(recovery_exchange, reopened)  # type: ignore[arg-type]

    recovered = asyncio.run(recovery_service.recover_unresolved())

    assert len(recovered) == 1
    assert recovered[0].status is ExecutionStatus.FILLED
    assert recovered[0].order_id == "order-recovered"
    assert recovered[0].cumulative_filled_quantity == Decimal("0.01")
    assert recovered[0].average_fill_price == Decimal("100.5")
    assert len(recovery_exchange.lookup_calls) == 1
    assert recovery_exchange.order_calls == []
    stored = reopened.get_execution("abc123")
    assert stored is not None
    assert stored.status is ExecutionStatus.FILLED


def test_restart_recovery_keeps_missing_exchange_order_unknown(tmp_path) -> None:
    path = str(tmp_path / "bot.sqlite3")
    db = PersistenceDatabase(path)
    initial_service = ExecutionService(AmbiguousExecutionExchange(), db)  # type: ignore[arg-type]
    asyncio.run(initial_service.execute(ready_decision()))

    reopened = PersistenceDatabase(path)
    recovery_exchange = RecoveryExchange(None)
    recovery_service = ExecutionService(recovery_exchange, reopened)  # type: ignore[arg-type]

    recovered = asyncio.run(recovery_service.recover_unresolved())

    assert recovered[0].status is ExecutionStatus.UNKNOWN_RECONCILING
    assert recovery_exchange.order_calls == []



def test_get_order_by_link_id_falls_back_to_history() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        assert request.url.params.get("orderLinkId") == "bot-link-1"
        if request.url.path == "/v5/order/realtime":
            return httpx.Response(
                200,
                json={"retCode": 0, "retMsg": "OK", "result": {"list": []}},
            )
        if request.url.path == "/v5/order/history":
            return httpx.Response(
                200,
                json={
                    "retCode": 0,
                    "retMsg": "OK",
                    "result": {
                        "list": [
                            {
                                "orderId": "order-history-1",
                                "orderLinkId": "bot-link-1",
                                "orderStatus": "Filled",
                                "cumExecQty": "0.01",
                                "avgPrice": "100.5",
                            }
                        ]
                    },
                },
            )
        raise AssertionError(request.url.path)

    client = BybitDemoClient(settings(), transport=httpx.MockTransport(handler))
    try:
        row = asyncio.run(
            client.get_order_by_link_id(
                symbol="BTCUSDT",
                order_link_id="bot-link-1",
            )
        )
    finally:
        asyncio.run(client.disconnect())

    assert row is not None
    assert row["orderId"] == "order-history-1"
    assert seen == ["/v5/order/realtime", "/v5/order/history"]


def test_execution_without_persistence_fails_closed_before_exchange_side_effects() -> None:
    exchange = FakeExecutionExchange()
    service = ExecutionService(exchange)  # type: ignore[arg-type]

    result = asyncio.run(service.execute(ready_decision()))

    assert result.status is ExecutionStatus.FAILED
    assert "Persistence is required" in (result.message or "")
    assert exchange.leverage_calls == []
    assert exchange.order_calls == []


def test_execution_blocks_when_persistence_write_probe_fails() -> None:
    class BrokenPersistence:
        def writable_health(self):
            raise RuntimeError("database is locked")

    exchange = FakeExecutionExchange()
    service = ExecutionService(exchange, BrokenPersistence())  # type: ignore[arg-type]

    result = asyncio.run(service.execute(ready_decision()))

    assert result.status is ExecutionStatus.FAILED
    assert "not writable" in (result.message or "")
    assert "database is locked" in (result.message or "")
    assert exchange.leverage_calls == []
    assert exchange.order_calls == []
