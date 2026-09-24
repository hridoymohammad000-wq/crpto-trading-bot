"""BlockTracker — daily trade-block event counter and summary reporter.

Tracks every reason a trade was blocked or rejected throughout the day.
Produces a structured daily summary log at midnight UTC and exposes
a snapshot via get_report() for the /diagnostics/block-report endpoint.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class BlockTracker:
    """Thread-safe counter for trade block/reject events.

    Call record() every time a trade is blocked or rejected.
    Call daily_summary_loop() as a background task to emit end-of-day logs.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._today: date = datetime.now(timezone.utc).date()
        # reason_code -> count
        self._counts: dict[str, int] = defaultdict(int)
        # last seen details per reason
        self._last_seen: dict[str, str] = {}
        # total signals evaluated today
        self._total_signals: int = 0
        # total trades executed today
        self._total_executed: int = 0
        # history: list of daily snapshots (keeps last 7 days)
        self._history: list[dict[str, Any]] = []
        self._task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def record_block(
        self,
        reason_codes: list[str] | tuple[str, ...],
        *,
        symbol: str = "",
        signal_id: str = "",
    ) -> None:
        """Record one or more block reasons for a signal."""
        async with self._lock:
            await self._maybe_rollover()
            for code in reason_codes:
                self._counts[code] += 1
                self._last_seen[code] = (
                    f"symbol={symbol} signal_id={signal_id} "
                    f"at={datetime.now(timezone.utc).isoformat()}"
                )
            self._total_signals += 1

    async def record_risk_reject(
        self,
        reason: str,
        *,
        symbol: str = "",
        signal_id: str = "",
    ) -> None:
        """Record a risk-gate rejection."""
        await self.record_block([f"RISK_{reason}"], symbol=symbol, signal_id=signal_id)

    async def record_execution(self, symbol: str = "") -> None:
        """Record a successful trade execution."""
        async with self._lock:
            await self._maybe_rollover()
            self._total_executed += 1

    def get_report(self) -> dict[str, Any]:
        """Return the current day's block report snapshot (synchronous)."""
        now = datetime.now(timezone.utc)
        counts_sorted = dict(
            sorted(self._counts.items(), key=lambda x: x[1], reverse=True)
        )
        return {
            "date": self._today.isoformat(),
            "generated_at": now.isoformat(),
            "total_signals_evaluated": self._total_signals,
            "total_trades_executed": self._total_executed,
            "total_blocked": self._total_signals - self._total_executed,
            "block_rate_pct": round(
                (1 - self._total_executed / max(self._total_signals, 1)) * 100, 1
            ),
            "block_counts": counts_sorted,
            "last_seen": self._last_seen,
            "top_blocker": (
                max(counts_sorted, key=lambda k: counts_sorted[k])
                if counts_sorted
                else None
            ),
            "history": self._history[-7:],
        }

    async def start_daily_summary_loop(self) -> None:
        """Start the background task that logs a summary at midnight UTC."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._midnight_loop(), name="block-tracker-midnight"
            )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _maybe_rollover(self) -> None:
        """If the UTC date has changed, archive today's counts and reset."""
        today = datetime.now(timezone.utc).date()
        if today != self._today:
            self._archive_day()
            self._today = today
            self._counts = defaultdict(int)
            self._last_seen = {}
            self._total_signals = 0
            self._total_executed = 0

    def _archive_day(self) -> None:
        snapshot = {
            "date": self._today.isoformat(),
            "total_signals": self._total_signals,
            "total_executed": self._total_executed,
            "block_counts": dict(self._counts),
            "top_blocker": (
                max(self._counts, key=lambda k: self._counts[k])
                if self._counts
                else None
            ),
        }
        self._history.append(snapshot)
        # Keep only last 7
        if len(self._history) > 7:
            self._history = self._history[-7:]

    async def _midnight_loop(self) -> None:
        """Wait until 23:55 UTC each day, emit summary log, then rollover."""
        while True:
            try:
                now = datetime.now(timezone.utc)
                # Seconds until 23:55:00 UTC today
                target = now.replace(hour=23, minute=55, second=0, microsecond=0)
                if now >= target:
                    # Already past 23:55 today → aim for tomorrow
                    from datetime import timedelta
                    target = target + timedelta(days=1)
                wait_seconds = (target - now).total_seconds()
                await asyncio.sleep(wait_seconds)

                # Emit the end-of-day summary
                report = self.get_report()
                logger.info(
                    "📊 DAILY BLOCK REPORT [%s] | signals=%d executed=%d blocked=%d (%.1f%%) | top_blocker=%s | breakdown=%s",
                    report["date"],
                    report["total_signals_evaluated"],
                    report["total_trades_executed"],
                    report["total_blocked"],
                    report["block_rate_pct"],
                    report["top_blocker"] or "none",
                    report["block_counts"],
                )

                # Archive and roll over
                async with self._lock:
                    self._archive_day()
                    today = datetime.now(timezone.utc).date()
                    self._today = today
                    self._counts = defaultdict(int)
                    self._last_seen = {}
                    self._total_signals = 0
                    self._total_executed = 0

                # Wait a bit so we don't fire twice in the same minute
                await asyncio.sleep(120)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("BlockTracker midnight loop error: %s", exc)
                await asyncio.sleep(60)
