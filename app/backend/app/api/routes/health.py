from datetime import datetime, timezone
from typing import Any, cast

from fastapi import APIRouter, Request

from app.bot.runtime import BotRuntime
from app.scanner.engine import ScannerEngine
from app.reconciliation.engine import ReconciliationEngine
from app.persistence import PersistenceDatabase
from app.exchange.bybit import BybitDemoClient
from app.repositories.activity import ActivityRepository


router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    bot_runtime = cast(BotRuntime, request.app.state.bot_runtime)
    scanner_engine = cast(ScannerEngine, request.app.state.scanner_engine)
    reconciliation_engine = cast(ReconciliationEngine, request.app.state.reconciliation_engine)
    activity_repo = cast(ActivityRepository, request.app.state.activity_repository)
    backend_startup_time = request.app.state.backend_startup_time
    watchdog = getattr(request.app.state, "health_watchdog", None)

    now = datetime.now(timezone.utc)
    uptime_seconds = (now - backend_startup_time).total_seconds()

    bot_snap = bot_runtime.snapshot()
    scanner_running = True

    watchdog_active_incidents = watchdog._active_incidents if watchdog else {}

    # Rely on watchdog state instead of executing fresh remote API/DB calls
    db_healthy = "Database unavailable or DB write failure" not in watchdog_active_incidents
    bybit_connected = "Bybit disconnected / auth/API failure" not in watchdog_active_incidents

    last_bybit_success = watchdog.last_success if watchdog else None

    position_manager_running = bot_runtime.worker_running

    last_scan_at = getattr(scanner_engine, "_last_universe_refresh", None)
    last_recon_at = getattr(reconciliation_engine, "_last_time", None)

    # Use in-memory signals buffer instead of querying DB
    last_signal_time = None
    if hasattr(activity_repo, "_lock") and hasattr(activity_repo, "_signals"):
        with activity_repo._lock:
            if activity_repo._signals:
                last_signal_time = activity_repo._signals[-1].signal_time

    # Omit heavy closed trades lookup - return None as permitted by schema
    last_order_time = None

    # Determine critical states
    scanner_stalled = False
    if scanner_running:
        if last_scan_at:
            try:
                ls_time = datetime.fromisoformat(last_scan_at.replace("Z", "+00:00")) if isinstance(last_scan_at, str) else last_scan_at
                scanner_stalled = (now - ls_time).total_seconds() > 1200
            except Exception:
                pass
        else:
            if uptime_seconds > 1200:
                scanner_stalled = True

    db_write_failure = not db_healthy
    bybit_disconnected = not bybit_connected

    # Open position but inactive manager
    open_positions = len(bot_runtime._position_manager._open_positions) if hasattr(bot_runtime, "_position_manager") and hasattr(bot_runtime._position_manager, "_open_positions") else 0
    manager_inactive = open_positions > 0 and not position_manager_running

    stale_reconciliation = False
    if last_recon_at:
        try:
            lr_time = datetime.fromisoformat(last_recon_at.replace("Z", "+00:00")) if isinstance(last_recon_at, str) else last_recon_at
            stale_reconciliation = (now - lr_time).total_seconds() > 600
        except Exception:
            pass

    repeated_be_failure = False 

    status = "healthy"
    if db_write_failure or bybit_disconnected or scanner_stalled or manager_inactive:
        status = "unhealthy"
    elif stale_reconciliation:
        status = "degraded"

    return {
        "status": status,
        "backend_healthy": True,
        "db_healthy": db_healthy,
        "bybit_connected": bybit_connected,
        "scanner_running": scanner_running,
        "position_manager_running": position_manager_running,
        "last_scan_timestamp": last_scan_at.isoformat() if hasattr(last_scan_at, "isoformat") else last_scan_at,
        "last_successful_bybit_api_timestamp": last_bybit_success.isoformat() if hasattr(last_bybit_success, "isoformat") else last_bybit_success,
        "last_signal_timestamp": last_signal_time.isoformat() if hasattr(last_signal_time, "isoformat") else last_signal_time,
        "last_order_timestamp": last_order_time.isoformat() if hasattr(last_order_time, "isoformat") else last_order_time,
        "last_reconciliation_timestamp": last_recon_at.isoformat() if hasattr(last_recon_at, "isoformat") else last_recon_at,
        "uptime_seconds": uptime_seconds,
        "watchdog_running": watchdog._running if watchdog else False,
        "watchdog_last_check": watchdog.last_check.isoformat() if watchdog and watchdog.last_check else None,
        "watchdog_last_success": watchdog.last_success.isoformat() if watchdog and watchdog.last_success else None,
        "watchdog_active_incidents": list(watchdog_active_incidents.keys()),
        "watchdog_last_alert": watchdog.last_alert.isoformat() if watchdog and watchdog.last_alert else None,
        "watchdog_last_recovery": watchdog.last_recovery.isoformat() if watchdog and watchdog.last_recovery else None,
        "critical_states": {
            "scanner_stalled": scanner_stalled,
            "db_write_failure": db_write_failure,
            "bybit_disconnected": bybit_disconnected,
            "manager_inactive_with_positions": manager_inactive,
            "stale_reconciliation": stale_reconciliation,
            "repeated_be_failure": repeated_be_failure
        }
    }
