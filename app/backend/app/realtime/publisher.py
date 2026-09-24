import asyncio
import logging
from decimal import Decimal
from typing import Any

from app.account import AccountService
from app.bot.runtime import BotRuntime
from app.market_data import MarketDataService
from app.models.candle import SupportedSymbol
from app.realtime.hub import RealtimeHub

logger = logging.getLogger(__name__)


def _num(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


class LiveSnapshotPublisher:
    def __init__(
        self,
        hub: RealtimeHub,
        market_data_service: MarketDataService,
        account_service: AccountService,
        bot_runtime: BotRuntime,
        *,
        symbols: tuple[SupportedSymbol, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT"),
        interval_seconds: float = 5.0,
    ) -> None:
        self._hub = hub
        self._market = market_data_service
        self._account = account_service
        self._runtime = bot_runtime
        self._symbols = symbols
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._previous_positions: dict[str, dict[str, Any]] = {}
        self._last_error: str | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="live-snapshot-publisher")

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            if self._hub.connection_count > 0:
                try:
                    await self.publish_snapshot()
                except Exception as exc:
                    logger.exception("Unexpected error in publish_snapshot")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except TimeoutError:
                pass

    async def publish_snapshot(self) -> None:
        await self._hub.publish(
            "bot_status",
            {
                "status": self._runtime.snapshot()["bot_status"].upper(),
                "isAutomatedExecutionEnabled": self._runtime.snapshot()["execution_enabled"],
            },
        )

        for symbol in self._symbols:
            try:
                ticker = await self._market.fetch_ticker(symbol)
                await self._hub.publish(
                    "price_update",
                    {
                        "symbol": symbol,
                        "price": _num(ticker.last_price),
                        "change24h": _num(ticker.price_change_24h_pct),
                        "high24h": _num(ticker.high_price_24h),
                        "low24h": _num(ticker.low_price_24h),
                        "volume24h": _num(ticker.volume_24h),
                    },
                )
            except Exception as exc:
                await self._publish_error_once("ticker", f"{symbol}: {type(exc).__name__}: {exc}")

        try:
            account = await self._account.get_summary()
            await self._hub.publish(
                "account_update",
                {
                    "balance": _num(account.balance),
                    "equity": _num(account.equity),
                    "availableBalance": _num(account.available_balance),
                    "dailyPnl": _num(account.unrealized_pnl) if account.unrealized_pnl is not None else 0.0,
                },
            )
        except Exception as exc:
            await self._publish_error_once("account", f"{type(exc).__name__}: {exc}")

        try:
            positions = await self._account.get_positions()
            current: dict[str, dict[str, Any]] = {}
            for row in positions:
                key = f"{row.symbol}:{row.side}"
                entry = _num(row.entry_price) or 0.0
                mark = _num(row.mark_price) or entry
                qty = float(row.size)
                value = _num(row.position_value) or (entry * qty)
                upl = _num(row.unrealized_pnl) or 0.0
                pnl_pct = (upl / value * 100.0) if value else 0.0
                payload = {
                    "id": key,
                    "symbol": row.symbol,
                    "side": row.side,
                    "entry": entry,
                    "current": mark,
                    "quantity": qty,
                    "positionValue": value,
                    "sl": _num(row.stop_loss) or 0.0,
                    "tp": _num(row.take_profit) or 0.0,
                    "unrealizedPnl": upl,
                    "pnlPercentage": pnl_pct,
                    "currentR": "0.00R",
                    "duration": "—",
                    "leverage": _num(row.leverage) or 1.0,
                    "riskAmount": 0.0,
                    "openedTime": "—",
                }
                current[key] = payload
                event = "position_opened" if key not in self._previous_positions else "position_updated"
                data = {"position": payload} if event == "position_opened" else {
                    "id": key,
                    "symbol": row.symbol,
                    "position": payload,
                    "current": mark,
                    "unrealizedPnl": upl,
                    "pnlPercentage": pnl_pct,
                    "sl": payload["sl"],
                    "tp": payload["tp"],
                }
                await self._hub.publish(event, data)
            for key, old in self._previous_positions.items():
                if key not in current:
                    await self._hub.publish("position_closed", {"id": key, "symbol": old["symbol"]})
            self._previous_positions = current
            self._last_error = None
        except Exception as exc:
            await self._publish_error_once("positions", f"{type(exc).__name__}: {exc}")

    async def _publish_error_once(self, category: str, message: str) -> None:
        if not hasattr(self, "_last_errors"):
            self._last_errors: dict[str, str] = {}
        if self._last_errors.get(category) == message:
            return
        self._last_errors[category] = message
        logger.warning("Live publisher error (%s): %s", category, message)
        await self._hub.publish(
            "system_event",
            {"level": "error", "message": f"Live data refresh error ({category})", "details": message},
        )
