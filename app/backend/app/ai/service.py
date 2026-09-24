import json
from typing import Any

import httpx

from app.core.config import Settings


class AIAnalysisService:
    """Optional read-only AI analyst.

    This service has no reference to risk, readiness, execution, exchange order APIs,
    or the bot runtime. It can only transform a supplied snapshot into analysis text.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self._settings.AI_ENABLED)

    @property
    def configured(self) -> bool:
        return bool(self._settings.GROQ_API_KEY.strip())

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "provider": self._settings.AI_PROVIDER,
            "model": self._settings.AI_MODEL,
            "mode": "analysis_only",
        }

    async def analyze(self, context: dict[str, Any], question: str | None = None) -> str:
        if not self.enabled:
            raise RuntimeError("AI analyst is disabled")
        if not self.configured:
            raise RuntimeError("GROQ_API_KEY is not configured")
        if self._settings.AI_PROVIDER.lower() != "groq":
            raise RuntimeError("Unsupported AI_PROVIDER; this build is configured for Groq")

        instructions = (
            "You are a read-only trading analysis assistant for a Bybit Demo bot. "
            "Analyze only the supplied snapshot. Never claim to place or approve orders. "
            "Never instruct the system to bypass deterministic strategy, risk, readiness, "
            "reconciliation, or ExecutionService controls. Never change SL/TP. "
            "Clearly separate observations, risks, and questions to investigate."
        )
        user_payload = {
            "question": question or "Review this snapshot and identify useful observations and risks.",
            "snapshot": context,
        }

        url = f"{self._settings.AI_BASE_URL.rstrip('/')}/responses"
        headers = {
            "Authorization": f"Bearer {self._settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._settings.AI_MODEL,
            "instructions": instructions,
            "input": json.dumps(user_payload, default=str),
            "max_output_tokens": self._settings.AI_MAX_OUTPUT_TOKENS,
        }

        async with httpx.AsyncClient(timeout=self._settings.AI_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

        if isinstance(data.get("output_text"), str) and data["output_text"].strip():
            return data["output_text"].strip()

        parts: list[str] = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                    parts.append(content["text"])
        text = "\n".join(part.strip() for part in parts if part.strip())
        if not text:
            raise RuntimeError("AI provider returned no text output")
        return text
