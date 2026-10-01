import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

from app.bot.runtime import BotRuntime
from app.models.candle import Candle
from app.models.signal import StrategyEvaluation, StrategySignal, SignalSide, StrategyName, IndicatorSnapshot
from app.scanner.models import SetupState
from app.scanner.state_machine import PipelineStateMachine

NOW = datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc)

def candle(tf: str, minutes_ago: int = 0, *, close: str | None = None) -> Candle:
    mins = {"1H": 60, "15m": 15, "5m": 5}[tf]
    # Add minor variations to avoid returning None for ADX/EMA but keep it ranging
    price = Decimal(close) if close is not None else Decimal("100") + Decimal(str((minutes_ago % 2) * 0.1))
    return Candle(symbol="BTCUSDT", timeframe=tf, start_time=NOW - timedelta(minutes=minutes_ago * mins), open=price, high=price+Decimal("1"), low=price-Decimal("1"), close=price, volume=Decimal("100"), turnover=Decimal("10000"), is_closed=True)

def test_watching_to_armed_transition_with_valid_5m_entry():
    state = Mock()
    state.state = SetupState.WATCHING
    state.last_processed_5m = NOW - timedelta(minutes=5)
    state.entry_5m = {}
    
    evaluation = Mock(spec=StrategyEvaluation)
    evaluation.latest_entry_candle_time = NOW
    evaluation.evaluation_time = NOW
    evaluation.indicators = IndicatorSnapshot(
        ema_fast=Decimal("100"), ema_slow=Decimal("100"), rsi=Decimal("50"), adx=Decimal("25"),
        volume=Decimal("100"), average_volume=Decimal("100"), higher_tf_ema_fast=Decimal("100"),
        higher_tf_ema_slow=Decimal("100"), higher_tf_ema_fast_previous=Decimal("100")
    )
    evaluation.crossover_age_candles = 0
    evaluation.reason_codes = []
    evaluation.signal = StrategySignal(
        signal_id="test", symbol="BTCUSDT", strategy=StrategyName.EMA_RSI_ADX_MOMENTUM,
        side=SignalSide.BUY, entry_timeframe="5m", trend_timeframe="15m",
        signal_time=NOW, reference_entry_price=Decimal(100), ema_fast=Decimal(100),
        ema_slow=Decimal(100), rsi=Decimal(100), adx=Decimal(100), volume=Decimal(100),
        average_volume=Decimal(100), higher_tf_ema_fast=Decimal(100),
        higher_tf_ema_slow=Decimal(100), higher_tf_ema_fast_previous=Decimal(100),
        crossover_age_candles=0, confidence=90
    )
    
    result = PipelineStateMachine.evaluate_5m_entry(state, evaluation)
    assert result is True
    assert state.state == SetupState.ARMED
    assert state.reason_codes == ["ENTRY_VALID"]
    assert "signal" in state.entry_5m

def test_armed_to_triggered_through_approved_authority():
    state = Mock()
    state.state = SetupState.ARMED
    state.execution_allowed = True
    signal = StrategySignal(
        signal_id="test", symbol="BTCUSDT", strategy=StrategyName.EMA_RSI_ADX_MOMENTUM,
        side=SignalSide.BUY, entry_timeframe="5m", trend_timeframe="15m",
        signal_time=NOW, reference_entry_price=Decimal(100), ema_fast=Decimal(100),
        ema_slow=Decimal(100), rsi=Decimal(100), adx=Decimal(100), volume=Decimal(100),
        average_volume=Decimal(100), higher_tf_ema_fast=Decimal(100),
        higher_tf_ema_slow=Decimal(100), higher_tf_ema_fast_previous=Decimal(100),
        crossover_age_candles=0, confidence=90
    )
    state.entry_5m = {"signal": signal}
    
    result = PipelineStateMachine.confirm_5m_entry(state)
    assert result is True
    assert state.state == SetupState.TRIGGERED
    assert state.reason_codes == ["STRATEGY_AUTHORITY_TRIGGER"]
    assert state.entry_5m["entry_status"] is True

def test_invalid_1h_trend_transitions_correctly():
    state = Mock()
    state.state = SetupState.DISCOVERED
    state.trend_1h = {}
    state.last_processed_1h = None
    
    candles = tuple(candle("1H", i, close="100") for i in range(35, -1, -1))
    
    PipelineStateMachine.evaluate_1h_trend(state, candles)
    
    assert state.state == SetupState.DISCOVERED
    assert state.reason_codes == ["HTF_1H_FAILED"]

def test_mark_executed_and_cooldown():
    state = Mock()
    state.execution_diagnostics = {}
    
    PipelineStateMachine.mark_executed(state, "order-123")
    assert state.state == SetupState.EXECUTED
    assert state.execution_diagnostics["execution_status"] == "SUBMITTED"
    assert state.execution_diagnostics["order_id"] == "order-123"
    
    PipelineStateMachine.enter_cooldown(state, 60, now=NOW)
    assert state.state == SetupState.COOLDOWN
    assert state.cooldown_until == NOW + timedelta(minutes=60)
    assert state.reason_codes == ["COOLDOWN_ACTIVE"]
