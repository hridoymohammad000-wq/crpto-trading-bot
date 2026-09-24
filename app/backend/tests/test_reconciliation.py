import pytest
from unittest.mock import AsyncMock, MagicMock
from app.reconciliation.engine import ReconciliationEngine, ReconciliationStatus
from app.models.account import AccountSummaryResponse, PositionResponse
from app.models.execution import ExecutionResult, ExecutionStatus
from app.models.signal import SignalSide
from datetime import datetime, timezone
from decimal import Decimal

@pytest.fixture
def mock_account_service():
    service = MagicMock()
    service.get_summary = AsyncMock(return_value=AccountSummaryResponse(
        balance="1000.0",
        equity="1100.0",
        margin_balance="1100.0",
        available_margin="900.0",
        available_balance="900.0",
        initial_margin="100.0",
        maintenance_margin="50.0",
        unrealized_pnl="100.0",
        account_type="UNIFIED",
        unified_margin_status=5,
        margin_mode="REGULAR_MARGIN",
        coins=[]
    ))
    
    pos1 = PositionResponse(
        symbol="BTCUSDT",
        side="LONG",
        size="1.0",
        entry_price="50000",
        mark_price="51000",
        unrealized_pnl="1000",
        leverage="10",
        position_value="51000"
    )
    service.get_positions = AsyncMock(return_value=[pos1])
    service.get_open_orders = AsyncMock(return_value=[])
    return service

@pytest.fixture
def mock_exchange():
    return MagicMock()

@pytest.fixture
def mock_persistence():
    db = MagicMock()
    
    # Setup mock signals
    mock_signal = MagicMock()
    mock_signal.signal_id = "sig1"
    mock_signal.symbol = "BTCUSDT"
    mock_signal.side.value = "LONG"
    db.list_signals.return_value = [mock_signal]
    
    # Setup other methods
    db.submitted_signal_ids.return_value = {"sig1"}
    db.list_closed_trades.return_value = []
    db.get_daily_baseline.return_value = Decimal("1000.0")
    db.get_all_metadata.return_value = {"status": "running"}
    db.latest_execution_for_symbol.return_value = None
    
    return db

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_reconciliation_never_calls_execute_query(mock_account_service, mock_exchange, mock_persistence):
    # 1. reconciliation never calls execute_query
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    mock_persistence.execute_query.assert_not_called()

@pytest.mark.anyio
async def test_reconciliation_empty_sqlite_db_does_not_crash(mock_account_service, mock_exchange, mock_persistence):
    # 2. empty SQLite DB does not crash (mocking empty returns)
    mock_persistence.list_signals.return_value = []
    mock_persistence.submitted_signal_ids.return_value = set()
    mock_persistence.list_closed_trades.return_value = []
    mock_persistence.get_daily_baseline.return_value = None
    mock_persistence.get_all_metadata.return_value = {}
    
    mock_account_service.get_positions = AsyncMock(return_value=[])
    
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    assert engine.status == ReconciliationStatus.SYNCED

@pytest.mark.anyio
async def test_real_persistence_getters_populate_local_state(mock_account_service, mock_exchange, mock_persistence):
    # 3. real persistence getters populate local_state
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    result = await engine.get_latest_result()
    assert result.local_state["submitted_order_ids"] == ["sig1"]
    assert result.local_state["persisted_signals"][0]["symbol"] == "BTCUSDT"
    assert result.local_state["daily_baseline"] == 1000.0
    assert result.local_state["runtime_metadata"]["status"] == "running"
    assert result.wallet["available_margin"] == 900.0
    assert result.wallet["available"] == 900.0
    assert result.wallet["margin_mode"] == "REGULAR_MARGIN"

@pytest.mark.anyio
async def test_matching_state_synced(mock_account_service, mock_exchange, mock_persistence):
    # 4. matching state -> SYNCED
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    assert engine.status == ReconciliationStatus.SYNCED

@pytest.mark.anyio
async def test_account_failure_account_unavailable(mock_account_service, mock_exchange, mock_persistence):
    # 5. account failure -> ACCOUNT_UNAVAILABLE
    mock_account_service.get_summary.side_effect = Exception("API down")
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    assert engine.status == ReconciliationStatus.ACCOUNT_UNAVAILABLE
    result = await engine.get_latest_result()
    assert "Failed to fetch account data" in result.mismatches[0]

@pytest.mark.anyio
async def test_position_mismatch(mock_account_service, mock_exchange, mock_persistence):
    # 6. position mismatch -> POSITION_MISMATCH
    # Bybit has a position but local has no history of it
    mock_persistence.list_signals.return_value = []
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    assert engine.status == ReconciliationStatus.POSITION_MISMATCH
    result = await engine.get_latest_result()
    assert len(result.mismatches) == 1
    assert "Position mismatch: BTCUSDT is open on Bybit but has no local history." in result.mismatches[0]

@pytest.mark.anyio
async def test_order_mismatch(mock_account_service, mock_exchange, mock_persistence):
    # 7. order mismatch -> ORDER_MISMATCH
    mock_account_service.get_open_orders = AsyncMock(return_value=[
        {"orderId": "o1", "symbol": "ETHUSDT", "side": "Buy"}
    ])
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    assert engine.status == ReconciliationStatus.ORDER_MISMATCH
    result = await engine.get_latest_result()
    assert len(result.mismatches) == 1
    assert "Order mismatch" in result.mismatches[0]

