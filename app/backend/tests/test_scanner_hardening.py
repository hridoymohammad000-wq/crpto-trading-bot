import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

from app.bot.runtime import BotRuntime
from app.bot.state import BotState
from app.models.candle import Candle
from app.models.execution import ExecutionResult, ExecutionStatus
from app.models.risk import RiskDecision, RiskDecisionStatus, RiskRejectReason
from app.models.signal import IndicatorSnapshot, SignalSide, StrategyEvaluation, StrategyName, StrategySignal
from app.scanner.engine import ScannerEngine
from app.scanner.models import SetupState, SymbolState
from app.scanner.state_machine import PipelineStateMachine

NOW = datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc)


def candle(tf: str, minutes_ago: int = 0, *, closed: bool = True, close: str = "104") -> Candle:
    mins = {"5m": 5, "15m": 15, "1H": 60}[tf]
    close_value = Decimal(close)
    return Candle(symbol="BTCUSDT", timeframe=tf, start_time=NOW - timedelta(minutes=minutes_ago * mins), open=close_value-Decimal("1"), high=close_value+Decimal("1"), low=close_value-Decimal("2"), close=close_value, volume=Decimal("100"), turnover=Decimal("10000"), is_closed=closed)


def signal(symbol="BTCUSDT") -> StrategySignal:
    return StrategySignal(signal_id=f"sig-{symbol}", symbol=symbol, strategy=StrategyName.EMA_RSI_ADX_MOMENTUM, side=SignalSide.BUY, entry_timeframe="5m", trend_timeframe="15m", signal_time=NOW, reference_entry_price=Decimal("100"), ema_fast=Decimal("101"), ema_slow=Decimal("99"), rsi=Decimal("60"), adx=Decimal("30"), volume=Decimal("120"), average_volume=Decimal("100"), higher_tf_ema_fast=Decimal("102"), higher_tf_ema_slow=Decimal("98"), higher_tf_ema_fast_previous=Decimal("101"), crossover_age_candles=0, confidence=90)


def evaluation(symbol="BTCUSDT", *, with_signal=True) -> StrategyEvaluation:
    return StrategyEvaluation(symbol=symbol, evaluation_time=NOW, latest_entry_candle_time=NOW, latest_trend_candle_time=NOW, signal=signal(symbol) if with_signal else None, indicators=IndicatorSnapshot(ema_fast=Decimal("101"), ema_slow=Decimal("99"), rsi=Decimal("60"), adx=Decimal("30"), volume=Decimal("120"), average_volume=Decimal("100"), higher_tf_ema_fast=Decimal("102"), higher_tf_ema_slow=Decimal("98"), higher_tf_ema_fast_previous=Decimal("101")), crossover_age_candles=0)


class FakeMarket:
    def __init__(self, c1h=None, c15=None, c5=None):
        self.c1h = tuple(c1h or [candle("1H", i, close=str(130 - i)) for i in range(24, -1, -1)])
        self.c15 = tuple(c15 or [candle("15m", i, close=str(140 - i)) for i in range(29, -1, -1)])
        self.c5 = tuple(c5 or [candle("5m", i) for i in range(29, -1, -1)])
        self.calls = []
    async def fetch_candles(self, symbol, timeframe, *, limit=200, closed_only=False):
        self.calls.append((symbol, timeframe, limit, closed_only))
        rows = {"1H": self.c1h, "15m": self.c15, "5m": self.c5}[timeframe]
        if closed_only:
            # Deliberately do NOT filter here in tests; production pipeline must still reject open candles.
            return rows[-limit:]
        return rows[-limit:]


def scanner(market=None, allow=None):
    return ScannerEngine(market or Mock(), execution_allowlist=allow or {"BTCUSDT"}, cooldown_minutes=60)


