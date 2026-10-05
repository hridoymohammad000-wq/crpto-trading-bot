import logging
import os

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


def _first_value(*names: str) -> str | None:
    for name in names:
        value = getattr(settings, name, None)

        if value is None:
            value = os.getenv(name)

        if value is not None and str(value).strip():
            return str(value).strip()

    return None


class PriceActionTelegramNotifier:

    def __init__(self):
        self.bot_token = _first_value(
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_TOKEN",
            "BOT_TOKEN",
        )

        self.chat_id = _first_value(
            "TELEGRAM_CHAT_ID",
            "TELEGRAM_TARGET_CHAT_ID",
            "CHAT_ID",
        )

        self.enabled = bool(
            self.bot_token and self.chat_id
        )

        # Prevent same active setup being sent every 5 minutes.
        self._active_signal_keys: set[str] = set()

    @staticmethod
    def _key(signal) -> str:
        return (
            f"{signal.symbol}:"
            f"{signal.side}:"
            f"{signal.pattern}"
        )

    async def send_new_signals(self, signals) -> int:

        current_keys = {
            self._key(signal)
            for signal in signals
        }

        if not self.enabled:
            logger.warning(
                "Telegram signal alerts disabled: "
                "bot token/chat id not configured"
            )

            self._active_signal_keys = current_keys
            return 0

        new_signals = [
            signal
            for signal in signals
            if self._key(signal)
            not in self._active_signal_keys
        ]

        sent = 0

        for signal in new_signals:

            risk = abs(
                signal.entry - signal.stop_loss
            )

            tp1 = (
                signal.entry + risk
                if signal.side == "LONG"
                else signal.entry - risk
            )

            tp2 = (
                signal.entry + risk * 2
                if signal.side == "LONG"
                else signal.entry - risk * 2
            )

            emoji = (
                "🟢"
                if signal.side == "LONG"
                else "🔴"
            )

            message = (
                f"{emoji} PRICE ACTION SIGNAL\n\n"
                f"Symbol: {signal.symbol}\n"
                f"Side: {signal.side}\n"
                f"Score: {signal.score}/100\n"
                f"Pattern: {signal.pattern}\n\n"
                f"Entry: {signal.entry}\n"
                f"SL: {signal.stop_loss}\n"
                f"TP 1:1: {round(tp1, 8)}\n"
                f"TP 1:2: {round(tp2, 8)}\n\n"
                f"1H Bias: {signal.htf_bias}\n"
                f"15M Structure: {signal.structure_bias}\n\n"
                f"Reasons:\n"
                + "\n".join(
                    f"• {reason}"
                    for reason in signal.reasons
                )
                + "\n\nSignal only — execution OFF"
            )

            url = (
                f"https://api.telegram.org/"
                f"bot{self.bot_token}/sendMessage"
            )

            try:
                async with httpx.AsyncClient(
                    timeout=10.0
                ) as client:

                    response = await client.post(
                        url,
                        json={
                            "chat_id": self.chat_id,
                            "text": message,
                        },
                    )

                    response.raise_for_status()

                sent += 1

                logger.info(
                    "Telegram signal sent | %s %s",
                    signal.symbol,
                    signal.side,
                )

            except Exception:
                logger.exception(
                    "Telegram signal send failed | %s",
                    signal.symbol,
                )

        self._active_signal_keys = current_keys

        return sent

    async def send_result_updates(self, events: list[dict]) -> int:

        if not events:
            return 0

        if not self.enabled:
            return 0

        sent = 0

        for row in events:

            status = row.get("status")
            symbol = row.get("symbol")
            side = row.get("side")
            result_r = row.get("result_r")
            entry = row.get("entry")
            exit_price = row.get("exit_price")
            pattern = row.get("pattern")

            if status == "WIN":
                icon = "?"
                title = "TP HIT"
            elif status == "LOSS":
                icon = "?"
                title = "SL HIT"
            elif status == "EXPIRED":
                icon = "?"
                title = "SIGNAL EXPIRED"
            else:
                continue

            message = (
                f"{icon} PRICE ACTION RESULT\n\n"
                f"{title}\n"
                f"Symbol: {symbol}\n"
                f"Side: {side}\n"
                f"Pattern: {pattern}\n\n"
                f"Entry: {entry}\n"
                f"Exit: {exit_price}\n"
                f"Result: {result_r}R\n\n"
                f"Signal tracking only ? execution OFF"
            )

            url = (
                f"https://api.telegram.org/"
                f"bot{self.bot_token}/sendMessage"
            )

            try:
                async with httpx.AsyncClient(
                    timeout=10.0
                ) as client:

                    response = await client.post(
                        url,
                        json={
                            "chat_id": self.chat_id,
                            "text": message,
                        },
                    )

                    response.raise_for_status()

                sent += 1

                logger.info(
                    "Telegram result sent | %s %s %s",
                    symbol,
                    side,
                    status,
                )

            except Exception:
                logger.exception(
                    "Telegram result send failed | %s",
                    symbol,
                )

        return sent

