import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from app.bot.runtime import BotRuntime

@pytest.mark.anyio
async def test_runtime_timeout_behavior():
    strategy_service = Mock()
    scanner_engine = Mock()
    execution_service = Mock()
    execution_service._exchange = Mock()
    activity_repository = Mock()
    
    execution_service.get_positions = AsyncMock()
    scanner_engine.refresh_universe = AsyncMock()
    
    runtime = BotRuntime(
        strategy_service=strategy_service,
        scanner_engine=scanner_engine,
        execution_service=execution_service,
        activity_repository=activity_repository,
        poll_interval_seconds=1.0,
        trade_sync_interval_seconds=1.0,
    )
    
    runtime._symbols = ["BTCUSDT"]
    scanner_engine.watchlist.all_monitored = ["BTCUSDT"]
    scanner_engine.get_or_create_state = Mock()
    state = Mock()
    state.state.value = "DISCOVERED"
    state.state = Mock()
    state.state.value = "DISCOVERED"
    state.state.__eq__ = lambda self, other: other == "DISCOVERED"
    from app.scanner.models import SetupState
    state.state = SetupState.DISCOVERED
    scanner_engine.get_or_create_state.return_value = state
    
    original_wait_for = asyncio.wait_for
    
    async def mock_wait_for(aw, timeout):
        if hasattr(aw, "cr_code") and "get_positions" in aw.cr_code.co_name:
            raise asyncio.TimeoutError()
        # Fallback to original wait_for with a tiny timeout if it's our mock
        if isinstance(aw, AsyncMock) or hasattr(aw, "__await__"):
            try:
                return await original_wait_for(aw, timeout=0.1)
            except Exception:
                return None
        return await original_wait_for(aw, timeout)
        
    with patch("asyncio.wait_for", new=mock_wait_for):
        await runtime._run_cycle()
        
    snapshot = runtime.snapshot()
    assert snapshot["cycle_count"] == 1
    assert snapshot["last_completed_cycle_time"] is not None