def runtime_for(symbol="BTCUSDT", *, market=None, allow=None, risk=None, execution=None):
    market = market or FakeMarket()
    strategy = Mock()
    strategy._market_data = market
    strategy.evaluate = AsyncMock(return_value=evaluation(symbol))
    sc = scanner(market, allow)
    sc.watchlist.core_symbols = {symbol}
    sc.watchlist.dynamic_symbols = set()
    sc.get_or_create_state(symbol).state = SetupState.WATCHING
    rt = BotRuntime(strategy, scanner_engine=sc, risk_service=risk, execution_service=execution, state=BotState(), symbols=(symbol,), poll_interval_seconds=1)
    rt._next_scanner_refresh_at = NOW + timedelta(hours=1)
    return rt, sc, strategy


def ready(symbol="BTCUSDT"):
    return RiskDecision(status=RiskDecisionStatus.READY, signal_id=f"sig-{symbol}", symbol=symbol, side=SignalSide.BUY, evaluated_at=NOW, entry=Decimal("100"), quantity=Decimal("1"), stop_loss=Decimal("95"), take_profit=Decimal("110"), risk_reward_ratio=Decimal("2"), leverage=Decimal("3"))


def rejected(symbol="BTCUSDT"):
    return RiskDecision(status=RiskDecisionStatus.REJECTED, signal_id=f"sig-{symbol}", symbol=symbol, side=SignalSide.BUY, evaluated_at=NOW, entry=Decimal("100"), reason=RiskRejectReason.INVALID_STOP_LOSS)


def submitted(symbol="BTCUSDT"):
    return ExecutionResult(status=ExecutionStatus.SUBMITTED, signal_id=f"sig-{symbol}", symbol=symbol, side=SignalSide.BUY, submitted_at=NOW, order_id="order-1")


def test_cooldown_uses_production_transition_and_expiry():
    sc = scanner()
    st = sc.get_or_create_state("BTCUSDT")
    st.state = SetupState.EXECUTED
    until = sc.enter_cooldown("BTCUSDT", now=NOW)
    assert st.state is SetupState.COOLDOWN
    assert until == NOW + timedelta(minutes=60)
    assert not PipelineStateMachine.release_cooldown(st, now=NOW + timedelta(minutes=59))
    assert st.state is SetupState.COOLDOWN
    sc.release_expired_cooldowns(now=NOW + timedelta(minutes=61))
    assert st.state is SetupState.DISCOVERED
    assert "BTCUSDT" not in sc.watchlist.cooldown_symbols


def test_cooldown_blocks_trend_reentry():
    st = SymbolState(symbol="BTCUSDT", state=SetupState.COOLDOWN, cooldown_until=NOW + timedelta(minutes=60))
    result = PipelineStateMachine.evaluate_1h_trend(st, tuple(candle("1H", i, close=str(130 - i)) for i in range(24, -1, -1)))
    assert st.state is SetupState.COOLDOWN
    assert isinstance(result, bool)


def test_same_5m_candle_is_not_strategy_evaluated_twice():
    rt, sc, strategy = runtime_for()
    asyncio.run(rt._run_cycle())
    first = strategy.evaluate.call_count
    asyncio.run(rt._run_cycle())
    assert first == 1
    assert strategy.evaluate.call_count == 1


def test_new_5m_candle_is_evaluated_once_more():
    market = FakeMarket()
    rt, sc, strategy = runtime_for(market=market)
    asyncio.run(rt._run_cycle())
    market.c5 = market.c5 + (Candle(symbol="BTCUSDT", timeframe="5m", start_time=NOW + timedelta(minutes=5), open=Decimal("100"), high=Decimal("105"), low=Decimal("98"), close=Decimal("104"), volume=Decimal("100"), turnover=Decimal("10000"), is_closed=True),)
    strategy.evaluate.return_value = StrategyEvaluation(**{**evaluation().model_dump(), "latest_entry_candle_time": NOW + timedelta(minutes=5), "evaluation_time": NOW + timedelta(minutes=5)})
    asyncio.run(rt._run_cycle())
    assert strategy.evaluate.call_count == 2


def test_same_1h_trend_not_processed_twice():
    rt, sc, _ = runtime_for()
    original = PipelineStateMachine.evaluate_1h_trend
    with patch.object(PipelineStateMachine, "evaluate_1h_trend", wraps=original) as spy:
        asyncio.run(rt._run_cycle()); first = spy.call_count
        asyncio.run(rt._run_cycle())
        assert first == 1
        assert spy.call_count == 1


