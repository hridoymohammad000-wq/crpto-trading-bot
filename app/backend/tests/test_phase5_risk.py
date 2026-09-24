import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.models.account import AccountSummaryResponse, PositionResponse
from app.models.candle import Candle
from app.models.risk import RiskDecisionStatus, RiskRejectReason
from app.models.signal import SignalSide, StrategyName, StrategySignal
from app.risk import RiskService


NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)


def make_signal(side: SignalSide = SignalSide.BUY, entry: str = "100") -> StrategySignal:
    return StrategySignal(
        signal_id=f"sig-{side.value}",
        symbol="BTCUSDT",
        strategy=StrategyName.EMA_RSI_ADX_MOMENTUM,
        side=side,
        entry_timeframe="5m",
        trend_timeframe="15m",
        signal_time=NOW,
        reference_entry_price=Decimal(entry),
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


def candle(index: int, *, low: str, high: str, close: str = "100") -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        start_time=NOW - timedelta(minutes=5 * (5 - index)),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("10"),
        turnover=Decimal("1000"),
        is_closed=True,
    )


class FakeAccountService:
    def __init__(self, equity="10000", available="5000", positions=None):
        self.equity = Decimal(equity) if equity is not None else None
        self.available = Decimal(available) if available is not None else None
        self.positions = positions or []

    async def get_summary(self):
        return AccountSummaryResponse(
            balance=self.equity,
            equity=self.equity,
            available_balance=self.available,
            available_trading_capacity=self.available,
            capacity_source="TOTAL_AVAILABLE_BALANCE",
            unrealized_pnl=Decimal("0"),
            coins=[],
        )

    async def get_positions(self):
        return self.positions


class FakeMarketData:
    def __init__(self, candles):
        self.candles = tuple(candles)

    async def fetch_candles(self, symbol, timeframe, *, limit=200, closed_only=False):
        return self.candles[-limit:]


def run(coro):
    return asyncio.run(coro)


def test_long_ready_uses_structure_stop_two_r_and_one_percent_risk():
    candles = [
        candle(1, low="97", high="101"),
        candle(2, low="98", high="102"),
        candle(3, low="96", high="101"),
        candle(4, low="98", high="103"),
        candle(5, low="97", high="102"),
    ]
    service = RiskService(FakeAccountService(), FakeMarketData(candles))
    decision = run(service.evaluate(make_signal()))

    assert decision.status == RiskDecisionStatus.READY
    assert decision.stop_loss == Decimal("95.904")  # 96 less 0.10% buffer
    assert decision.take_profit == Decimal("108.192")
    assert decision.risk_reward_ratio == Decimal("2")
    assert decision.risk_amount == Decimal("100")
    assert decision.leverage == Decimal("3")
    assert decision.quantity == Decimal("24.41406250")


def test_short_ready_places_stop_above_structure_and_tp_below_entry():
    candles = [
        candle(1, low="95", high="102"),
        candle(2, low="96", high="103"),
        candle(3, low="94", high="104"),
        candle(4, low="95", high="103"),
        candle(5, low="96", high="102"),
    ]
    service = RiskService(FakeAccountService(), FakeMarketData(candles))
    decision = run(service.evaluate(make_signal(SignalSide.SELL, "100")))

    assert decision.status == RiskDecisionStatus.READY
    assert decision.stop_loss == Decimal("104.104")
    assert decision.take_profit == Decimal("91.792")
    assert decision.risk_reward_ratio == Decimal("2")


def test_rejects_duplicate_symbol_position():
    positions = [
        PositionResponse(symbol="BTCUSDT", side="LONG", size=Decimal("0.1"))
    ]
    service = RiskService(
        FakeAccountService(positions=positions),
        FakeMarketData([candle(i, low="96", high="102") for i in range(1, 6)]),
    )
    decision = run(service.evaluate(make_signal()))
    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason == RiskRejectReason.DUPLICATE_SYMBOL_POSITION


def test_rejects_when_three_positions_are_already_active():
    positions = [
        PositionResponse(symbol="ETHUSDT", side="LONG", size=Decimal("1")),
        PositionResponse(symbol="SOLUSDT", side="SHORT", size=Decimal("1")),
        PositionResponse(symbol="XRPUSDT", side="LONG", size=Decimal("1")),
    ]
    service = RiskService(
        FakeAccountService(positions=positions),
        FakeMarketData([candle(i, low="96", high="102") for i in range(1, 6)]),
    )
    decision = run(service.evaluate(make_signal()))
    assert decision.reason == RiskRejectReason.MAX_ACTIVE_POSITIONS


def test_rejects_invalid_long_stop_when_structure_is_above_entry():
    service = RiskService(
        FakeAccountService(),
        FakeMarketData([candle(i, low="101", high="103", close="102") for i in range(1, 6)]),
    )
    decision = run(service.evaluate(make_signal(entry="100")))
    assert decision.reason == RiskRejectReason.INVALID_STOP_LOSS


