import asyncio
import hashlib
import hmac
import socket
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings
from app.exchange.bybit import BYBIT_DEMO_REST_URL, BybitDemoClient
from app.exchange.bybit.exceptions import (
    BybitAPIError,
    BybitAuthenticationError,
    BybitConnectionError,
)
from app.models.candle import Candle


@pytest.fixture
def default_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.delenv("BYBIT_API_KEY", raising=False)
    monkeypatch.delenv("BYBIT_API_SECRET", raising=False)
    monkeypatch.delenv("BYBIT_DEMO", raising=False)
    return Settings(_env_file=None)


@pytest.fixture
def configured_settings() -> Settings:
    return Settings(
        _env_file=None,
        BYBIT_API_KEY="fake-key",
        BYBIT_API_SECRET="fake-secret",
        BYBIT_DEMO=True,
    )


async def call_and_disconnect(
    client: BybitDemoClient,
    method_name: str,
) -> object:
    try:
        return await getattr(client, method_name)()
    finally:
        await client.disconnect()


def test_bybit_demo_defaults_to_true(default_settings: Settings) -> None:
    assert default_settings.BYBIT_DEMO is True


def test_empty_api_credentials_are_allowed(default_settings: Settings) -> None:
    assert default_settings.BYBIT_API_KEY == ""
    assert default_settings.BYBIT_API_SECRET == ""


def test_client_initializes_without_network_call(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
) -> None:
    def fail_on_network_call(*args: object, **kwargs: object) -> None:
        raise AssertionError("Initialization attempted a network call")

    monkeypatch.setattr(socket, "create_connection", fail_on_network_call)

    BybitDemoClient(default_settings)


def test_client_uses_demo_rest_url(default_settings: Settings) -> None:
    client = BybitDemoClient(default_settings)

    assert client.base_url == "https://api-demo.bybit.com"
    assert client.base_url == BYBIT_DEMO_REST_URL


def test_client_configuration_has_no_testnet_url(default_settings: Settings) -> None:
    client = BybitDemoClient(default_settings)

    assert "testnet" not in client.base_url


def test_get_server_time_success(configured_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v5/market/time"
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {
                    "timeSecond": "1688639403",
                    "timeNano": "1688639403423213947",
                },
            },
        )

    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(call_and_disconnect(client, "get_server_time"))

    assert result == 1688639403


def test_get_wallet_balance_success(configured_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v5/account/wallet-balance"
        assert request.url.params["accountType"] == "UNIFIED"
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {
                    "list": [
                        {
                            "totalEquity": "1250.75",
                            "totalWalletBalance": "1200.50",
                            "totalMarginBalance": "1250.75",
                            "totalAvailableBalance": "950.25",
                            "totalInitialMargin": "150.00",
                            "totalMaintenanceMargin": "75.00",
                            "totalPerpUPL": "50.25",
                            "coin": [
                                {
                                    "coin": "USDT",
                                    "equity": "1000.25",
                                    "walletBalance": "975.00",
                                }
                            ],
                        }
                    ]
                },
            },
        )

    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(call_and_disconnect(client, "get_account_balance"))

    assert result.total_equity == Decimal("1250.75")
    assert result.total_wallet_balance == Decimal("1200.50")
    assert result.total_margin_balance == Decimal("1250.75")
    assert result.total_available_balance == Decimal("950.25")
    assert result.total_initial_margin == Decimal("150.00")
    assert result.total_maintenance_margin == Decimal("75.00")
    assert result.total_perp_upl == Decimal("50.25")
    assert result.coins[0].coin == "USDT"
    assert result.coins[0].equity == Decimal("1000.25")
    assert result.coins[0].wallet_balance == Decimal("975.00")



def test_wallet_balance_does_not_fallback_when_available_margin_missing(
    configured_settings: Settings,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v5/account/wallet-balance"
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {
                    "list": [
                        {
                            "totalEquity": "1000",
                            "totalWalletBalance": "1000",
                            "totalMarginBalance": "1000",
                            "totalPerpUPL": "0",
                            "coin": [],
                        }
                    ]
                },
            },
        )

    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(call_and_disconnect(client, "get_account_balance"))
    assert result.total_wallet_balance == Decimal("1000")
    assert result.total_available_balance is None


def test_get_account_info_success(configured_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v5/account/info"
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {
                    "unifiedMarginStatus": 5,
                    "marginMode": "REGULAR_MARGIN",
                },
            },
        )

    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(call_and_disconnect(client, "get_account_info"))
    assert result.unified_margin_status == 5
    assert result.margin_mode == "REGULAR_MARGIN"