@pytest.mark.anyio
async def test_local_db_read_failure_handled_clearly(mock_account_service, mock_exchange, mock_persistence):
    # 8. local DB read failure handled clearly
    mock_persistence.list_signals.side_effect = Exception("DB corrupted")
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    assert engine.status == ReconciliationStatus.LOCAL_STATE_STALE
    result = await engine.get_latest_result()
    assert "Local DB read failure: DB corrupted" in result.mismatches[0]

@pytest.mark.anyio
async def test_critical_mismatch_blocks_execution(mock_account_service, mock_exchange, mock_persistence):
    # 9. critical mismatch blocks execution
    mock_persistence.list_signals.return_value = []
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    assert engine.status == ReconciliationStatus.POSITION_MISMATCH
    assert not engine.is_safe()

@pytest.mark.anyio
async def test_synced_allows_normal_execution_flow(mock_account_service, mock_exchange, mock_persistence):
    # 10. SYNCED allows normal execution flow
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    assert engine.status == ReconciliationStatus.SYNCED
    assert engine.is_safe()


def test_reconciliation_is_not_safe_before_first_run(mock_account_service, mock_exchange, mock_persistence):
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    assert engine.status == ReconciliationStatus.RECONCILING
    assert engine.has_completed_once is False
    assert engine.is_safe() is False


@pytest.mark.anyio
async def test_reconciliation_marks_first_attempt_complete_on_account_failure(mock_account_service, mock_exchange, mock_persistence):
    mock_account_service.get_summary.side_effect = Exception("API down")
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    assert engine.has_completed_once is True
    assert engine.status == ReconciliationStatus.ACCOUNT_UNAVAILABLE
    assert engine.is_safe() is False


def _expected_execution(*, stop_loss="49000", take_profit="53000") -> ExecutionResult:
    return ExecutionResult(
        status=ExecutionStatus.ACKNOWLEDGED,
        signal_id="sig1",
        execution_intent_id="intent-sig1",
        risk_decision_id="risk-sig1",
        request_hash="hash-sig1",
        symbol="BTCUSDT",
        side=SignalSide.BUY,
        submitted_at=datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc),
        order_id="order-1",
        order_link_id="sig-sig1",
        quantity=Decimal("1"),
        price=Decimal("50000"),
        stop_loss=Decimal(stop_loss),
        take_profit=Decimal(take_profit),
        leverage=Decimal("3"),
    )


@pytest.mark.anyio
async def test_missing_required_stop_loss_is_critical_protection_mismatch(
    mock_account_service, mock_exchange, mock_persistence
):
    mock_persistence.latest_execution_for_symbol.return_value = _expected_execution()
    # Default fixture position has no SL/TP. Missing SL must fail closed.
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    result = await engine.get_latest_result()

    assert engine.status == ReconciliationStatus.PROTECTION_MISMATCH
    assert engine.is_safe() is False
    assert any("missing required stop loss" in item for item in result.mismatches)


@pytest.mark.anyio
async def test_mismatched_stop_loss_is_critical_protection_mismatch(
    mock_account_service, mock_exchange, mock_persistence
):
    mock_persistence.latest_execution_for_symbol.return_value = _expected_execution()
    mock_account_service.get_positions = AsyncMock(return_value=[
        PositionResponse(
            symbol="BTCUSDT",
            side="LONG",
            size="1",
            entry_price="50000",
            mark_price="51000",
            leverage="3",
            stop_loss="49500",
            take_profit="53000",
        )
    ])
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    result = await engine.get_latest_result()

    assert engine.status == ReconciliationStatus.PROTECTION_MISMATCH
    assert any("stop loss is 49500" in item for item in result.mismatches)


@pytest.mark.anyio
async def test_matching_stop_and_take_profit_remain_synced(
    mock_account_service, mock_exchange, mock_persistence
):
    mock_persistence.latest_execution_for_symbol.return_value = _expected_execution()
    mock_account_service.get_positions = AsyncMock(return_value=[
        PositionResponse(
            symbol="BTCUSDT",
            side="LONG",
            size="1",
            entry_price="50000",
            mark_price="51000",
            leverage="3",
            stop_loss="49000",
            take_profit="53000",
        )
    ])
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    result = await engine.get_latest_result()

    assert engine.status == ReconciliationStatus.SYNCED
    assert result.mismatches == []
    assert result.warnings == []


@pytest.mark.anyio
async def test_take_profit_mismatch_is_warning_only(
    mock_account_service, mock_exchange, mock_persistence
):
    mock_persistence.latest_execution_for_symbol.return_value = _expected_execution()
    mock_account_service.get_positions = AsyncMock(return_value=[
        PositionResponse(
            symbol="BTCUSDT",
            side="LONG",
            size="1",
            entry_price="50000",
            mark_price="51000",
            leverage="3",
            stop_loss="49000",
            take_profit="54000",
        )
    ])
    engine = ReconciliationEngine(mock_account_service, mock_exchange, mock_persistence)
    await engine.reconcile()
    result = await engine.get_latest_result()

    assert engine.status == ReconciliationStatus.SYNCED
    assert engine.is_safe() is True
    assert result.mismatches == []
    assert any("TP warning" in item for item in result.warnings)