def test_open_5m_candle_cannot_reach_strategy():
    market = FakeMarket(c5=[candle("5m", closed=False)])
    rt, _, strategy = runtime_for(market=market)
    asyncio.run(rt._run_cycle())
    strategy.evaluate.assert_not_called()


def test_open_1h_candle_cannot_reach_trend_evaluator():
    market = FakeMarket(c1h=[candle("1H", closed=False)], c15=[candle("15m", closed=False)], c5=[candle("5m", closed=False)])
    rt, _, _ = runtime_for(market=market)
    with patch.object(PipelineStateMachine, "evaluate_1h_trend", wraps=PipelineStateMachine.evaluate_1h_trend) as spy:
        asyncio.run(rt._run_cycle())
        spy.assert_not_called()


def test_scanner_decision_path_fetches_only_closed_1h_15m_5m_candles():
    market = FakeMarket()
    rt, _, strategy = runtime_for(market=market)

    asyncio.run(rt._run_cycle())

    assert market.calls == [
        ("BTCUSDT", "1H", 60, True),
        ("BTCUSDT", "15m", 30, True),
        ("BTCUSDT", "5m", 200, True),
    ]
    strategy.evaluate.assert_awaited_once()
    assert strategy.evaluate.await_args.kwargs["htf_candles"] == market.c1h
    assert strategy.evaluate.await_args.kwargs["trend_candles"] == market.c15
    assert strategy.evaluate.await_args.kwargs["entry_candles"] == market.c5




def test_non_allowlisted_symbol_never_executes_even_when_risk_ready():
    risk = AsyncMock(); risk.evaluate.return_value = ready("ETHUSDT")
    execution = AsyncMock(); execution.execute.return_value = submitted("ETHUSDT")
    rt, sc, strategy = runtime_for("ETHUSDT", allow={"BTCUSDT"}, risk=risk, execution=execution)
    strategy.evaluate.return_value = evaluation("ETHUSDT")
    asyncio.run(rt._run_cycle())
    risk.evaluate.assert_not_called()
    execution.execute.assert_not_called()
    st = sc.get_or_create_state("ETHUSDT")
    assert st.state is SetupState.INVALIDATED
    assert st.reason_codes == ["BLOCKED_BY_EXECUTION_ALLOWLIST"]


def test_risk_rejection_prevents_execution_on_allowlisted_symbol():
    risk = AsyncMock(); risk.evaluate.return_value = rejected()
    execution = AsyncMock()
    rt, sc, _ = runtime_for(risk=risk, execution=execution)
    asyncio.run(rt._run_cycle())
    execution.execute.assert_not_called()
    assert sc.get_or_create_state("BTCUSDT").state is SetupState.INVALIDATED
    assert sc.get_or_create_state("BTCUSDT").reason_codes == ["RISK_REJECTED"]


def test_allowlisted_ready_signal_executes_exactly_once_and_enters_cooldown():
    risk = AsyncMock(); risk.evaluate.return_value = ready()
    execution = AsyncMock(); execution.execute.return_value = submitted()
    rt, sc, _ = runtime_for(risk=risk, execution=execution)
    asyncio.run(rt._run_cycle())
    execution.execute.assert_awaited_once()
    st = sc.get_or_create_state("BTCUSDT")
    assert st.state is SetupState.COOLDOWN
    assert st.execution_diagnostics["execution_status"] == "SUBMITTED"
    asyncio.run(rt._run_cycle())
    assert execution.execute.await_count == 1


def test_watchlist_refresh_preserves_active_state():
    sc = scanner()
    st = sc.get_or_create_state("DOGEUSDT"); st.state = SetupState.ARMED
    sc.universe = []
    sc._update_watchlist()
    assert "DOGEUSDT" in sc.watchlist.dynamic_symbols
    assert sc.get_or_create_state("DOGEUSDT").state is SetupState.ARMED


def test_scanner_has_no_execution_dependency():
    sc = scanner()
    assert not hasattr(sc, "_execution_service")


