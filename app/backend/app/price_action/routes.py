from fastapi import APIRouter, Request

router = APIRouter(
    prefix="/price-action",
    tags=["price-action"],
)


@router.get("/scan")
async def scan_price_action(
    request: Request,
):
    scanner = (
        request.app.state
        .price_action_scanner
    )

    result = await scanner.scan()

    return {
        "total_tickers":
            result.total_tickers,

        "eligible_symbols":
            result.eligible_symbols,

        "scanned_symbols":
            result.scanned_symbols,

        "failed_symbols":
            result.failed_symbols,

        "signal_count":
            len(result.signals),

        "long_count":
            sum(
                1
                for x in result.signals
                if x.side == "LONG"
            ),

        "short_count":
            sum(
                1
                for x in result.signals
                if x.side == "SHORT"
            ),

        "signals": [
            {
                "symbol": x.symbol,
                "side": x.side,
                "score": x.score,
                "entry": x.entry,
                "stop_loss":
                    x.stop_loss,
                "pattern":
                    x.pattern,
                "htf_bias":
                    x.htf_bias,
                "structure_bias":
                    x.structure_bias,
                "reasons":
                    list(x.reasons),
            }
            for x in result.signals
        ],
    }


@router.get("/history")
async def signal_history(
    request: Request,
):
    history = (
        request.app.state
        .price_action_auto_scanner
        .history
    )

    return {
        "summary":
            history.summary(),

        "signals":
            history.records(),
    }


@router.get("/history/summary")
async def signal_history_summary(
    request: Request,
):
    history = (
        request.app.state
        .price_action_auto_scanner
        .history
    )

    return history.summary()
