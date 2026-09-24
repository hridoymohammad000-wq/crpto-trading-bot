import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.routes.market import get_market_data_service
from app.exchange.base import ExchangeClient
from app.main import app
from app.market_data import MarketDataService
from app.models.candle import Candle


class FakeExchangeClient(ExchangeClient):
    def __init__(self, candles: tuple[Candle, ...] = ()) -> None:
        self.candles = candles
        self.requests: list[tuple[str, str, int]] = []

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def get_server_time(self) -> object:
        raise NotImplementedError

    async def get_account_balance(self) -> object:
        raise NotImplementedError

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> tuple[Candle, ...]:
        self.requests.append((symbol, timeframe, limit))
        return self.candles

    async def get_positions(self) -> object:
        raise NotImplementedError

    async def place_order(self) -> object:
        raise NotImplementedError


def make_candle(
    minute: int,
    *,
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
    close: str = "101",
    is_closed: bool = True,
) -> Candle:
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        start_time=datetime(2024, 1, 1, tzinfo=timezone.utc)
        + timedelta(minutes=minute),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal(close),
        volume=Decimal("12.5"),
        turnover=Decimal("1250"),
        is_closed=is_closed,
    )


def test_service_deduplicates_and_updates_unfinished_candle() -> None:
    service = MarketDataService(FakeExchangeClient())
    original = make_candle(0, close="101", is_closed=False)
    updated = make_candle(0, close="105", is_closed=False)

    service.merge([original, original])
    service.merge([updated])

    history = service._history[("BTCUSDT", "5m")]
    assert len(history) == 1
    assert history[0].close == Decimal("105")


def test_service_keeps_bounded_chronological_history() -> None:
    service = MarketDataService(FakeExchangeClient(), max_history=2)

    service.merge([make_candle(10), make_candle(0), make_candle(5)])

    history = service._history[("BTCUSDT", "5m")]
    assert [candle.start_time.minute for candle in history] == [5, 10]


def test_service_exposes_closed_candles_only() -> None:
    candles = (make_candle(0), make_candle(5, is_closed=False))
    service = MarketDataService(FakeExchangeClient(candles))

    result = asyncio.run(
        service.fetch_candles("BTCUSDT", "5m", limit=10, closed_only=True)
    )

    assert result == (candles[0],)
    assert service.latest_closed_candle("BTCUSDT", "5m") == candles[0]
    assert service.recent_closed_candles("BTCUSDT", "5m", limit=10) == (
        candles[0],
    )


def test_diagnostic_endpoint_returns_normalized_candles() -> None:
    candle = make_candle(0)
    exchange = FakeExchangeClient((candle,))
    service = MarketDataService(exchange)
    app.dependency_overrides[get_market_data_service] = lambda: service
    try:
        response = TestClient(app).get(
            "/market/candles",
            params={"symbol": "BTCUSDT", "timeframe": "5m", "limit": 1},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "start_time": "2024-01-01T00:00:00Z",
            "open": "100",
            "high": "110",
            "low": "90",
            "close": "101",
            "volume": "12.5",
            "turnover": "1250",
            "is_closed": True,
        }
    ]
    assert exchange.requests == [("BTCUSDT", "5m", 1)]


def test_diagnostic_endpoint_rejects_unsupported_symbol() -> None:
    response = TestClient(app).get(
        "/market/candles",
        params={"symbol": "BTCUSD", "timeframe": "5m"},
    )

    assert response.status_code == 422


def test_diagnostic_endpoint_rejects_unsupported_timeframe() -> None:
    response = TestClient(app).get(
        "/market/candles",
        params={"symbol": "BTCUSDT", "timeframe": "30m"},
    )

    assert response.status_code == 422
