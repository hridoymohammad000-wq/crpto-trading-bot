from fastapi import APIRouter, Request
import httpx

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


@router.post("/test/backend")
async def test_backend() -> dict:
    return {"ok": True, "message": "Backend API is reachable"}


@router.post("/test/websocket")
async def test_websocket(request: Request) -> dict:
    hub = getattr(request.app.state, "realtime_hub", None)
    if hub is None:
        return {"ok": False, "message": "WebSocket hub not initialised"}
    return {"ok": True, "message": "WebSocket hub is active"}


@router.post("/test/bybit")
async def test_bybit(request: Request) -> dict:
    if not settings.BYBIT_API_KEY.strip() or not settings.BYBIT_API_SECRET.strip():
        return {"ok": False, "message": "Bybit API key / secret not configured"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api-demo.bybit.com/v5/market/time")

        if resp.status_code == 200:
            data = resp.json()
            ts = data.get("result", {}).get("timeSecond", "?")
            return {
                "ok": True,
                "message": f"Bybit Demo API reachable - server time: {ts}",
            }

        return {
            "ok": False,
            "message": f"Bybit Demo returned HTTP {resp.status_code}",
        }

    except httpx.TimeoutException:
        return {"ok": False, "message": "Bybit Demo API timed out"}

    except Exception as exc:
        return {"ok": False, "message": f"Bybit Demo connection failed: {exc}"}


@router.post("/test/telegram")
async def test_telegram() -> dict:
    token = settings.TELEGRAM_BOT_TOKEN.strip()
    chat_id = settings.TELEGRAM_CHAT_ID.strip()

    if not token or not chat_id:
        return {
            "ok": False,
            "message": "Telegram token / chat ID not configured",
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "Crypto Intraday Bot\n\nTelegram connection test successful.",
                },
            )

        data = resp.json()

        if resp.status_code == 200 and data.get("ok"):
            return {
                "ok": True,
                "message": "Telegram test message sent successfully",
            }

        return {
            "ok": False,
            "message": f"Telegram API error: {data.get('description', 'Unknown error')}",
        }

    except httpx.TimeoutException:
        return {"ok": False, "message": "Telegram API timed out"}

    except Exception as exc:
        return {
            "ok": False,
            "message": f"Telegram connection failed: {type(exc).__name__}: {exc}",
        }


@router.post("/test/ai")
async def test_ai(request: Request) -> dict:
    if not settings.AI_ENABLED:
        return {
            "ok": False,
            "message": "AI Analyst is disabled (AI_ENABLED=false)",
        }

    key = settings.GROQ_API_KEY.strip()

    if not key:
        return {"ok": False, "message": "GROQ_API_KEY not configured"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )

        if resp.status_code == 200:
            models = resp.json().get("data", [])
            return {
                "ok": True,
                "message": f"Groq API reachable - {len(models)} models available",
            }

        return {
            "ok": False,
            "message": f"Groq API returned HTTP {resp.status_code}",
        }

    except httpx.TimeoutException:
        return {"ok": False, "message": "Groq API timed out"}

    except Exception as exc:
        return {"ok": False, "message": f"Groq connection failed: {exc}"}
