import pytest
from unittest.mock import AsyncMock
from decimal import Decimal

from app.execution.position_manager import PositionManager
from app.exchange.bybit.client import Position
from app.persistence.database import PersistenceDatabase


@pytest.fixture
def mock_exchange():
    exchange = AsyncMock()
    exchange.get_positions.return_value = []
    exchange.set_trading_stop = AsyncMock()
    return exchange


@pytest.fixture
def memory_db(tmp_path):
    db = PersistenceDatabase(str(tmp_path / "test.sqlite3"))
    db.initialize()
    return db


@pytest.fixture
def position_manager(mock_exchange, memory_db):
    return PositionManager(mock_exchange, memory_db)


def _pos(symbol, side, entry, mark, sl, size="1.0", tp=None):
    return Position(
        symbol=symbol,
        side=side,
        size=Decimal(size),
        entry_price=Decimal(str(entry)),
        mark_price=Decimal(str(mark)),
        position_value=Decimal("100"),
        leverage=Decimal("1"),
        unrealized_pnl=Decimal("0"),
        stop_loss=Decimal(str(sl)),
        take_profit=Decimal(str(tp)) if tp is not None else None,
        liquidation_price=Decimal("0"),
    )


def _setup_verified_positions(mock_exchange, pos, new_sl):
    """After set_trading_stop, get_positions returns SL updated to new_sl."""
    verified_pos = Position(
        symbol=pos.symbol,
        side=pos.side,
        size=pos.size,
        entry_price=pos.entry_price,
        mark_price=pos.mark_price,
        position_value=pos.position_value,
        leverage=pos.leverage,
        unrealized_pnl=pos.unrealized_pnl,
        stop_loss=Decimal(str(new_sl)),
        take_profit=pos.take_profit,
        liquidation_price=pos.liquidation_price,
    )
    # First call returns original positions, subsequent calls return verified
    mock_exchange.get_positions.side_effect = [
        (pos,),        # initial fetch
        (verified_pos,),  # post-amend verification
    ]


# ──────────────────────────────────────────────────────────────────────
# 1. LONG reaches exactly +1R -> BE triggers
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_long_exactly_1r(position_manager, mock_exchange, memory_db):
    # Entry 100, SL 90 -> risk = 10. +1R = 110. Mark = 110.
    pos = _pos("BTCUSDT", "Buy", 100, 110, 90)
    verified = _pos("BTCUSDT", "Buy", 100, 110, 100)  # SL moved to entry
    mock_exchange.get_positions.side_effect = [(pos,), (verified,)]

    await position_manager.manage_open_positions()

    mock_exchange.set_trading_stop.assert_called_once_with(
        symbol="BTCUSDT", stop_loss=Decimal("100")
    )
    state = memory_db.get_position_management_state("BTCUSDT")
    assert state["be_triggered"] is True
    assert state["be_status"] == "SUCCESS"
    assert state["current_stop_loss"] == Decimal("100")


# ──────────────────────────────────────────────────────────────────────
# 2. LONG below +1R -> no BE
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_long_below_1r(position_manager, mock_exchange, memory_db):
    pos = _pos("BTCUSDT", "Buy", 100, 109.9, 90)
    mock_exchange.get_positions.return_value = (pos,)

    await position_manager.manage_open_positions()

    mock_exchange.set_trading_stop.assert_not_called()
    state = memory_db.get_position_management_state("BTCUSDT")
    assert state["be_triggered"] is False
    assert state["be_status"] == "MONITORING"
    assert state["current_stop_loss"] == Decimal("90")


# ──────────────────────────────────────────────────────────────────────
# 3. SHORT reaches exactly +1R -> BE triggers
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_short_exactly_1r(position_manager, mock_exchange, memory_db):
    # Entry 100, SL 110 -> risk = 10. +1R = 90. Mark = 90.
    pos = _pos("ETHUSDT", "Sell", 100, 90, 110)
    verified = _pos("ETHUSDT", "Sell", 100, 90, 100)
    mock_exchange.get_positions.side_effect = [(pos,), (verified,)]

    await position_manager.manage_open_positions()

    mock_exchange.set_trading_stop.assert_called_once_with(
        symbol="ETHUSDT", stop_loss=Decimal("100")
    )
    state = memory_db.get_position_management_state("ETHUSDT")
    assert state["be_triggered"] is True
    assert state["be_status"] == "SUCCESS"


