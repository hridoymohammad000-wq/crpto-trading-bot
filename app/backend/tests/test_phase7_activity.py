import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from fastapi.testclient import TestClient

from app.activity import ActivityService
from app.core.config import Settings
from app.exchange.bybit import BybitDemoClient
from app.main import app
from app.models.activity import ClosedTradeResponse
from app.models.signal import StrategyName, StrategySignal, SignalSide
from app.repositories import ActivityRepository


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        BYBIT_API_KEY="fake-key",
        BYBIT_API_SECRET="fake-secret",
        BYBIT_DEMO=True,
    )


def _signal(signal_id: str = "sig-1") -> StrategySignal:
    return StrategySignal(
        signal_id=signal_id,
        symbol="BTCUSDT",
        strategy=StrategyName.EMA_RSI_ADX_MOMENTUM,
        side=SignalSide.BUY,
        entry_timeframe="5m",
        trend_timeframe="15m",
        signal_time=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
        reference_entry_price=Decimal("100000"),
        ema_fast=Decimal("100100"),
        ema_slow=Decimal("99900"),
        rsi=Decimal("60"),
        adx=Decimal("25"),
        volume=Decimal("120"),
        average_volume=Decimal("100"),
        higher_tf_ema_fast=Decimal("100050"),
        higher_tf_ema_slow=Decimal("99850"),
        higher_tf_ema_fast_previous=Decimal("100000"),
        crossover_age_candles=0,
        confidence=80,
    )


def test_activity_repository_returns_newest_signal_first() -> None:
    repo = ActivityRepository()
    repo.record_signal(_signal("sig-1"))
    repo.record_signal(_signal("sig-2"))
    rows = repo.list_signals(limit=10)
    assert [row.signal_id for row in rows] == ["sig-2", "sig-1"]


def test_activity_repository_updates_existing_signal_instead_of_duplicate() -> None:
    repo = ActivityRepository()
    repo.record_signal(_signal("sig-1"))
    repo.record_signal(_signal("sig-1"))
    assert len(repo.list_signals(limit=10)) == 1


def test_bybit_closed_trade_history_is_parsed_from_demo_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v5/position/closed-pnl"
        assert request.url.params["category"] == "linear"
        assert request.url.params["settleCoin"] == "USDT"
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "result": {
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "side": "Buy",
                            "qty": "0.01",
                            "avgEntryPrice": "100000",
                            "avgExitPrice": "102000",
                            "closedPnl": "20",
                            "openFee": "-0.5",
                            "closeFee": "-0.5",
                            "orderId": "close-1",
                            "createdTime": "1789560000000",
                            "updatedTime": "1789563600000",
                        }
                    ]
                },
            },
        )

    client = BybitDemoClient(_settings(), transport=httpx.MockTransport(handler))
    try:
        rows = asyncio.run(client.get_closed_trades(limit=25))
    finally:
        asyncio.run(client.disconnect())

    assert len(rows) == 1
    assert rows[0].side == "SHORT"
    assert rows[0].realized_pnl == Decimal("20")
    assert rows[0].quantity == Decimal("0.01")


class StubActivityService:
    def list_signals(self, *, limit: int = 100):
        repo = ActivityRepository()
        repo.record_signal(_signal())
        return repo.list_signals(limit=limit)

    async def list_trades(self, *, limit: int = 100):
        return [
            ClosedTradeResponse(
                symbol="BTCUSDT",
                side="LONG",
                quantity=Decimal("0.01"),
                entry_price=Decimal("100000"),
                exit_price=Decimal("102000"),
                realized_pnl=Decimal("20"),
            )
        ][:limit]

    async def get_trade_stats(self, *, limit: int = 100):
        class ExchangeStub:
            async def get_closed_trades(self, limit: int = 100):
                return ()
        service = ActivityService(ExchangeStub(), ActivityRepository())  # type: ignore[arg-type]
        trades = await self.list_trades(limit=limit)
        # Exercise the real stat math with a purpose-built exchange shape.
        class TradeExchange:
            async def get_closed_trades(self, limit: int = 100):
                from app.exchange.bybit import ClosedTrade
                return tuple(
                    ClosedTrade(
                        symbol=t.symbol,
                        side=t.side,
                        quantity=t.quantity,
                        entry_price=t.entry_price,
                        exit_price=t.exit_price,
                        realized_pnl=t.realized_pnl,
                        open_fee=t.open_fee,
                        close_fee=t.close_fee,
                        order_id=t.order_id,
                        created_at=t.created_at,
                        updated_at=t.updated_at,
                    )
                    for t in trades
                )
        return await ActivityService(TradeExchange(), ActivityRepository()).get_trade_stats(limit=limit)  # type: ignore[arg-type]


def test_phase7_signal_trade_and_stats_endpoints_exist() -> None:
    original = app.state.activity_service
    app.state.activity_service = StubActivityService()
    try:
        with TestClient(app) as client:
            signals = client.get("/signals")
            trades = client.get("/trades")
            stats = client.get("/trades/stats")
    finally:
        app.state.activity_service = original

    assert signals.status_code == 200
    assert signals.json()[0]["signal_id"] == "sig-1"
    assert trades.status_code == 200
    assert trades.json()[0]["realized_pnl"] == "20"
    assert stats.status_code == 200
    assert stats.json()["total_trades"] == 1
    assert stats.json()["win_rate_pct"] == "100"


def test_sync_closed_trades_upserts_and_is_idempotent(tmp_path) -> None:
    from app.persistence import PersistenceDatabase
    from app.exchange.bybit import ClosedTrade

    class ExchangeStub:
        async def get_closed_trades(self, limit: int = 100):
            return (
                ClosedTrade(
                    symbol="TAOUSDT",
                    side="LONG",
                    quantity=Decimal("2.079"),
                    entry_price=Decimal("285.59"),
                    exit_price=Decimal("282.18"),
                    realized_pnl=Decimal("-7.74"),
                    open_fee=Decimal("-0.3266"),
                    close_fee=Decimal("-0.3227"),
                    order_id="tao-close-1",
                    created_at=datetime(2026, 9, 21, 14, 3, 26, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 9, 21, 14, 6, 2, tzinfo=timezone.utc),
                ),
            )[:limit]

    db = PersistenceDatabase(str(tmp_path / "activity.sqlite3"))
    db.initialize()
    service = ActivityService(ExchangeStub(), ActivityRepository(persistence=db), db)  # type: ignore[arg-type]

    first = asyncio.run(service.sync_closed_trades())
    second = asyncio.run(service.sync_closed_trades())

    assert first == 1
    assert second == 1
    rows = db.list_closed_trades(limit=10)
    assert len(rows) == 1
    assert rows[0].symbol == "TAOUSDT"
    assert rows[0].order_id == "tao-close-1"
