from typing import cast

from fastapi import APIRouter, HTTPException, Request, status

from app.bot.runtime import BotRuntime
from app.bot.leadership import RuntimeLeadershipError

router = APIRouter(prefix="/bot")


def get_runtime(request: Request) -> BotRuntime:
    return cast(BotRuntime, request.app.state.bot_runtime)


@router.post("/start")
async def start_bot(request: Request) -> dict[str, str]:
    runtime = get_runtime(request)
    try:
        await runtime.start()
    except RuntimeLeadershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return {"bot_status": runtime.snapshot()["bot_status"]}


@router.post("/stop")
async def stop_bot(request: Request) -> dict[str, str]:
    runtime = get_runtime(request)
    await runtime.stop()
    return {"bot_status": runtime.snapshot()["bot_status"]}


@router.get("/runtime")
def runtime_status(request: Request) -> dict[str, object]:
    return get_runtime(request).snapshot()