# ──────────────────────────────────────────────────────────────────────
# 4. SHORT below +1R -> no BE
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_short_below_1r(position_manager, mock_exchange, memory_db):
    pos = _pos("ETHUSDT", "Sell", 100, 90.1, 110)
    mock_exchange.get_positions.return_value = (pos,)

    await position_manager.manage_open_positions()

    mock_exchange.set_trading_stop.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# 5. BE amend request succeeds (exchange confirms)
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_be_amend_success_verified(position_manager, mock_exchange, memory_db):
    pos = _pos("SOLUSDT", "Buy", 120, 130, 110)
    verified = _pos("SOLUSDT", "Buy", 120, 130, 120)
    mock_exchange.get_positions.side_effect = [(pos,), (verified,)]

    await position_manager.manage_open_positions()

    state = memory_db.get_position_management_state("SOLUSDT")
    assert state["be_status"] == "SUCCESS"
    assert state["be_triggered"] is True
    assert state["current_stop_loss"] == Decimal("120")


# ──────────────────────────────────────────────────────────────────────
# 6. BE amend request fails -> original SL remains
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_be_amend_request_fails(position_manager, mock_exchange, memory_db):
    pos = _pos("BTCUSDT", "Buy", 100, 110, 90)
    mock_exchange.get_positions.return_value = (pos,)
    mock_exchange.set_trading_stop.side_effect = Exception("API Error: retCode 12345")

    await position_manager.manage_open_positions()

    state = memory_db.get_position_management_state("BTCUSDT")
    assert state["be_triggered"] is False
    assert state["be_status"] == "FAILED"
    assert state["current_stop_loss"] == Decimal("90")  # Original SL remains


# ──────────────────────────────────────────────────────────────────────
# 7. Duplicate monitor cycles do NOT submit duplicate BE amendments
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_duplicate_monitor_cycles(position_manager, mock_exchange, memory_db):
    pos = _pos("BTCUSDT", "Buy", 100, 110, 90)
    verified = _pos("BTCUSDT", "Buy", 100, 110, 100)
    mock_exchange.get_positions.side_effect = [(pos,), (verified,)]

    await position_manager.manage_open_positions()
    mock_exchange.set_trading_stop.assert_called_once()

    # Cycle 2: position now shows SL=100 (BE applied on exchange)
    mock_exchange.set_trading_stop.reset_mock()
    pos2 = _pos("BTCUSDT", "Buy", 100, 115, 100)
    mock_exchange.get_positions.return_value = (pos2,)
    mock_exchange.get_positions.side_effect = None

    await position_manager.manage_open_positions()
    mock_exchange.set_trading_stop.assert_not_called()

    # Cycle 3: still no duplicate
    await position_manager.manage_open_positions()
    mock_exchange.set_trading_stop.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# 8. Restart recovery: previously applied BE is NOT re-submitted
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_restart_recovery_already_success(position_manager, mock_exchange, memory_db):
    # Simulate DB state from before restart: BE was successfully applied
    memory_db.upsert_position_management_state({
        "symbol": "SOLUSDT",
        "be_triggered": True,
        "be_trigger_price": Decimal("110"),
        "be_triggered_at": "2026-01-01T00:00:00Z",
        "original_stop_loss": Decimal("90"),
        "current_stop_loss": Decimal("100"),
        "be_order_id": None,
        "be_status": "SUCCESS",
        "updated_at": "2026-01-01T00:00:00Z",
    })

    pos = _pos("SOLUSDT", "Buy", 100, 115, 100)
    mock_exchange.get_positions.return_value = (pos,)

    await position_manager.manage_open_positions()

    # Must NOT re-submit
    mock_exchange.set_trading_stop.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# 8b. Restart recovery: monitoring state, position at +1R -> triggers BE
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_restart_recovery_monitoring(position_manager, mock_exchange, memory_db):
    memory_db.upsert_position_management_state({
        "symbol": "SOLUSDT",
        "be_triggered": False,
        "be_trigger_price": None,
        "be_triggered_at": None,
        "original_stop_loss": Decimal("90"),
        "current_stop_loss": Decimal("90"),
        "be_order_id": None,
        "be_status": "MONITORING",
        "updated_at": "2026-01-01T00:00:00Z",
    })

    pos = _pos("SOLUSDT", "Buy", 100, 110, 90)
    verified = _pos("SOLUSDT", "Buy", 100, 110, 100)
    mock_exchange.get_positions.side_effect = [(pos,), (verified,)]

    await position_manager.manage_open_positions()

    mock_exchange.set_trading_stop.assert_called_once()
    state = memory_db.get_position_management_state("SOLUSDT")
    assert state["be_status"] == "SUCCESS"


# ──────────────────────────────────────────────────────────────────────
# 9. Position already above +1R when monitoring starts
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_already_above_1r(position_manager, mock_exchange, memory_db):
    pos = _pos("ADAUSDT", "Buy", 100, 150, 90)
    verified = _pos("ADAUSDT", "Buy", 100, 150, 100)
    mock_exchange.get_positions.side_effect = [(pos,), (verified,)]

    await position_manager.manage_open_positions()

    mock_exchange.set_trading_stop.assert_called_once_with(
        symbol="ADAUSDT", stop_loss=Decimal("100")
    )


