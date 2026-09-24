import asyncio
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

from app.bot.runtime import BotRuntime
from app.models.signal import StrategySignal, SignalSide
from app.models.execution import ExecutionResult, ExecutionStatus
from app.scanner.models import SymbolState, SetupState
from app.scanner.state_machine import PipelineStateMachine

@pytest.mark.anyio
async def test_runtime_locks_out_symbol_on_unknown_reconciling_status():
    strategy_service = Mock()
    scanner_engine = Mock()
    execution_service = Mock()
    activity_repository = Mock()
    
    execution_service._exchange = Mock()
    execution_service._exchange.get_positions = AsyncMock(return_value=[])
    
    # We want execution to return UNKNOWN_RECONCILING
    execution_service.execute = AsyncMock(return_value=ExecutionResult(
        status=ExecutionStatus.UNKNOWN_RECONCILING,
        signal_id="sig-1",
        symbol="BTCUSDT",
        side=SignalSide.BUY,
        submitted_at=datetime.now(timezone.utc)
    ))
    
    scanner_engine.refresh_universe = AsyncMock()
    scanner_engine._is_execution_allowed = Mock(return_value=True)
    scanner_engine.watchlist = Mock()
    scanner_engine.watchlist.all_monitored = ["BTCUSDT"]
    scanner_engine.watchlist.cooldown_symbols = {}
    scanner_engine._last_universe_refresh = None
    
    from app.models.risk import RiskDecisionStatus
    risk_service = Mock()
    risk_decision = Mock()
    risk_decision.status = RiskDecisionStatus.READY
    risk_decision.stop_loss = Decimal(0.9)
    risk_decision.take_profit = Decimal(1.1)
    risk_decision.position_size = Decimal(100)
    risk_decision.notional_value = Decimal(100)
    risk_service.evaluate = AsyncMock(return_value=risk_decision)
    
    runtime = BotRuntime(
        strategy_service=strategy_service,
        scanner_engine=scanner_engine,
        execution_service=execution_service,
        activity_repository=activity_repository,
        risk_service=risk_service,
        poll_interval_seconds=1.0,
        trade_sync_interval_seconds=1.0,
    )
    
    runtime._symbols = ["BTCUSDT"]
    
    # We create a fake state in TRIGGERED
    state = SymbolState("BTCUSDT", SetupState.TRIGGERED)
    state.execution_allowed = True
    state.trigger_1m = {"signal": Mock(
        symbol="BTCUSDT",
        side=SignalSide.BUY,
        signal_id="sig-1",
        entry_price=Decimal(1),
        reference_entry_price=Decimal(1),
        stop_loss=Decimal(0.9),
        take_profit=Decimal(1.1)
    )}
    scanner_engine.get_or_create_state = Mock(return_value=state)
    
    # Mock strategy evaluation to produce a signal
    eval_mock = Mock()
    eval_mock.latest_entry_candle_time = datetime.now(timezone.utc)
    eval_mock.signal = Mock()
    eval_mock.signal.symbol = "BTCUSDT"
    eval_mock.signal.side = SignalSide.BUY
    eval_mock.signal.signal_id = "sig-1"
    eval_mock.signal.entry_price = Decimal(1)
    eval_mock.signal.stop_loss = Decimal(0.9)
    eval_mock.signal.take_profit = Decimal(1.1)
    strategy_service.evaluate = AsyncMock(return_value=eval_mock)
    
    from app.models.candle import Candle
    market_data = Mock()
    mock_candle = Candle(
        symbol="BTCUSDT",
        timeframe="15m",
        start_time=datetime.now(timezone.utc),
        open=Decimal(100),
        high=Decimal(105),
        low=Decimal(95),
        close=Decimal(100),
        is_closed=True,
        volume=Decimal(1000),
        turnover=Decimal(100000)
    )
    market_data.fetch_candles = AsyncMock(return_value=tuple([mock_candle] * 30))
    strategy_service._market_data = market_data
    
    from app.models.readiness import TradingReadinessDecision, TradingReadinessStatus
    readiness_decision = Mock()
    readiness_decision.status = TradingReadinessStatus.READY
    runtime._trading_readiness_service = Mock()
    runtime._trading_readiness_service.evaluate = AsyncMock(return_value=readiness_decision)
    
    # Prevent timeouts from blocking the test
    async def fast_wait(aw, timeout):
        if hasattr(aw, "__await__") or asyncio.iscoroutine(aw):
            return await aw
        return aw
    
    with patch("asyncio.wait_for", new=fast_wait):
        with patch.object(PipelineStateMachine, 'evaluate_15m_context', return_value=True):
            with patch.object(PipelineStateMachine, 'evaluate_5m_setup', return_value=True):
                with patch.object(PipelineStateMachine, 'arm_strategy_authority_trigger', return_value=True):
                    await runtime._run_cycle()
                    
    execution_service.execute.assert_called_once()
    
    # Verify the state got updated to UNKNOWN_RECONCILING
    assert state.execution_diagnostics["execution_status"] == "UNKNOWN_RECONCILING"
    
    # Second cycle - execution should be blocked because of the diagnostic status
    execution_service.execute.reset_mock()
    
    with patch("asyncio.wait_for", new=fast_wait):
        with patch.object(PipelineStateMachine, 'evaluate_15m_context', return_value=True):
            with patch.object(PipelineStateMachine, 'evaluate_5m_setup', return_value=True):
                with patch.object(PipelineStateMachine, 'arm_strategy_authority_trigger', return_value=True):
                    await runtime._run_cycle()
                
    assert state.execution_allowed is False
    assert "RECONCILIATION_MISMATCH" in state.reason_codes
    execution_service.execute.assert_not_called()

    # Third cycle - simulate reconciliation engine becoming safe
    reconciliation_engine = Mock()
    reconciliation_engine.is_safe = Mock(return_value=True)
    runtime._reconciliation_engine = reconciliation_engine

    with patch("asyncio.wait_for", new=fast_wait):
        with patch.object(PipelineStateMachine, 'evaluate_15m_context', return_value=True):
            with patch.object(PipelineStateMachine, 'evaluate_5m_setup', return_value=True):
                with patch.object(PipelineStateMachine, 'arm_strategy_authority_trigger', return_value=True):
                    await runtime._run_cycle()

    # Verify recovery
    assert "execution_status" not in state.execution_diagnostics
    assert "RECOVERED" in state.reason_codes
    assert state.execution_allowed is True
    # execution_service.execute is not called because state is INVALIDATED (from the ORDER_OUTCOME_UNKNOWN),
    # which prevents it from being ARMED or TRIGGERED without traversing normal state machine logic.
    execution_service.execute.assert_not_called()
