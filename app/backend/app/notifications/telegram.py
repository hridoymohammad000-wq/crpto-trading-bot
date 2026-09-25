import asyncio
import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_telegram_message(message: str) -> None:
    """Send a text message to the configured Telegram chat."""
    token = settings.TELEGRAM_BOT_TOKEN.strip()
    chat_id = settings.TELEGRAM_CHAT_ID.strip()

    if not token or not chat_id:
        logger.debug("Telegram is not configured; skipping notification.")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )
        
        if resp.status_code != 200:
            logger.warning(
                "Failed to send Telegram message. HTTP %d: %s",
                resp.status_code,
                resp.text,
            )
        else:
            logger.info("Telegram notification sent successfully.")
    except Exception as exc:
        logger.error("Exception while sending Telegram message: %s", exc)

