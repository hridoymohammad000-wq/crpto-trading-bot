import asyncio
from decimal import Decimal

import httpx
from fastapi.testclient import TestClient

from app.api.routes.market import get_market_data_service
from app.core.config import Settings
from app.exchange.bybit.client import BybitDemoClient, MarketTicker
from app.main import app
from app.market_data import MarketDataService


def configured_settings() -> Settings:
    return Settings(BYBIT_DEMO=True, BYBIT_API_KEY="demo-key", BYBIT_API_SECRET="demo-secret")


def test_one_minute_candles_supported() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v5/market/kline"
        assert request.url.params["interval"] == "1"
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "time": 1704067320000,
                "result": {
                    "category": "linear",
                    "symbol": "SOLUSDT",
                    "list": [["1704067200000", "100", "101", "99", "100.5", "12", "1206"]],
                },
            },
        )

    client = BybitDemoClient(configured_settings(), transport=httpx.MockTransport(handler))
    candles = asyncio.run(client.get_candles("SOLUSDT", "1m", 1))
    asyncio.run(client.disconnect())
    assert candles[0].timeframe == "1m"
    assert candles[0].is_closed is True


def test_real_ticker_normalization() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v5/market/tickers"
        assert dict(request.url.params) == {"category": "linear", "symbol": "BTCUSDT"}
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "result": {
                    "category": "linear",
                    "list": [{
                        "symbol": "BTCUSDT",
                        "lastPrice": "60000.5",
                        "highPrice24h": "61000",
                        "lowPrice24h": "59000",
                        "volume24h": "1234.5",
                        "turnover24h": "74000000",
                        "prevPrice24h": "59500",
                        "price24hPcnt": "0.00841176",
                        "bid1Price": "60000.0",
                        "ask1Price": "60001.0",
                    }],
                },
            },
        )

    client = BybitDemoClient(configured_settings(), transport=httpx.MockTransport(handler))
    ticker = asyncio.run(client.get_ticker("BTCUSDT"))
    asyncio.run(client.disconnect())
    assert ticker.last_price == Decimal("60000.5")
    assert ticker.high_price_24h == Decimal("61000")
    assert ticker.price_change_24h_pct == Decimal("0.00841176")


class FakeTickerExchange:
    async def get_candles(self, symbol: str, timeframe: str, limit: int = 200):
        return ()

    async def get_ticker(self, symbol: str) -> MarketTicker:
        return MarketTicker(
            symbol=symbol,
            last_price=Decimal("150.25"),
            high_price_24h=Decimal("155"),
            low_price_24h=Decimal("145"),
            volume_24h=Decimal("1000"),
            turnover_24h=Decimal("150000"),
            prev_price_24h=Decimal("149"),
            price_change_24h_pct=Decimal("0.00838926"),
            bid_price=Decimal("150.20"),
            ask_price=Decimal("150.30"),
        )


def test_ticker_endpoint_returns_24h_market_data() -> None:
    service = MarketDataService(FakeTickerExchange())
    app.dependency_overrides[get_market_data_service] = lambda: service
    try:
        response = TestClient(app).get("/market/ticker", params={"symbol": "SOLUSDT"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "SOLUSDT"
    assert body["last_price"] == "150.25"
    assert body["high_price_24h"] == "155"
    assert body["low_price_24h"] == "145"
    assert body["volume_24h"] == "1000"


def test_candle_endpoint_accepts_one_minute() -> None:
    service = MarketDataService(FakeTickerExchange())
    app.dependency_overrides[get_market_data_service] = lambda: service
    try:
        response = TestClient(app).get(
            "/market/candles", params={"symbol": "BTCUSDT", "timeframe": "1m", "limit": 1}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
