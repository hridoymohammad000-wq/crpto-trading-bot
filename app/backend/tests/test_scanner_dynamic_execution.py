import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

from app.bot.runtime import BotRuntime
from app.bot.state import BotState
from app.models.candle import Candle
from app.models.execution import ExecutionResult, ExecutionStatus
from app.models.risk import RiskDecision, RiskDecisionStatus
from app.models.signal import IndicatorSnapshot, SignalSide, StrategyEvaluation, StrategyName, StrategySignal
from app.scanner.engine import ScannerEngine
from app.scanner.models import SetupState

NOW = datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc)


def candle(tf: str, t: datetime) -> Candle:
    return Candle(symbol="DOGEUSDT", timeframe=tf, start_time=t, open=Decimal("100"), high=Decimal("105"), low=Decimal("98"), close=Decimal("104"), volume=Decimal("100"), turnover=Decimal("10000"), is_closed=True)


def make_signal(symbol: str) -> StrategySignal:
    return StrategySignal(signal_id=f"sig-{symbol}", symbol=symbol, strategy=StrategyName.EMA_RSI_ADX_MOMENTUM, side=SignalSide.BUY, entry_timeframe="5m", trend_timeframe="15m", signal_time=NOW, reference_entry_price=Decimal("100"), ema_fast=Decimal("101"), ema_slow=Decimal("99"), rsi=Decimal("60"), adx=Decimal("30"), volume=Decimal("120"), average_volume=Decimal("100"), higher_tf_ema_fast=Decimal("102"), higher_tf_ema_slow=Decimal("98"), higher_tf_ema_fast_previous=Decimal("101"), crossover_age_candles=0, confidence=90)


def evaluation(symbol: str) -> StrategyEvaluation:
    sig = make_signal(symbol)
    return StrategyEvaluation(symbol=symbol, evaluation_time=NOW, latest_entry_candle_time=NOW, latest_trend_candle_time=NOW, signal=sig, indicators=IndicatorSnapshot(ema_fast=Decimal("101"), ema_slow=Decimal("99"), rsi=Decimal("60"), adx=Decimal("30"), volume=Decimal("120"), average_volume=Decimal("100"), higher_tf_ema_fast=Decimal("102"), higher_tf_ema_slow=Decimal("98"), higher_tf_ema_fast_previous=Decimal("101")), crossover_age_candles=0)


class Market:
    async def fetch_candles(self, symbol, timeframe, *, limit=200, closed_only=False):
        n = 30
        step = {"15m": 15, "5m": 5, "1m": 1}[timeframe]
        rows = []
        base = Decimal("100")
        for i in range(n, 0, -1):
            t = NOW - timedelta(minutes=i * step)
            rows.append(Candle(symbol=symbol, timeframe=timeframe, start_time=t, open=base, high=base+Decimal("5"), low=base-Decimal("1"), close=base+Decimal("4"), volume=Decimal("100"), turnover=Decimal("10000"), is_closed=True))
            base += Decimal("2")
        return tuple(rows[-limit:])


def ready(symbol: str) -> RiskDecision:
    return RiskDecision(status=RiskDecisionStatus.READY, signal_id=f"sig-{symbol}", symbol=symbol, side=SignalSide.BUY, evaluated_at=NOW, entry=Decimal("100"), quantity=Decimal("1"), stop_loss=Decimal("95"), take_profit=Decimal("110"), risk_reward_ratio=Decimal("2"), leverage=Decimal("3"))


def submitted(symbol: str) -> ExecutionResult:
    return ExecutionResult(status=ExecutionStatus.SUBMITTED, signal_id=f"sig-{symbol}", symbol=symbol, side=SignalSide.BUY, submitted_at=NOW, order_id=f"order-{symbol}")


def test_scanner_mode_allows_dynamic_watchlist_symbol():
    sc = ScannerEngine(Mock(), execution_selection_mode="SCANNER")
    sc.watchlist.dynamic_symbols = {"DOGEUSDT"}
    st = sc.get_or_create_state("DOGEUSDT")
    assert st.execution_allowed is True


def test_scanner_mode_blocks_unselected_symbol():
    sc = ScannerEngine(Mock(), execution_selection_mode="SCANNER")
    sc.watchlist.dynamic_symbols = {"DOGEUSDT"}
    st = sc.get_or_create_state("XRPUSDT")
    assert st.execution_allowed is False


def test_static_mode_still_supports_manual_allowlist():
    sc = ScannerEngine(Mock(), execution_allowlist={"BTCUSDT"}, execution_selection_mode="STATIC")
    assert sc.get_or_create_state("BTCUSDT").execution_allowed is True
    assert sc.get_or_create_state("ETHUSDT").execution_allowed is False


def test_dynamic_scanner_symbol_uses_existing_strategy_then_risk_then_execution():
    symbol = "DOGEUSDT"
    market = Market()
    strategy = Mock(); strategy._market_data = market; strategy.evaluate = AsyncMock(return_value=evaluation(symbol))
    risk = AsyncMock(); risk.evaluate.return_value = ready(symbol)
    execution = AsyncMock(); execution.execute.return_value = submitted(symbol)
    sc = ScannerEngine(market, execution_selection_mode="SCANNER")
    sc.watchlist.core_symbols = set()
    sc.watchlist.dynamic_symbols = {symbol}
    st = sc.get_or_create_state(symbol); st.state = SetupState.WATCHING
    rt = BotRuntime(strategy, scanner_engine=sc, risk_service=risk, execution_service=execution, state=BotState(), symbols=(symbol,), poll_interval_seconds=1)
    rt._next_scanner_refresh_at = NOW + timedelta(hours=1)
    asyncio.run(rt._run_cycle())
    risk.evaluate.assert_awaited_once()
    execution.execute.assert_awaited_once()
    assert st.state is SetupState.COOLDOWN
    assert st.execution_diagnostics["execution_status"] == "SUBMITTED"
