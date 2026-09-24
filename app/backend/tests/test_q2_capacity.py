import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest

from app.account.service import AccountService
from app.exchange.bybit.client import AccountBalance, BybitDemoClient, CoinBalance
from pydantic import BaseModel


class MockAccountInfo(BaseModel):
    unified_margin_status: int = 3
    margin_mode: str = "ISOLATED_MARGIN"


def test_cross_margin_uses_total_available_balance():
    async def run():
        client = Mock(spec=BybitDemoClient)
        client.get_account_balance = AsyncMock(
            return_value=AccountBalance(
                total_wallet_balance=Decimal("1000"),
                total_equity=Decimal("1000"),
                total_margin_balance=Decimal("1000"),
                total_available_balance=Decimal("950"),
                total_initial_margin=Decimal("50"),
                total_maintenance_margin=Decimal("10"),
                total_perp_upl=Decimal("0"),
                coins=[
                    CoinBalance(
                        coin="USDT",
                        equity=Decimal("1000"),
                        wallet_balance=Decimal("1000"),
                        total_order_im=Decimal("0"),
                        total_position_im=Decimal("50"),
                    )
                ],
            )
        )
        client.get_account_info = AsyncMock(
            return_value=MockAccountInfo(margin_mode="REGULAR_MARGIN")
        )

        service = AccountService(client)
        summary = await service.get_summary()
        assert summary.available_trading_capacity == Decimal("950")
        assert summary.capacity_source == "TOTAL_AVAILABLE_BALANCE"
    asyncio.run(run())


def test_isolated_margin_missing_total_derives_from_usdt_coin():
    async def run():
        client = Mock(spec=BybitDemoClient)
        client.get_account_balance = AsyncMock(
            return_value=AccountBalance(
                total_wallet_balance=Decimal("1000"),
                total_equity=Decimal("1000"),
                total_margin_balance=Decimal("1000"),
                total_available_balance=None,  # Missing in ISOLATED_MARGIN
                total_initial_margin=Decimal("50"),
                total_maintenance_margin=Decimal("10"),
                total_perp_upl=Decimal("0"),
                coins=[
                    CoinBalance(
                        coin="USDT",
                        equity=Decimal("1000"),
                        wallet_balance=Decimal("1000"),
                        total_order_im=Decimal("10"),
                        total_position_im=Decimal("40"),
                    )
                ],
            )
        )
        client.get_account_info = AsyncMock(
            return_value=MockAccountInfo(margin_mode="ISOLATED_MARGIN")
        )

        service = AccountService(client)
        summary = await service.get_summary()
        
        # 1000 - 10 - 40 = 950
        assert summary.available_trading_capacity == Decimal("950")
        assert summary.capacity_source == "ISOLATED_DERIVED"
    asyncio.run(run())


def test_isolated_margin_missing_fields_leaves_capacity_unknown():
    async def run():
        client = Mock(spec=BybitDemoClient)
        client.get_account_balance = AsyncMock(
            return_value=AccountBalance(
                total_wallet_balance=Decimal("1000"),
                total_equity=Decimal("1000"),
                total_margin_balance=Decimal("1000"),
                total_available_balance=None,
                total_initial_margin=Decimal("50"),
                total_maintenance_margin=Decimal("10"),
                total_perp_upl=Decimal("0"),
                coins=[
                    CoinBalance(
                        coin="USDT",
                        equity=Decimal("1000"),
                        wallet_balance=Decimal("1000"),
                        total_order_im=None,  # Missing
                        total_position_im=Decimal("40"),
                    )
                ],
            )
        )
        client.get_account_info = AsyncMock(
            return_value=MockAccountInfo(margin_mode="ISOLATED_MARGIN")
        )

        service = AccountService(client)
        summary = await service.get_summary()
        
        assert summary.available_trading_capacity is None
        assert summary.capacity_source == "UNAVAILABLE"
    asyncio.run(run())


def test_missing_usdt_coin_leaves_capacity_unknown():
    async def run():
        client = Mock(spec=BybitDemoClient)
        client.get_account_balance = AsyncMock(
            return_value=AccountBalance(
                total_wallet_balance=Decimal("1000"),
                total_equity=Decimal("1000"),
                total_margin_balance=Decimal("1000"),
                total_available_balance=None,
                total_initial_margin=Decimal("50"),
                total_maintenance_margin=Decimal("10"),
                total_perp_upl=Decimal("0"),
                coins=[
                    CoinBalance(
                        coin="BTC",
                        equity=Decimal("1"),
                        wallet_balance=Decimal("1"),
                        total_order_im=Decimal("0"),
                        total_position_im=Decimal("0"),
                    )
                ],
            )
        )
        client.get_account_info = AsyncMock(
            return_value=MockAccountInfo(margin_mode="ISOLATED_MARGIN")
        )

        service = AccountService(client)
        summary = await service.get_summary()
        
        assert summary.available_trading_capacity is None
        assert summary.capacity_source == "UNAVAILABLE"
    asyncio.run(run())