def test_rejects_insufficient_margin_instead_of_silently_downsizing():
    service = RiskService(
        FakeAccountService(equity="10000", available="100"),
        FakeMarketData([candle(i, low="99", high="101") for i in range(1, 6)]),
    )
    decision = run(service.evaluate(make_signal(entry="100")))
    assert decision.reason == RiskRejectReason.INSUFFICIENT_AVAILABLE_BALANCE


def test_session_daily_loss_guard_rejects_after_three_percent_drawdown():
    account = FakeAccountService(equity="10000", available="5000")
    service = RiskService(
        account,
        FakeMarketData([candle(i, low="96", high="102") for i in range(1, 6)]),
    )
    first = run(service.evaluate(make_signal()))
    assert first.status == RiskDecisionStatus.READY

    account.equity = Decimal("9700")
    second = run(service.evaluate(make_signal()))
    assert second.status == RiskDecisionStatus.REJECTED
    assert second.reason == RiskRejectReason.DAILY_LOSS_LIMIT
    assert second.daily_drawdown_pct == Decimal("3.00")


def test_configuration_refuses_rr_below_two_and_leverage_over_ten():
    try:
        RiskService(FakeAccountService(), FakeMarketData([]), minimum_rr=Decimal("1.9"))
        assert False, "expected ValueError"
    except ValueError:
        pass

    try:
        RiskService(FakeAccountService(), FakeMarketData([]), leverage=Decimal("11"))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_ready_decision_reports_portfolio_risk_and_fee_slippage_allowance():
    positions = [
        PositionResponse(
            symbol="ETHUSDT",
            side="LONG",
            size=Decimal("1"),
            entry_price=Decimal("100"),
            position_value=Decimal("100"),
            stop_loss=Decimal("95"),
        )
    ]
    service = RiskService(
        FakeAccountService(positions=positions),
        FakeMarketData([candle(i, low="96", high="102") for i in range(1, 6)]),
    )
    decision = run(service.evaluate(make_signal()))

    assert decision.status == RiskDecisionStatus.READY
    assert decision.portfolio_open_risk_before == Decimal("5.300")
    assert decision.fee_slippage_allowance is not None
    assert decision.fee_slippage_allowance > 0
    assert decision.portfolio_open_risk_after == (
        decision.portfolio_open_risk_before
        + decision.risk_amount
        + decision.fee_slippage_allowance
    )
    assert decision.max_open_risk_amount == Decimal("300")


def test_rejects_when_proposed_trade_exceeds_total_open_risk_cap():
    positions = [
        PositionResponse(
            symbol="ETHUSDT",
            side="LONG",
            size=Decimal("1"),
            entry_price=Decimal("100"),
            position_value=Decimal("100"),
            stop_loss=Decimal("95"),
        )
    ]
    service = RiskService(
        FakeAccountService(positions=positions),
        FakeMarketData([candle(i, low="96", high="102") for i in range(1, 6)]),
        max_open_risk_pct=Decimal("1"),
    )
    decision = run(service.evaluate(make_signal()))

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason == RiskRejectReason.MAX_OPEN_RISK_EXCEEDED
    assert decision.portfolio_open_risk_before == Decimal("5.300")
    assert decision.portfolio_open_risk_after is not None
    assert decision.portfolio_open_risk_after > Decimal("100")
    assert decision.max_open_risk_amount == Decimal("100")


def test_rejects_when_existing_position_risk_cannot_be_determined():
    positions = [
        PositionResponse(
            symbol="ETHUSDT",
            side="LONG",
            size=Decimal("1"),
            entry_price=Decimal("100"),
            stop_loss=None,
        )
    ]
    service = RiskService(
        FakeAccountService(positions=positions),
        FakeMarketData([candle(i, low="96", high="102") for i in range(1, 6)]),
    )
    decision = run(service.evaluate(make_signal()))

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason == RiskRejectReason.OPEN_POSITION_RISK_UNKNOWN
    assert decision.max_open_risk_amount == Decimal("300")


def test_fee_slippage_allowance_is_included_in_margin_capacity_check():
    service = RiskService(
        FakeAccountService(equity="10000", available="814"),
        FakeMarketData([candle(i, low="96", high="102") for i in range(1, 6)]),
    )
    decision = run(service.evaluate(make_signal(entry="100")))

    # Base estimated margin is about 813.80, but configured fee/slippage
    # allowance pushes required capacity above the available 814.
    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.reason == RiskRejectReason.INSUFFICIENT_AVAILABLE_BALANCE
    assert decision.fee_slippage_allowance is not None
    assert decision.fee_slippage_allowance > 0
