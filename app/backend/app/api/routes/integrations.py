from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status")
async def integrations_status() -> dict:
    return {
        "backend": {"status": "connected"},
        "bybit": {
            "configured": bool(settings.BYBIT_API_KEY.strip() and settings.BYBIT_API_SECRET.strip()),
            "demo": bool(settings.BYBIT_DEMO),
        },
        "telegram": {
            "configured": bool(settings.TELEGRAM_BOT_TOKEN.strip() and settings.TELEGRAM_CHAT_ID.strip()),
        },
        "ai": {
            "enabled": bool(settings.AI_ENABLED),
            "configured": bool(settings.GROQ_API_KEY.strip()),
            "provider": settings.AI_PROVIDER,
            "model": settings.AI_MODEL,
        },
    }
