"""Strategy Lab: runs multiple strategy workers in parallel.

Each worker independently evaluates symbols and generates signals.
Uses asyncio.Semaphore to limit concurrent exchange API calls.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.models.candle import SupportedSymbol
from app.models.signal import StrategyEvaluation
from app.strategies.base_worker import BaseStrategyWorker

logger = logging.getLogger(__name__)

_MAX_CONCURRENT = 5


class StrategyLabService:
    """Orchestrates N strategy workers across M symbols concurrently."""

    def __init__(self, workers: list[BaseStrategyWorker]) -> None:
        self._workers = workers
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

    async def evaluate_all(
        self, symbols: list[SupportedSymbol]
    ) -> dict[str, list[StrategyEvaluation]]:
        """Run all workers × all symbols concurrently."""
        results: dict[str, list[StrategyEvaluation]] = {
            w.strategy_name: [] for w in self._workers
        }

        async def _run(worker: BaseStrategyWorker, symbol: SupportedSymbol) -> tuple[str, StrategyEvaluation]:
            async with self._semaphore:
                try:
                    evaluation = await worker.evaluate(symbol)
                    return worker.strategy_name, evaluation
                except Exception as exc:
                    logger.exception(
                        "Strategy %s failed for %s: %s",
                        worker.strategy_name,
                        symbol,
                        exc,
                    )
                    return worker.strategy_name, StrategyEvaluation(
                        symbol=symbol,
                        evaluation_time=datetime.now(timezone.utc),
                        latest_entry_candle_time=None,
                        latest_trend_candle_time=None,
                        reason_codes=(),
                    )

        tasks = [
            _run(worker, symbol)
            for worker in self._workers
            for symbol in symbols
        ]

        completed = await asyncio.gather(*tasks)
        for strategy_name, evaluation in completed:
            results[strategy_name].append(evaluation)

        self._latest = results
        self._last_run = datetime.now(timezone.utc)
        return results
