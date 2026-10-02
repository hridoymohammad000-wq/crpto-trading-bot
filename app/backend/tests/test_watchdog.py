import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from app.bot.watchdog import ScheduledHealthWatchdog

@pytest.fixture
def mock_deps():
    bot_runtime = MagicMock()
    bot_runtime.worker_running = True
    bot_runtime._position_manager._open_positions = []
    
    scanner = MagicMock()
    scanner._last_universe_refresh = datetime.now(timezone.utc).isoformat()
    
    recon = MagicMock()
    recon._last_time = datetime.now(timezone.utc).isoformat()
    
    persistence = MagicMock()
    persistence.execute.return_value = None
    
    exchange = MagicMock()
    exchange.is_connected.return_value = True
    
    return bot_runtime, scanner, recon, persistence, exchange

@pytest.mark.asyncio
async def test_watchdog_first_problem_triggers_alert(mock_deps):
    bot_runtime, scanner, recon, persistence, exchange = mock_deps
    
    watchdog = ScheduledHealthWatchdog(bot_runtime, scanner, recon, persistence, exchange, interval_seconds=1)
    
    # Introduce a problem
    exchange.is_connected.return_value = False
    
    with patch("app.bot.watchdog.send_telegram_message", new_callable=AsyncMock) as mock_send:
        await watchdog._check_health()
        assert mock_send.call_count == 1
        call_args = mock_send.call_args[0][0]
        assert "Bybit disconnected" in call_args
        assert "NEW" in call_args

@pytest.mark.asyncio
async def test_watchdog_deduplication(mock_deps):
    bot_runtime, scanner, recon, persistence, exchange = mock_deps
    watchdog = ScheduledHealthWatchdog(bot_runtime, scanner, recon, persistence, exchange, interval_seconds=1)
    
    bot_runtime.worker_running = False # Problem
    
    with patch("app.bot.watchdog.send_telegram_message", new_callable=AsyncMock) as mock_send:
        await watchdog._check_health()
        assert mock_send.call_count == 1 # First time alerts
        
        # Second time, same problem -> NO alert due to 15m cooldown
        await watchdog._check_health()
        assert mock_send.call_count == 1

@pytest.mark.asyncio
async def test_watchdog_15m_reminder(mock_deps):
    bot_runtime, scanner, recon, persistence, exchange = mock_deps
    watchdog = ScheduledHealthWatchdog(bot_runtime, scanner, recon, persistence, exchange, interval_seconds=1)
    
    bot_runtime.worker_running = False
    
    with patch("app.bot.watchdog.send_telegram_message", new_callable=AsyncMock) as mock_send:
        await watchdog._check_health()
        
        # Manually move last_alert_time back 15 minutes
        problem_key = "Backend/runtime unhealthy"
        watchdog._last_alert_time[problem_key] = datetime.now(timezone.utc) - timedelta(minutes=16)
        
        await watchdog._check_health()
        assert mock_send.call_count == 2
        call_args = mock_send.call_args[0][0]
        assert "REMINDER" in call_args

@pytest.mark.asyncio
async def test_watchdog_recovery_alert(mock_deps):
    bot_runtime, scanner, recon, persistence, exchange = mock_deps
    watchdog = ScheduledHealthWatchdog(bot_runtime, scanner, recon, persistence, exchange, interval_seconds=1)
    
    # Problem
    bot_runtime.worker_running = False
    
    with patch("app.bot.watchdog.send_telegram_message", new_callable=AsyncMock) as mock_send:
        await watchdog._check_health()
        assert len(watchdog._active_incidents) == 1
        
        # Recovery
        bot_runtime.worker_running = True
        await watchdog._check_health()
        
        assert len(watchdog._active_incidents) == 0
        assert mock_send.call_count == 2
        call_args = mock_send.call_args[0][0]
        assert "RECOVERED" in call_args

@pytest.mark.asyncio
async def test_watchdog_recurring_incident(mock_deps):
    bot_runtime, scanner, recon, persistence, exchange = mock_deps
    watchdog = ScheduledHealthWatchdog(bot_runtime, scanner, recon, persistence, exchange, interval_seconds=1)
    
    with patch("app.bot.watchdog.send_telegram_message", new_callable=AsyncMock) as mock_send:
        bot_runtime.worker_running = False
        await watchdog._check_health()
        
        bot_runtime.worker_running = True
        await watchdog._check_health()
        
        bot_runtime.worker_running = False
        await watchdog._check_health()
        
        # 1. New Alert, 2. Recovery, 3. New Alert
        assert mock_send.call_count == 3

@pytest.mark.asyncio
async def test_watchdog_losing_trade_no_alert(mock_deps):
    bot_runtime, scanner, recon, persistence, exchange = mock_deps
    watchdog = ScheduledHealthWatchdog(bot_runtime, scanner, recon, persistence, exchange, interval_seconds=1)
    
    # Simulate normal condition (no errors, even if trades are losing)
    with patch("app.bot.watchdog.send_telegram_message", new_callable=AsyncMock) as mock_send:
        await watchdog._check_health()
        assert mock_send.call_count == 0

@pytest.mark.asyncio
async def test_watchdog_telegram_failure_does_not_crash(mock_deps):
    bot_runtime, scanner, recon, persistence, exchange = mock_deps
    watchdog = ScheduledHealthWatchdog(bot_runtime, scanner, recon, persistence, exchange, interval_seconds=1)
    
    bot_runtime.worker_running = False
    
    with patch("app.bot.watchdog.send_telegram_message", new_callable=AsyncMock, side_effect=Exception("Network error")) as mock_send:
        # Should not raise exception
        await watchdog._check_health()
        assert mock_send.call_count == 1
        assert "Backend/runtime unhealthy" in watchdog._active_incidents

@pytest.mark.asyncio
async def test_watchdog_multiple_simultaneous(mock_deps):
    bot_runtime, scanner, recon, persistence, exchange = mock_deps
    watchdog = ScheduledHealthWatchdog(bot_runtime, scanner, recon, persistence, exchange, interval_seconds=1)
    
    bot_runtime.worker_running = False
    persistence.execute.side_effect = Exception("DB dead")
    
    with patch("app.bot.watchdog.send_telegram_message", new_callable=AsyncMock) as mock_send:
        await watchdog._check_health()
        assert mock_send.call_count == 2
        assert len(watchdog._active_incidents) == 2
