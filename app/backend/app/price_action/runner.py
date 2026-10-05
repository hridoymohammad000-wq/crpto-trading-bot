import asyncio
import logging
from datetime import datetime, timezone

from app.price_action.history import (
    PriceActionSignalHistory,
)
from app.price_action.telegram_signals import (
    PriceActionTelegramNotifier,
)


logger = logging.getLogger(__name__)


class PriceActionAutoScanner:

    def __init__(
        self,
        scanner,
        interval_seconds: int = 300,
    ):
        self.scanner = scanner
        self.interval_seconds = interval_seconds

        self.task: asyncio.Task | None = None
        self.running = False

        self.last_run_at = None
        self.last_result = None
        self.last_signals = []

        self.telegram = (
            PriceActionTelegramNotifier()
        )

        self.history = (
            PriceActionSignalHistory(
                scanner.market
            )
        )

    async def start(self):

        if self.running:
            return

        self.running = True

        self.task = asyncio.create_task(
            self._loop(),
            name="price-action-auto-scanner",
        )

        logger.info(
            "Price Action auto scanner started "
            "| interval=%ss",
            self.interval_seconds,
        )

    async def stop(self):

        self.running = False

        if self.task:

            self.task.cancel()

            try:
                await self.task

            except asyncio.CancelledError:
                pass

            self.task = None

        logger.info(
            "Price Action auto scanner stopped"
        )

    async def _loop(self):

        while self.running:

            started = datetime.now(
                timezone.utc
            )

            try:

                result = (
                    await self.scanner.scan()
                )

                self.last_run_at = started
                self.last_result = result
                self.last_signals = list(
                    result.signals
                )

                # ---------------------------------------------
                # Save NEW signals
                # ---------------------------------------------

                saved = (
                    self.history.record_new_signals(
                        result.signals,
                        now=started,
                    )
                )

                # ---------------------------------------------
                # Evaluate previous OPEN signals
                # ---------------------------------------------

                before_rows = {
                    row.get("id"): row.get("status")
                    for row in self.history.records()
                }

                updated = (
                    await self.history
                    .evaluate_open_signals()
                )

                after_records = self.history.records()

                result_events = [
                    row
                    for row in after_records
                    if (
                        row.get("id") in before_rows
                        and before_rows[row.get("id")] == "OPEN"
                        and row.get("status")
                        in {"WIN", "LOSS", "EXPIRED"}
                    )
                ]

                result_telegram_sent = (
                    await self.telegram
                    .send_result_updates(
                        result_events
                    )
                )

                summary = (
                    self.history.summary()
                )

                # ---------------------------------------------
                # Telegram
                # ---------------------------------------------

                telegram_sent = (
                    await self.telegram
                    .send_new_signals(
                        result.signals
                    )
                )

                longs = [
                    x
                    for x in result.signals
                    if x.side == "LONG"
                ]

                shorts = [
                    x
                    for x in result.signals
                    if x.side == "SHORT"
                ]

                print()
                print("=" * 78)

                print(
                    "PRICE ACTION AUTO SCAN:",
                    started.isoformat(),
                )

                print(
                    "SCANNED:",
                    result.scanned_symbols,
                    "| FAILED:",
                    result.failed_symbols,
                    "| SIGNALS:",
                    len(result.signals),
                    "| LONG:",
                    len(longs),
                    "| SHORT:",
                    len(shorts),
                    "| TELEGRAM:",
                    telegram_sent,
                )

                print(
                    "HISTORY NEW:",
                    saved,
                    "| UPDATED:",
                    updated,
                    "| OPEN:",
                    summary["open"],
                    "| WIN:",
                    summary["wins"],
                    "| LOSS:",
                    summary["losses"],
                    "| WIN RATE:",
                    f'{summary["win_rate_pct"]}%',
                    "| TOTAL R:",
                    summary["total_r"],
                    "| RESULT ALERTS:",
                    result_telegram_sent,
                )

                if not result.signals:
                    print(
                        "NO VALID SIGNAL"
                    )

                for x in result.signals:

                    risk = abs(
                        x.entry
                        - x.stop_loss
                    )

                    tp = (
                        x.entry
                        + risk * 2
                        if x.side == "LONG"
                        else x.entry
                        - risk * 2
                    )

                    print()

                    print(
                        x.symbol,
                        "|",
                        x.side,
                        "| SCORE",
                        x.score,
                        "|",
                        x.pattern,
                    )

                    print(
                        "ENTRY:",
                        round(
                            x.entry,
                            8,
                        ),
                        "| SL:",
                        round(
                            x.stop_loss,
                            8,
                        ),
                        "| TP 1:2:",
                        round(
                            tp,
                            8,
                        ),
                    )

                    print(
                        "REASONS:",
                        ", ".join(
                            x.reasons
                        ),
                    )

                print("=" * 78)

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception(
                    "Price Action auto scan failed"
                )

            await asyncio.sleep(
                self.interval_seconds
            )
