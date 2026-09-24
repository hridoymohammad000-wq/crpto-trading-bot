from decimal import Decimal

from fastapi.testclient import TestClient

from app.exchange.bybit import AccountBalance, CoinBalance, Position
from app.exchange.bybit.exceptions import BybitAuthenticationError
from app.main import app


class StubAccountService:
    async def get_summary(self):
        from app.models.account import AccountSummaryResponse, CoinBalanceResponse

        return AccountSummaryResponse(
            balance=Decimal("10000.00"),
            equity=Decimal("10145.30"),
            margin_balance=Decimal("10145.30"),
            available_margin=Decimal("8850.00"),
            available_balance=Decimal("8850.00"),
            initial_margin=Decimal("1000.00"),
            maintenance_margin=Decimal("500.00"),
            unrealized_pnl=Decimal("145.30"),
            account_type="UNIFIED",
            unified_margin_status=5,
            margin_mode="REGULAR_MARGIN",
            available_trading_capacity=Decimal("8850.00"),
            capacity_source="TOTAL_AVAILABLE_BALANCE",
            coins=[
                CoinBalanceResponse(
                    coin="USDT",
                    equity=Decimal("10145.30"),
                    wallet_balance=Decimal("10000.00"),
                    total_order_im=Decimal("0"),
                    total_position_im=Decimal("1150.00"),
                )
            ],
        )

    async def get_positions(self):
        from app.models.account import PositionResponse

        return [
            PositionResponse(
                symbol="BTCUSDT",
                side="LONG",
                size=Decimal("0.02"),
                entry_price=Decimal("108000"),
                mark_price=Decimal("108520.40"),
                position_value=Decimal("2170.408"),
                leverage=Decimal("5"),
                unrealized_pnl=Decimal("10.408"),
                stop_loss=Decimal("107500"),
                take_profit=Decimal("109500"),
                liquidation_price=Decimal("90000"),
            )
        ]


class AuthFailAccountService:
    async def get_summary(self):
        raise BybitAuthenticationError("missing")

    async def get_positions(self):
        raise BybitAuthenticationError("missing")


def test_account_endpoint_returns_real_data_shape() -> None:
    original = app.state.account_service
    app.state.account_service = StubAccountService()
    try:
        with TestClient(app) as client:
            response = client.get("/account")
    finally:
        app.state.account_service = original

    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"] == "demo"
    assert payload["balance"] == "10000.00"
    assert payload["equity"] == "10145.30"
    assert payload["margin_balance"] == "10145.30"
    assert payload["available_margin"] == "8850.00"
    assert payload["available_balance"] == "8850.00"
    assert payload["initial_margin"] == "1000.00"
    assert payload["maintenance_margin"] == "500.00"
    assert payload["unrealized_pnl"] == "145.30"
    assert payload["account_type"] == "UNIFIED"
    assert payload["unified_margin_status"] == 5
    assert payload["margin_mode"] == "REGULAR_MARGIN"
    assert payload["available_trading_capacity"] == "8850.00"
    assert payload["capacity_source"] == "TOTAL_AVAILABLE_BALANCE"
    assert payload["coins"][0]["coin"] == "USDT"
    assert payload["coins"][0]["total_order_im"] == "0"
    assert payload["coins"][0]["total_position_im"] == "1150.00"


def test_positions_endpoint_returns_open_positions_shape() -> None:
    original = app.state.account_service
    app.state.account_service = StubAccountService()
    try:
        with TestClient(app) as client:
            response = client.get("/positions")
    finally:
        app.state.account_service = original

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["symbol"] == "BTCUSDT"
    assert payload[0]["side"] == "LONG"
    assert payload[0]["size"] == "0.02"
    assert payload[0]["unrealized_pnl"] == "10.408"


def test_private_account_endpoint_is_fail_closed_without_credentials() -> None:
    original = app.state.account_service
    app.state.account_service = AuthFailAccountService()
    try:
        with TestClient(app) as client:
            response = client.get("/account")
    finally:
        app.state.account_service = original

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Bybit Demo API credentials are not configured"
    }
