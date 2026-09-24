from fastapi import APIRouter

from app.bot.state import bot_state

router = APIRouter()


@router.get("/status")
def status() -> dict[str, str]:
    return {"bot_status": bot_state.status.value}
