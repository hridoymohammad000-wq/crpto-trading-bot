"""Strategy Lab API routes — multi-strategy signal aggregation."""

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Request

from app.models.signal import StrategyDiagnosticResponse
from app.strategies.lab_service import StrategyLabService

router = APIRouter(prefix="/strategy-lab", tags=["strategy-lab"])


def _get_lab(request: Request) -> StrategyLabService:
    return cast(StrategyLabService, request.app.state.strategy_lab_service)


@router.get("/signals")
async def get_lab_signals(
    symbols: Annotated[
        str,
        Query(
            description="Comma-separated list of symbols (e.g. BTCUSDT,ETHUSDT)",
            pattern=r"^[A-Z0-9,]+$",
        ),
    ] = "BTCUSDT,ETHUSDT",
    lab: StrategyLabService = Depends(_get_lab),
) -> dict[str, Any]:
    """Run all Strategy Lab workers against the given symbols and return results."""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    results = await lab.evaluate_all(symbol_list)

    response: dict[str, list[dict[str, Any]]] = {}
    for strategy_name, evaluations in results.items():
        response[strategy_name] = []
        for ev in evaluations:
            entry: dict[str, Any] = {
                "symbol": ev.symbol,
                "evaluation_time": ev.evaluation_time.isoformat(),
                "has_signal": ev.signal is not None,
                "reason_codes": [r.value for r in ev.reason_codes],
            }
            if ev.signal is not None:
                entry["signal"] = {
                    "signal_id": ev.signal.signal_id,
                    "side": ev.signal.side.value,
                    "confidence": ev.signal.confidence,
                    "reference_entry_price": str(ev.signal.reference_entry_price),
                    "signal_time": ev.signal.signal_time.isoformat(),
                }
            response[strategy_name].append(entry)

    return {
        "last_run": lab.last_run.isoformat() if lab.last_run else None,
        "worker_count": len(lab.workers),
        "symbol_count": len(symbol_list),
        "results": response,
    }


@router.get("/workers")
async def get_lab_workers(
    lab: StrategyLabService = Depends(_get_lab),
) -> dict[str, Any]:
    """List active Strategy Lab workers with their stats."""
    workers = []
    for w in lab.workers:
        latest = lab.latest_results.get(w.strategy_name, [])
        signal_count = sum(1 for ev in latest if ev.signal is not None)
        workers.append({
            "name": w.strategy_name,
            "last_signal_count": signal_count,
            "last_evaluation_count": len(latest),
        })

    return {
        "workers": workers,
        "last_run": lab.last_run.isoformat() if lab.last_run else None,
    }
