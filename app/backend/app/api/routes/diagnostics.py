"""Diagnostics routes — block report, blocker history."""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/block-report")
async def get_block_report(request: Request) -> dict:
    """Return today's trade-block summary.

    Shows how many times each blocker fired, which blocker is most common,
    and a 7-day history of daily block counts.
    """
    block_tracker = getattr(request.app.state, "block_tracker", None)
    if block_tracker is None:
        return {
            "error": "BlockTracker not initialised",
            "date": None,
            "total_signals_evaluated": 0,
            "total_trades_executed": 0,
            "total_blocked": 0,
            "block_rate_pct": 0.0,
            "block_counts": {},
            "top_blocker": None,
            "history": [],
        }
    return block_tracker.get_report()
