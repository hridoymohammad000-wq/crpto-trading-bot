import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from app.bot.runtime import BotRuntime
from app.scanner.engine import ScannerEngine
from app.reconciliation.engine import ReconciliationEngine
from app.persistence import PersistenceDatabase
from app.exchange.bybit import BybitDemoClient
from app.notifications.telegram import send_telegram_message

logger = logging.getLogger(__name__)

class ScheduledHealthWatchdog:
    def __init__(
        self,
        bot_runtime: BotRuntime,
        scanner_engine: ScannerEngine,
        reconciliation_engine: ReconciliationEngine,
        persistence: PersistenceDatabase,
        exchange: BybitDemoClient,
        interval_seconds: int = 60
    ) -> None:
        self._bot_runtime = bot_runtime
        self._scanner_engine = scanner_engine
        self._reconciliation_engine = reconciliation_engine
        self._persistence = persistence
        self._exchange = exchange
        self._interval_seconds = interval_seconds
        
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._active_incidents: dict[str, datetime] = {}
        self._last_alert_time: dict[str, datetime] = {}
        
        self.last_check: datetime | None = None
        self.last_success: datetime | None = None
        self.last_alert: datetime | None = None
        self.last_recovery: datetime | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._check_health()
                self.last_success = datetime.now(timezone.utc)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watchdog evaluation error: {e}", exc_info=True)
            finally:
                self.last_check = datetime.now(timezone.utc)
            await asyncio.sleep(self._interval_seconds)

    async def _check_health(self) -> None:
        now = datetime.now(timezone.utc)
        current_incidents = set()
        
        # 1. Backend/runtime unhealthy
        if not self._bot_runtime.worker_running:
            current_incidents.add("Backend/runtime unhealthy")
            
        # 2. Bybit disconnected / auth/API failure
        try:
            connected = getattr(self._exchange, "is_connected", lambda: True)()
            if not connected:
                current_incidents.add("Bybit disconnected / auth/API failure")
        except Exception:
            current_incidents.add("Bybit disconnected / auth/API failure")
            
        # 3. Database unavailable or DB write failure
        try:
            self._persistence.health()
        except Exception:
            current_incidents.add("Database unavailable or DB write failure")
            
        # 4. Scanner stalled
        last_scan = getattr(self._scanner_engine, "_last_universe_refresh", None)
        if last_scan:
            ls_time = datetime.fromisoformat(last_scan.replace("Z", "+00:00")) if isinstance(last_scan, str) else last_scan
            if (now - ls_time).total_seconds() > 300:
                current_incidents.add("Scanner stalled")
                
        # 5. Position Manager inactive
        # (Covered by Backend/runtime unhealthy, but we can keep the open_positions check)
            
        # 6. Open position exists while Position Manager inactive
        open_positions = len(self._bot_runtime._position_manager._open_positions) if hasattr(self._bot_runtime, "_position_manager") and hasattr(self._bot_runtime._position_manager, "_open_positions") else 0
        if open_positions > 0 and not self._bot_runtime.worker_running:
            current_incidents.add("Open position exists while Position Manager inactive")
            
        # 7. Reconciliation stale or mismatch
        last_recon = getattr(self._reconciliation_engine, "_last_time", None)
        if last_recon:
            lr_time = datetime.fromisoformat(last_recon.replace("Z", "+00:00")) if isinstance(last_recon, str) else last_recon
            if (now - lr_time).total_seconds() > 600:
                current_incidents.add("Reconciliation stale or mismatch")
                
        # Handle logic for new/resolved incidents
        new_incidents = current_incidents - set(self._active_incidents.keys())
        resolved_incidents = set(self._active_incidents.keys()) - current_incidents
        
        for incident in new_incidents:
            self._active_incidents[incident] = now
            self._last_alert_time[incident] = now
            self.last_alert = now
            await self._send_alert(incident, now, "NEW")
            
        for incident in current_incidents:
            if incident not in new_incidents:
                # Deduplication / 15m reminder
                last_alert = self._last_alert_time.get(incident, now)
                if (now - last_alert).total_seconds() >= 900:
                    self._last_alert_time[incident] = now
                    self.last_alert = now
                    await self._send_alert(incident, self._active_incidents[incident], "REMINDER")
                    
        for incident in resolved_incidents:
            start_time = self._active_incidents.pop(incident, now)
            self._last_alert_time.pop(incident, None)
            self.last_recovery = now
            await self._send_recovery(incident, start_time, now)

    async def _send_alert(self, problem: str, start_time: datetime, alert_type: str) -> None:
        now = datetime.now(timezone.utc)
        last_scan = getattr(self._scanner_engine, "_last_universe_refresh", "Unknown")
        open_positions = len(self._bot_runtime._position_manager._open_positions) if hasattr(self._bot_runtime, "_position_manager") and hasattr(self._bot_runtime._position_manager, "_open_positions") else 0
        
        msg = f"🚨 <b>CRYPTO BOT ALERT</b> ({alert_type})\n\n"
        msg += f"<b>Problem:</b> {problem}\n"
        msg += "<b>Environment:</b> BYBIT DEMO\n"
        msg += f"<b>Time:</b> {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        msg += f"<b>Last Scan:</b> {last_scan}\n"
        msg += f"<b>Backend:</b> {'UP' if self._bot_runtime.worker_running else 'DOWN'}\n"
        msg += f"<b>Bybit:</b> {'CONNECTED' if getattr(self._exchange, 'is_connected', lambda: True)() else 'DISCONNECTED'}\n"
        try:
            self._persistence.health()
            db_status = "HEALTHY"
        except Exception:
            db_status = "UNHEALTHY"
        msg += f"<b>DB:</b> {db_status}\n"
        msg += f"<b>Open Positions:</b> {open_positions}\n"
        msg += f"<b>Position Manager:</b> {'RUNNING' if self._bot_runtime.worker_running else 'STOPPED'}\n\n"
        msg += "<b>Action:</b> Check bot runtime."
        
        try:
            await send_telegram_message(msg)
        except Exception as e:
            logger.error(f"Failed to send watchdog alert: {e}")

    async def _send_recovery(self, problem: str, start_time: datetime, end_time: datetime) -> None:
        downtime_seconds = int((end_time - start_time).total_seconds())
        m, s = divmod(downtime_seconds, 60)
        h, m = divmod(m, 60)
        downtime_str = f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"
        
        msg = "✅ <b>CRYPTO BOT RECOVERED</b>\n\n"
        msg += f"<b>Problem resolved:</b> {problem}\n"
        msg += f"<b>Downtime:</b> {downtime_str}\n"
        msg += f"<b>Time:</b> {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        
        try:
            await send_telegram_message(msg)
        except Exception as e:
            logger.error(f"Failed to send watchdog recovery: {e}")
