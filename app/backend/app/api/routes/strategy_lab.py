"""Strategy Lab API routes — multi-strategy signal aggregation."""

from decimal import Decimal
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Request

from app.market_data.service import MarketDataService
from app.strategies.lab_repository import StrategyLabRepository
from app.strategies.lab_service import StrategyLabService

router = APIRouter(prefix="/strategy-lab", tags=["strategy-lab"])


def _get_lab(request: Request) -> StrategyLabService:
    return cast(
        StrategyLabService,
        request.app.state.strategy_lab_service,
    )


def _get_lab_repository(request: Request) -> StrategyLabRepository:
    return cast(
        StrategyLabRepository,
        request.app.state.strategy_lab_repository,
    )


def _get_market_data(request: Request) -> MarketDataService:
    return cast(
        MarketDataService,
        request.app.state.market_data_service,
    )


@router.get("/signals")
async def get_lab_signals(
    symbols: Annotated[
        str,
        Query(
            description="Comma-separated symbols, e.g. BTCUSDT,ETHUSDT",
            pattern=r"^[A-Z0-9,]+$",
            max_length=250,
        ),
    ] = "BTCUSDT,ETHUSDT",
    lab: StrategyLabService = Depends(_get_lab),
) -> dict[str, Any]:
    """Run all Strategy Lab workers against selected symbols."""

    symbol_list = [
        symbol.strip()
        for symbol in symbols.split(",")
        if symbol.strip()
    ]

    # Prevent accidental exchange API fan-out.
    symbol_list = symbol_list[:20]

    results = await lab.evaluate_all(symbol_list)

    response: dict[str, list[dict[str, Any]]] = {}

    for strategy_name, evaluations in results.items():
        response[strategy_name] = []

        for evaluation in evaluations:
            entry: dict[str, Any] = {
                "symbol": evaluation.symbol,
                "evaluation_time": evaluation.evaluation_time.isoformat(),
                "has_signal": evaluation.signal is not None,
                "reason_codes": [
                    reason.value
                    for reason in evaluation.reason_codes
                ],
            }

            if evaluation.signal is not None:
                entry["signal"] = {
                    "signal_id": evaluation.signal.signal_id,
                    "strategy": evaluation.signal.strategy.value,
                    "side": evaluation.signal.side.value,
                    "confidence": evaluation.signal.confidence,
                    "reference_entry_price": str(
                        evaluation.signal.reference_entry_price
                    ),
                    "signal_time": evaluation.signal.signal_time.isoformat(),
                }

            response[strategy_name].append(entry)

    return {
        "last_run": (
            lab.last_run.isoformat()
            if lab.last_run
            else None
        ),
        "worker_count": len(lab.workers),
        "symbol_count": len(symbol_list),
        "results": response,
    }


@router.get("/workers")
async def get_lab_workers(
    lab: StrategyLabService = Depends(_get_lab),
) -> dict[str, Any]:
    """List active Strategy Lab workers with latest-run stats."""

    workers = []

    for worker in lab.workers:
        latest = lab.latest_results.get(
            worker.strategy_name,
            [],
        )

        signal_count = sum(
            1
            for evaluation in latest
            if evaluation.signal is not None
        )

        workers.append(
            {
                "name": worker.strategy_name,
                "last_signal_count": signal_count,
                "last_evaluation_count": len(latest),
            }
        )

    return {
        "workers": workers,
        "last_run": (
            lab.last_run.isoformat()
            if lab.last_run
            else None
        ),
    }


@router.get("/history")
def get_lab_history(
    limit: int = Query(default=100, ge=1, le=500),
    strategy: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None),
    repository: StrategyLabRepository = Depends(
        _get_lab_repository
    ),
) -> dict[str, Any]:
    """Return persisted Strategy Lab paper signals."""

    rows = repository.list_signals(
        limit=limit,
        strategy=strategy,
        symbol=symbol,
        status=status,
    )

    return {
        "count": len(rows),
        "signals": rows,
    }


@router.get("/performance")
def get_lab_performance(
    repository: StrategyLabRepository = Depends(
        _get_lab_repository
    ),
) -> dict[str, Any]:
    """Return current paper-signal performance marks by strategy."""

    strategies = repository.performance()

    return {
        "strategy_count": len(strategies),
        "strategies": strategies,
    }


@router.post("/mark")
async def mark_lab_signals(
    lab: StrategyLabService = Depends(_get_lab),
    repository: StrategyLabRepository = Depends(
        _get_lab_repository
    ),
    market_data: MarketDataService = Depends(
        _get_market_data
    ),
) -> dict[str, Any]:
    """Mark all OPEN Strategy Lab paper signals using current ticker prices."""

    open_signals = repository.list_signals(
        limit=10000,
        status="OPEN",
    )

    symbols = sorted(
        {
            str(row["symbol"])
            for row in open_signals
        }
    )

    prices: dict[str, Decimal] = {}
    errors: list[dict[str, str]] = []

    for symbol in symbols:
        try:
            ticker = await market_data.fetch_ticker(symbol)
            prices[symbol] = Decimal(
                str(ticker.last_price)
            )
        except Exception as exc:
            errors.append(
                {
                    "symbol": symbol,
                    "error": str(exc),
                }
            )

    updated = lab.mark_open_signals(prices)

    return {
        "open_signal_count": len(open_signals),
        "symbol_count": len(symbols),
        "priced_symbol_count": len(prices),
        "updated_signal_count": updated,
        "errors": errors,
    }