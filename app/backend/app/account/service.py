from decimal import Decimal
from typing import Literal

from app.exchange.bybit import BybitDemoClient
from app.models.account import (
    AccountSummaryResponse,
    CoinBalanceResponse,
    PositionResponse,
)


class AccountService:
    def __init__(self, exchange_client: BybitDemoClient) -> None:
        self.exchange_client = exchange_client

    async def get_summary(self) -> AccountSummaryResponse:
        balance = await self.exchange_client.get_account_balance()
        account_info = await self.exchange_client.get_account_info()

        capacity_source: Literal["TOTAL_AVAILABLE_BALANCE", "ISOLATED_DERIVED", "UNAVAILABLE"] = "UNAVAILABLE"
        available_trading_capacity: Decimal | None = None

        if account_info.margin_mode == "ISOLATED_MARGIN":
            usdt_coin = next((c for c in balance.coins if c.coin == "USDT"), None)
            if (
                usdt_coin is not None
                and usdt_coin.wallet_balance is not None
                and usdt_coin.total_order_im is not None
                and usdt_coin.total_position_im is not None
            ):
                available_trading_capacity = (
                    usdt_coin.wallet_balance
                    - usdt_coin.total_order_im
                    - usdt_coin.total_position_im
                )
                capacity_source = "ISOLATED_DERIVED"
        elif balance.total_available_balance is not None:
            available_trading_capacity = balance.total_available_balance
            capacity_source = "TOTAL_AVAILABLE_BALANCE"

        return AccountSummaryResponse(
            balance=balance.total_wallet_balance,
            equity=balance.total_equity,
            margin_balance=balance.total_margin_balance,
            available_margin=balance.total_available_balance,
            available_balance=balance.total_available_balance,
            initial_margin=balance.total_initial_margin,
            maintenance_margin=balance.total_maintenance_margin,
            unrealized_pnl=balance.total_perp_upl,
            account_type="UNIFIED",
            unified_margin_status=account_info.unified_margin_status,
            margin_mode=account_info.margin_mode,
            available_trading_capacity=available_trading_capacity,
            capacity_source=capacity_source,
            coins=[
                CoinBalanceResponse(
                    coin=coin.coin,
                    equity=coin.equity,
                    wallet_balance=coin.wallet_balance,
                    total_order_im=coin.total_order_im,
                    total_position_im=coin.total_position_im,
                )
                for coin in balance.coins
            ],
        )

    async def get_positions(self) -> list[PositionResponse]:
        positions = await self.exchange_client.get_positions()
        return [
            PositionResponse(
                symbol=position.symbol,
                side=position.side,
                size=position.size,
                entry_price=position.entry_price,
                mark_price=position.mark_price,
                position_value=position.position_value,
                leverage=position.leverage,
                unrealized_pnl=position.unrealized_pnl,
                stop_loss=position.stop_loss,
                take_profit=position.take_profit,
                liquidation_price=position.liquidation_price,
            )
            for position in positions
        ]

    async def get_open_orders(self) -> list[dict[str, object]]:
        orders = await self.exchange_client.get_open_orders()
        return list(orders)
