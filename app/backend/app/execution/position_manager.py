import logging
from decimal import Decimal
from datetime import datetime, timezone

from app.exchange.base import ExchangeClient
from app.persistence.database import PersistenceDatabase

logger = logging.getLogger(__name__)


class PositionManager:
    """Monitors open positions and moves SL to Break-Even once +1R is reached.

    Lifecycle:
        Called from BotRuntime._run_cycle() at the end of each cycle.
        No separate background loop or thread is created.

    Safety guarantees:
        - Never marks BE as SUCCESS without exchange confirmation AND position verification.
        - Never moves SL farther from entry (backwards).
        - Never submits duplicate BE amendments for already-successful positions.
        - Persists state so restarts can reconstruct without re-amending.
        - If amendment fails, original SL remains active on the exchange.
    """

    def __init__(self, exchange: ExchangeClient, persistence: PersistenceDatabase) -> None:
        self._exchange = exchange
        self._persistence = persistence

    async def manage_open_positions(self) -> None:
        """Scan all open positions and apply BE management where appropriate."""
        if not hasattr(self._exchange, "set_trading_stop"):
            return

        try:
            positions = await self._exchange.get_positions()
        except Exception as exc:
            logger.error("PositionManager: Failed to fetch positions: %s", exc)
            return

        for position in positions:
            try:
                await self._manage_position(position)
            except Exception as exc:
                logger.error(
                    "PositionManager: Error managing position %s: %s",
                    position.symbol, exc,
                )

    async def _manage_position(self, position) -> None:
        # Guard: need entry, mark, size, and SL to calculate R
        if (
            not position.entry_price
            or not position.mark_price
            or not position.size
            or not position.stop_loss
        ):
            return

        state = self._persistence.get_position_management_state(position.symbol)

        # Initialize state if not tracked
        if not state:
            state = {
                "symbol": position.symbol,
                "be_triggered": False,
                "be_trigger_price": None,
                "be_triggered_at": None,
                "original_stop_loss": position.stop_loss,
                "current_stop_loss": position.stop_loss,
                "be_order_id": None,
                "be_status": "MONITORING",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._persistence.upsert_position_management_state(state)

        # Already successfully applied — nothing to do
        if state.get("be_triggered") and state.get("be_status") == "SUCCESS":
            return

        # Calculate initial R from original SL
        entry = position.entry_price
        orig_sl = state["original_stop_loss"]
        if orig_sl is None:
            return

        risk = abs(entry - orig_sl)
        if risk <= 0:
            return

        # Use live mark price (NOT closed 5m candle)
        current_price = position.mark_price

        side = position.side.upper()

        # +1R trigger check (uses >= so exact +1R boundary triggers)
        if side == "BUY":
            reached_1r = current_price >= entry + risk
        else:  # SELL / SHORT
            reached_1r = current_price <= entry - risk

        if not reached_1r:
            return

        # --- +1R reached, attempt BE ---
        new_sl = entry

        # Safety: never move SL backwards (farther from entry than original)
        if side == "BUY" and orig_sl >= new_sl:
            return
        if side == "SELL" and orig_sl <= new_sl:
            return

        # Safety: if current_stop_loss is already at or past BE, skip
        current_sl = state.get("current_stop_loss")
        if current_sl is not None:
            if side == "BUY" and current_sl >= new_sl:
                return
            if side == "SELL" and current_sl <= new_sl:
                return

        # Step 1: Request BE amendment on exchange
        try:
            await self._exchange.set_trading_stop(
                symbol=position.symbol,
                stop_loss=new_sl,
            )
        except Exception as exc:
            logger.error(
                "PositionManager: Exchange amend request FAILED for %s: %s",
                position.symbol, exc,
            )
            from app.notifications.telegram import send_telegram_message
            import asyncio
            asyncio.ensure_future(send_telegram_message(f"🚨 <b>BE Modification Failure</b>\n\nFailed to move SL to BE for {position.symbol}.\nError: {exc}"))
            state.update({
                "be_status": "FAILED",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            self._persistence.upsert_position_management_state(state)
            return

        # Step 2: Verify actual position SL on exchange
        verified = False
        try:
            positions_after = await self._exchange.get_positions()
            for pos in positions_after:
                if pos.symbol == position.symbol and pos.stop_loss is not None:
                    # Tolerance: within 0.1% of entry price to account for tick rounding
                    diff = abs(pos.stop_loss - new_sl)
                    tolerance = max(new_sl * Decimal("0.001"), Decimal("0.01"))
                    if diff <= tolerance:
                        verified = True
                    break
        except Exception as exc:
            logger.warning(
                "PositionManager: Post-amend verification fetch failed for %s: %s",
                position.symbol, exc,
            )

        # Step 3: Persist based on verification result
        now = datetime.now(timezone.utc).isoformat()
        if verified:
            state.update({
                "be_triggered": True,
                "be_trigger_price": current_price,
                "be_triggered_at": now,
                "current_stop_loss": new_sl,
                "be_status": "SUCCESS",
                "updated_at": now,
            })
            self._persistence.upsert_position_management_state(state)
            logger.info(
                "PositionManager: VERIFIED — Moved %s SL to Break-Even at %s",
                position.symbol, new_sl,
            )
        else:
            state.update({
                "be_status": "VERIFICATION_FAILED",
                "updated_at": now,
            })
            self._persistence.upsert_position_management_state(state)
            logger.error(
                "PositionManager: Exchange accepted amend for %s but "
                "post-verification could not confirm SL == %s",
                position.symbol, new_sl,
            )
