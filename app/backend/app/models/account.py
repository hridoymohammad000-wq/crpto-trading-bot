from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class CoinBalanceResponse(BaseModel):
    coin: str
    equity: Decimal | None = None
    wallet_balance: Decimal | None = None
    total_order_im: Decimal | None = None
    total_position_im: Decimal | None = None


class AccountSummaryResponse(BaseModel):
    environment: Literal["demo"] = "demo"
    balance: Decimal | None = None
    equity: Decimal | None = None
    margin_balance: Decimal | None = None
    available_margin: Decimal | None = None
    # Compatibility alias used by the existing Risk/UI code. It must always
    # carry the same normalized value as available_margin.
    available_balance: Decimal | None = None
    initial_margin: Decimal | None = None
    maintenance_margin: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    account_type: Literal["UNIFIED"] = "UNIFIED"
    unified_margin_status: int | None = None
    margin_mode: str | None = None
    available_trading_capacity: Decimal | None = None
    capacity_source: Literal["TOTAL_AVAILABLE_BALANCE", "ISOLATED_DERIVED", "UNAVAILABLE"] = "UNAVAILABLE"
    coins: list[CoinBalanceResponse]


class PositionResponse(BaseModel):
    symbol: str
    side: Literal["LONG", "SHORT"]
    size: Decimal
    entry_price: Decimal | None = None
    mark_price: Decimal | None = None
    position_value: Decimal | None = None
    leverage: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    liquidation_price: Decimal | None = None