# ──────────────────────────────────────────────────────────────────────
# 10. Existing TP behavior remains unchanged
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_tp_unchanged(position_manager, mock_exchange, memory_db):
    pos = _pos("BTCUSDT", "Buy", 100, 110, 90, tp=120)
    verified = _pos("BTCUSDT", "Buy", 100, 110, 100, tp=120)
    mock_exchange.get_positions.side_effect = [(pos,), (verified,)]

    await position_manager.manage_open_positions()

    # Only stop_loss is passed — TP is not touched
    mock_exchange.set_trading_stop.assert_called_once_with(
        symbol="BTCUSDT", stop_loss=Decimal("100")
    )


# ──────────────────────────────────────────────────────────────────────
# 11. Existing SL behavior: never move SL backwards
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_never_move_sl_backwards(position_manager, mock_exchange, memory_db):
    # SL already past BE (user manually moved SL to 105)
    pos = _pos("BTCUSDT", "Buy", 100, 110, 105)
    mock_exchange.get_positions.return_value = (pos,)

    await position_manager.manage_open_positions()

    mock_exchange.set_trading_stop.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# 12. Multiple simultaneous positions
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_multiple_simultaneous_positions(position_manager, mock_exchange, memory_db):
    pos1 = _pos("BTCUSDT", "Buy", 100, 110, 90)   # reaches +1R
    pos2 = _pos("ETHUSDT", "Buy", 100, 105, 90)   # < 1R
    pos3 = _pos("SOLUSDT", "Sell", 100, 80, 110)  # reaches +2R

    v1 = _pos("BTCUSDT", "Buy", 100, 110, 100)
    v3 = _pos("SOLUSDT", "Sell", 100, 80, 100)

    # get_positions called: initial, then verify for pos1, then for pos3
    mock_exchange.get_positions.side_effect = [
        (pos1, pos2, pos3),  # initial
        (v1,),               # verify BTCUSDT
        (v3,),               # verify SOLUSDT
    ]

    await position_manager.manage_open_positions()

    assert mock_exchange.set_trading_stop.call_count == 2

    state_btc = memory_db.get_position_management_state("BTCUSDT")
    state_eth = memory_db.get_position_management_state("ETHUSDT")
    state_sol = memory_db.get_position_management_state("SOLUSDT")

    assert state_btc["be_triggered"] is True
    assert state_eth["be_triggered"] is False
    assert state_sol["be_triggered"] is True


# ──────────────────────────────────────────────────────────────────────
# 13. Exchange response confirmation (retCode validation via _post)
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_exchange_retcode_failure(position_manager, mock_exchange, memory_db):
    """Simulates Bybit returning retCode != 0 which _post converts to BybitAPIError."""
    from app.exchange.bybit.exceptions import BybitAPIError

    pos = _pos("DOTUSDT", "Buy", 100, 110, 90)
    mock_exchange.get_positions.return_value = (pos,)
    mock_exchange.set_trading_stop.side_effect = BybitAPIError(
        "Bybit API returned error code 110025: position is cross margin mode"
    )

    await position_manager.manage_open_positions()

    state = memory_db.get_position_management_state("DOTUSDT")
    assert state["be_status"] == "FAILED"
    assert state["be_triggered"] is False


# ──────────────────────────────────────────────────────────────────────
# 14. Post-amend verification failure -> VERIFICATION_FAILED
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_post_amend_verification_failure(position_manager, mock_exchange, memory_db):
    pos = _pos("XRPUSDT", "Buy", 100, 110, 90)
    # After amend, exchange still shows old SL
    still_old = _pos("XRPUSDT", "Buy", 100, 110, 90)
    mock_exchange.get_positions.side_effect = [(pos,), (still_old,)]

    await position_manager.manage_open_positions()

    state = memory_db.get_position_management_state("XRPUSDT")
    assert state["be_status"] == "VERIFICATION_FAILED"
    assert state["be_triggered"] is False


# ──────────────────────────────────────────────────────────────────────
# 15. Retry after FAILED state
# ──────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retry_after_failure(position_manager, mock_exchange, memory_db):
    # First attempt fails
    pos = _pos("AVAXUSDT", "Buy", 100, 110, 90)
    mock_exchange.get_positions.return_value = (pos,)
    mock_exchange.set_trading_stop.side_effect = Exception("Timeout")

    await position_manager.manage_open_positions()
    state = memory_db.get_position_management_state("AVAXUSDT")
    assert state["be_status"] == "FAILED"

    # Second attempt succeeds
    mock_exchange.set_trading_stop.side_effect = None
    verified = _pos("AVAXUSDT", "Buy", 100, 112, 100)
    mock_exchange.get_positions.side_effect = [(pos,), (verified,)]

    await position_manager.manage_open_positions()
    state = memory_db.get_position_management_state("AVAXUSDT")
    assert state["be_status"] == "SUCCESS"
    assert state["be_triggered"] is True
