"""Strategy Lab: runs multiple strategy workers in parallel.

Each worker independently evaluates symbols and generates paper-only signals.
Strategy Lab signals may be persisted for research, but they never enter the
execution pipeline.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

from app.models.candle import SupportedSymbol
from app.models.signal import StrategyEvaluation
from app.strategies.base_worker import BaseStrategyWorker
from app.strategies.lab_repository import StrategyLabRepository

logger = logging.getLogger(__name__)

_MAX_CONCURRENT = 5


class StrategyLabService:
    """Orchestrates N strategy workers across M symbols concurrently."""

    def __init__(
        self,
        workers: list[BaseStrategyWorker],
        repository: StrategyLabRepository | None = None,
    ) -> None:
        self._workers = workers
        self._repository = repository
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
        self._latest: dict[str, list[StrategyEvaluation]] = {}
        self._last_run: datetime | None = None

    @property
    def workers(self) -> list[BaseStrategyWorker]:
        return list(self._workers)

    @property
    def latest_results(self) -> dict[str, list[StrategyEvaluation]]:
        return dict(self._latest)

    @property
    def last_run(self) -> datetime | None:
        return self._last_run

    def mark_open_signals(
        self,
        prices: dict[str, Decimal],
    ) -> int:
        """Mark OPEN paper signals against supplied market prices."""

        if self._repository is None:
            return 0

        rows = self._repository.list_signals(
            limit=10000,
            status="OPEN",
        )

        updated = 0

        for row in rows:
            symbol = str(row["symbol"])
            current_price = prices.get(symbol)

            if current_price is None:
                continue

            entry_price = Decimal(str(row["entry_price"]))

            if entry_price <= 0:
                continue

            side = str(row["side"]).upper()

            if side == "BUY":
                pnl_pct = (
                    (current_price - entry_price)
                    / entry_price
                ) * Decimal("100")

            elif side == "SELL":
                pnl_pct = (
                    (entry_price - current_price)
                    / entry_price
                ) * Decimal("100")

            else:
                continue

            self._repository.update_mark(
                str(row["signal_id"]),
                current_price=current_price,
                pnl_pct=pnl_pct,
            )

            updated += 1

        return updated

    async def evaluate_all(
        self,
        symbols: list[SupportedSymbol],
    ) -> dict[str, list[StrategyEvaluation]]:
        """Run all workers × all symbols concurrently."""

        results: dict[str, list[StrategyEvaluation]] = {
            worker.strategy_name: []
            for worker in self._workers
        }

        async def _run(
            worker: BaseStrategyWorker,
            symbol: SupportedSymbol,
        ) -> tuple[str, StrategyEvaluation]:
            async with self._semaphore:
                try:
                    evaluation = await worker.evaluate(symbol)

                    return (
                        worker.strategy_name,
                        evaluation,
                    )

                except Exception as exc:
                    logger.exception(
                        "Strategy %s failed for %s: %s",
                        worker.strategy_name,
                        symbol,
                        exc,
                    )

                    return (
                        worker.strategy_name,
                        StrategyEvaluation(
                            symbol=symbol,
                            evaluation_time=datetime.now(timezone.utc),
                            latest_entry_candle_time=None,
                            latest_trend_candle_time=None,
                            reason_codes=(),
                        ),
                    )

        tasks = [
            _run(worker, symbol)
            for worker in self._workers
            for symbol in symbols
        ]

        completed = await asyncio.gather(*tasks)

        for strategy_name, evaluation in completed:
            results[strategy_name].append(evaluation)

            if (
                evaluation.signal is not None
                and self._repository is not None
            ):
                try:
                    created = self._repository.save_signal(
                        evaluation.signal
                    )

                    if created:
                        logger.info(
                            "Strategy Lab paper signal persisted: "
                            "strategy=%s symbol=%s signal_id=%s",
                            evaluation.signal.strategy.value,
                            evaluation.signal.symbol,
                            evaluation.signal.signal_id,
                        )

                except Exception:
                    logger.exception(
                        "Failed to persist Strategy Lab signal "
                        "strategy=%s symbol=%s",
                        strategy_name,
                        evaluation.symbol,
                    )

        self._latest = results
        self._last_run = datetime.now(timezone.utc)

        return results