def test_missing_credentials_rejected_for_private_request(
    default_settings: Settings,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("A private request was sent without credentials")

    client = BybitDemoClient(
        default_settings,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BybitAuthenticationError):
        asyncio.run(call_and_disconnect(client, "get_account_balance"))


def test_authentication_headers_are_constructed(
    configured_settings: Settings,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        timestamp = request.headers["X-BAPI-TIMESTAMP"]
        signature_payload = f"{timestamp}fake-key5000accountType=UNIFIED"
        expected_signature = hmac.new(
            b"fake-secret",
            signature_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        assert request.headers["X-BAPI-API-KEY"] == "fake-key"
        assert request.headers["X-BAPI-RECV-WINDOW"] == "5000"
        assert request.headers["X-BAPI-SIGN"] == expected_signature
        assert "fake-secret" not in request.headers.values()

        return httpx.Response(
            200,
            json={"retCode": 0, "result": {"list": [{}]}},
        )

    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(handler),
    )

    asyncio.run(call_and_disconnect(client, "get_account_balance"))


def test_nonzero_ret_code_raises_api_error(
    configured_settings: Settings,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"retCode": 10001, "retMsg": "Invalid request", "result": {}},
        )
    )
    client = BybitDemoClient(configured_settings, transport=transport)

    with pytest.raises(BybitAPIError, match="10001"):
        asyncio.run(call_and_disconnect(client, "get_server_time"))


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
def test_connection_errors_are_normalized(
    error_type: type[httpx.RequestError],
    configured_settings: Settings,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error_type("simulated failure", request=request)

    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BybitConnectionError):
        asyncio.run(call_and_disconnect(client, "get_server_time"))


def test_non_success_http_status_raises_api_error(
    configured_settings: Settings,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, text="unavailable")
    )
    client = BybitDemoClient(configured_settings, transport=transport)

    with pytest.raises(BybitAPIError, match="503"):
        asyncio.run(call_and_disconnect(client, "get_server_time"))


def test_malformed_response_raises_api_error(
    configured_settings: Settings,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"retCode": 0, "result": {}})
    )
    client = BybitDemoClient(configured_settings, transport=transport)

    with pytest.raises(BybitAPIError, match="malformed"):
        asyncio.run(call_and_disconnect(client, "get_server_time"))


def test_get_btcusdt_five_minute_candles(
    configured_settings: Settings,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v5/market/kline"
        assert dict(request.url.params) == {
            "category": "linear",
            "symbol": "BTCUSDT",
            "interval": "5",
            "limit": "2",
        }
        assert "X-BAPI-API-KEY" not in request.headers
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "time": 1704067920000,
                "result": {
                    "category": "linear",
                    "symbol": "BTCUSDT",
                    "list": [
                        [
                            "1704067800000",
                            "43010.1",
                            "43020.2",
                            "43000.0",
                            "43015.5",
                            "4.25",
                            "182801.50",
                        ],
                        [
                            "1704067500000",
                            "43000.1",
                            "43015.5",
                            "42990.0",
                            "43010.1",
                            "3.50",
                            "150520.25",
                        ],
                    ],
                },
            },
        )

    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(handler),
    )
    candles = asyncio.run(client.get_candles("BTCUSDT", "5m", 2))
    asyncio.run(client.disconnect())

    assert all(isinstance(candle, Candle) for candle in candles)
    assert candles[0].start_time < candles[1].start_time
    assert candles[0].open == Decimal("43000.1")
    assert candles[0].volume == Decimal("3.50")
    assert candles[0].is_closed is True
    assert candles[1].is_closed is False


def test_get_ethusdt_fifteen_minute_candles(
    configured_settings: Settings,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "ETHUSDT"
        assert request.url.params["interval"] == "15"
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "time": 1704069600000,
                "result": {
                    "category": "linear",
                    "symbol": "ETHUSDT",
                    "list": [
                        [
                            "1704068100000",
                            "2250.00",
                            "2260.00",
                            "2245.00",
                            "2255.00",
                            "12.5",
                            "28187.5",
                        ]
                    ],
                },
            },
        )

    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(handler),
    )
    candles = asyncio.run(client.get_candles("ETHUSDT", "15m", 1))
    asyncio.run(client.disconnect())

    assert candles[0].symbol == "ETHUSDT"
    assert candles[0].timeframe == "15m"
    assert candles[0].is_closed is True


@pytest.mark.parametrize(
    ("symbol", "timeframe"),
    [("BTCUSD", "5m"), ("BTCUSDT", "30m")],
)
def test_get_candles_rejects_unsupported_market(
    symbol: str,
    timeframe: str,
    default_settings: Settings,
) -> None:
    client = BybitDemoClient(default_settings)

    with pytest.raises(ValueError, match="Unsupported"):
        asyncio.run(client.get_candles(symbol, timeframe))


@pytest.mark.parametrize("limit", [0, 1001])
def test_get_candles_rejects_invalid_limit(
    limit: int,
    default_settings: Settings,
) -> None:
    client = BybitDemoClient(default_settings)

    with pytest.raises(ValueError, match="between 1 and 1000"):
        asyncio.run(client.get_candles("BTCUSDT", "5m", limit))


def test_get_candles_nonzero_ret_code_raises_api_error(
    configured_settings: Settings,
) -> None:
    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"retCode": 10001, "retMsg": "Invalid request"},
            )
        ),
    )

    with pytest.raises(BybitAPIError, match="10001"):
        asyncio.run(client.get_candles("BTCUSDT", "5m"))
    asyncio.run(client.disconnect())


@pytest.mark.parametrize(
    "payload",
    [
        {"retCode": 0, "time": 1704067920000, "result": {}},
        {
            "retCode": 0,
            "time": 1704067920000,
            "result": {
                "category": "linear",
                "symbol": "BTCUSDT",
                "list": [["bad"]],
            },
        },
        {
            "retCode": 0,
            "time": 1704067920000,
            "result": {
                "category": "linear",
                "symbol": "BTCUSDT",
                "list": [
                    [
                        "1704067500000",
                        "not-a-number",
                        "43015",
                        "42990",
                        "43010",
                        "3.5",
                        "150520",
                    ]
                ],
            },
        },
    ],
)
def test_malformed_kline_response_raises_api_error(
    payload: dict[str, object],
    configured_settings: Settings,
) -> None:
    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        ),
    )

    with pytest.raises(BybitAPIError, match="malformed"):
        asyncio.run(client.get_candles("BTCUSDT", "5m"))
    asyncio.run(client.disconnect())


def test_get_positions_success(configured_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v5/position/list"
        assert dict(request.url.params) == {
            "category": "linear",
            "settleCoin": "USDT",
        }
        assert request.headers["X-BAPI-API-KEY"] == "fake-key"
        return httpx.Response(
            200,
            json={
                "retCode": 0,
                "retMsg": "OK",
                "result": {
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "side": "Buy",
                            "size": "0.02",
                            "avgPrice": "108000",
                            "markPrice": "108520.40",
                            "positionValue": "2170.408",
                            "leverage": "5",
                            "unrealisedPnl": "10.408",
                            "stopLoss": "107500",
                            "takeProfit": "109500",
                            "liqPrice": "90000",
                        },
                        {
                            "symbol": "ETHUSDT",
                            "side": "Sell",
                            "size": "1.5",
                            "avgPrice": "4220",
                            "markPrice": "4185",
                            "positionValue": "6277.5",
                            "leverage": "5",
                            "unrealisedPnl": "52.5",
                            "stopLoss": "4255",
                            "takeProfit": "4115",
                            "liqPrice": "5000",
                        },
                        {
                            "symbol": "SOLUSDT",
                            "side": "Buy",
                            "size": "0",
                            "avgPrice": "",
                            "markPrice": "236.2",
                            "positionValue": "0",
                            "leverage": "",
                            "unrealisedPnl": "0",
                            "stopLoss": "",
                            "takeProfit": "",
                            "liqPrice": "",
                        },
                    ]
                },
            },
        )

    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(handler),
    )
    positions = asyncio.run(client.get_positions())
    asyncio.run(client.disconnect())

    assert len(positions) == 2
    assert positions[0].symbol == "BTCUSDT"
    assert positions[0].side == "LONG"
    assert positions[0].size == Decimal("0.02")
    assert positions[0].entry_price == Decimal("108000")
    assert positions[0].unrealized_pnl == Decimal("10.408")
    assert positions[1].side == "SHORT"
    assert positions[1].take_profit == Decimal("4115")


def test_get_positions_missing_credentials_rejected(
    default_settings: Settings,
) -> None:
    client = BybitDemoClient(default_settings)

    with pytest.raises(BybitAuthenticationError):
        asyncio.run(client.get_positions())


@pytest.mark.parametrize(
    "position",
    [
        {"symbol": "BTCUSDT", "side": "", "size": "1"},
        {"symbol": "BTCUSDT", "side": "Buy", "size": "bad"},
    ],
)
def test_get_positions_malformed_response_raises_api_error(
    position: dict[str, str],
    configured_settings: Settings,
) -> None:
    client = BybitDemoClient(
        configured_settings,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "retCode": 0,
                    "result": {"list": [position]},
                },
            )
        ),
    )

    with pytest.raises(BybitAPIError):
        asyncio.run(client.get_positions())
    asyncio.run(client.disconnect())


def test_place_order_requires_private_credentials(default_settings: Settings) -> None:
    client = BybitDemoClient(default_settings)

    with pytest.raises(BybitAuthenticationError):
        asyncio.run(
            client.place_order(
                symbol="BTCUSDT",
                side="Buy",
                quantity=Decimal("0.001"),
                stop_loss=Decimal("90000"),
                take_profit=Decimal("110000"),
            )
        )
def test_parse_closed_trade_mapping() -> None:
    from app.exchange.bybit.client import BybitDemoClient
    from decimal import Decimal
    val_buy = {
        "symbol": "TAOUSDT", "side": "Buy", "qty": "1", "closedPnl": "1",
        "avgEntryPrice": "100", "avgExitPrice": "101", "openFee": "0", "closeFee": "0"
    }
    t_short = BybitDemoClient._parse_closed_trade(val_buy)
    assert t_short.side == "SHORT"
    val_sell = {
        "symbol": "TAOUSDT", "side": "Sell", "qty": "1", "closedPnl": "1",
        "avgEntryPrice": "100", "avgExitPrice": "101", "openFee": "0", "closeFee": "0"
    }
    t_long = BybitDemoClient._parse_closed_trade(val_sell)
    assert t_long.side == "LONG"
