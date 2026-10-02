from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from app.exchange.bybit import BybitDemoClient
from app.models.activity import ClosedTradeResponse, TradeStatsResponse
from app.repositories import ActivityRepository
from app.persistence import PersistenceDatabase


class ActivityService:
    def __init__(
        self,
        exchange: BybitDemoClient,
        repository: ActivityRepository,
        persistence: PersistenceDatabase | None = None,
    ) -> None:
        self._exchange = exchange
        self._repository = repository
        self._persistence = persistence

    def list_signals(self, *, limit: int = 100):
        return self._repository.list_signals(limit=limit)

    @staticmethod
    def _trade_path_metrics(
        trade: ClosedTradeResponse,
        candles,
    ) -> dict:
        """Calculate deterministic MAE/MFE from closed 5m candle path.

        Only closed candles whose start time is at/after the recorded entry
        time and at/before the recorded exit time are considered.
        """
        entry = trade.entry_price
        exit_price = trade.exit_price
        start = trade.created_at
        end = trade.updated_at

        if entry is None or exit_price is None or start is None or end is None:
            return {"excursion_status": "HISTORICAL_DATA_UNAVAILABLE"}

        # Check if the candles provided cover the full trade window.
        sorted_candles = sorted((c for c in candles if c.is_closed), key=lambda c: c.start_time)
        if not sorted_candles:
            return {"excursion_status": "HISTORICAL_DATA_UNAVAILABLE"}
        
        # A partial window occurs if the earliest candle starts strictly after the trade started,
        # or if the latest candle starts strictly before the trade ended (with some tolerance).
        earliest_candle_start = sorted_candles[0].start_time
        latest_candle_start = sorted_candles[-1].start_time
        
        is_partial = earliest_candle_start > start
        
        path = [
            c for c in sorted_candles
            if c.start_time >= start and c.start_time <= end
        ]

        if not path:
            return {"excursion_status": "PARTIAL" if is_partial else "HISTORICAL_DATA_UNAVAILABLE"}

        side = str(trade.side).upper()

        if side == "LONG":
            favorable = max(path, key=lambda c: c.high)
            adverse = min(path, key=lambda c: c.low)

            mfe_price = favorable.high - entry
            mae_price = adverse.low - entry
        else:
            favorable = min(path, key=lambda c: c.low)
            adverse = max(path, key=lambda c: c.high)

            mfe_price = entry - favorable.low
            mae_price = entry - adverse.high

        mfe_pct = (mfe_price / entry * Decimal("100")) if entry else None
        mae_pct = (mae_price / entry * Decimal("100")) if entry else None

        risk = (
            abs(entry - trade.stop_loss)
            if trade.stop_loss is not None
            else None
        )

        mfe_r = (mfe_price / risk) if risk and risk > 0 else None
        mae_r = (mae_price / risk) if risk and risk > 0 else None

        # Reconstruct a 5m ATR(14) immediately before entry.
        before = [
            c for c in sorted_candles
            if c.start_time < start
        ][-15:]

        atr = None
        if len(before) >= 14:
            trs = []
            previous_close = None
            for candle in before:
                if previous_close is None:
                    tr = candle.high - candle.low
                else:
                    tr = max(
                        candle.high - candle.low,
                        abs(candle.high - previous_close),
                        abs(candle.low - previous_close),
                    )
                trs.append(tr)
                previous_close = candle.close

            if trs:
                atr = sum(trs[-14:], Decimal("0")) / Decimal("14")

        sl_distance_atr = (
            risk / atr
            if risk is not None and atr is not None and atr > 0
            else None
        )

        excursion_status = "PARTIAL" if is_partial else "COMPLETE"

        return {
            "mae_price": mae_price,
            "mfe_price": mfe_price,
            "mae_pct": mae_pct,
            "mfe_pct": mfe_pct,
            "mae_r": mae_r,
            "mfe_r": mfe_r,
            "sl_distance": risk,
            "sl_distance_atr": sl_distance_atr,
            "mae_at": adverse.start_time,
            "mfe_at": favorable.start_time,
            "excursion_status": excursion_status,
        }

    async def list_trades(self, *, limit: int = 100) -> list[ClosedTradeResponse]:
        rows = await self._exchange.get_closed_trades(limit=limit)
        trades = [
            ClosedTradeResponse(
                symbol=row.symbol,
                side=row.side,
                quantity=row.quantity,
                entry_price=row.entry_price,
                exit_price=row.exit_price,
                realized_pnl=row.realized_pnl,
                open_fee=row.open_fee,
                close_fee=row.close_fee,
                order_id=row.order_id,
                order_link_id=row.order_link_id,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        if self._persistence is not None:
            self._persistence.upsert_closed_trades(trades)

            # Enrich every newly synced trade with its 5m intratrade path.
            # Failure to reconstruct a path must never block trade syncing.
            # Fetch persisted trades to get their stop_loss which Bybit doesn't provide
            persisted_trades = self._persistence.list_closed_trades(limit=max(100, limit * 2))
            persisted_by_id = {t.order_id: t for t in persisted_trades if t.order_id}

            for api_trade in trades:
                try:
                    if api_trade.created_at is None or api_trade.updated_at is None:
                        continue

                    # Use the DB trade so we have the initial stop_loss for MAE-R calculations
                    trade = persisted_by_id.get(api_trade.order_id, api_trade)

                    candles = await self._exchange.get_candles(
                        trade.symbol,
                        "5m",
                        limit=1000,
                    )

                    metrics = self._trade_path_metrics(trade, candles)
                    if metrics:
                        trade_key = trade.order_id or "|".join(
                            [
                                trade.symbol,
                                trade.side,
                                str(trade.quantity),
                                str(trade.entry_price),
                                str(trade.exit_price),
                                trade.created_at.isoformat() if trade.created_at else "",
                                trade.updated_at.isoformat() if trade.updated_at else "",
                            ]
                        )
                        self._persistence.update_trade_path_metrics(
                            trade_key,
                            **metrics,
                        )
                except Exception:
                    # Diagnostic enrichment is best-effort; it must never
                    # prevent the primary closed-trade sync from succeeding.
                    continue

        return trades

    def list_persisted_trades(self, *, limit: int = 100) -> list[ClosedTradeResponse]:
        if self._persistence is None:
            return []
        return self._persistence.list_closed_trades(limit=limit)

    def get_persisted_trade_stats(self, *, limit: int = 100) -> TradeStatsResponse:
        return self._calculate_stats(self.list_persisted_trades(limit=limit))

    async def sync_closed_trades(self, *, limit: int = 100) -> int:
        """Fetch recent Bybit Demo closed trades and upsert them into SQLite.

        Persistence is idempotent because ``closed_trades.trade_key`` is the
        primary key and ``upsert_closed_trades`` uses ``ON CONFLICT``. Errors
        are intentionally allowed to propagate so the runtime caller can log
        them and apply its retry cadence without hiding failures.

        ``limit`` defaults to 100, matching the existing activity endpoint.
        This sync therefore covers the most recent window rather than doing
        historical pagination/backfill.
        """
        trades = await self.list_trades(limit=limit)
        return len(trades)

    async def get_trade_stats(self, *, limit: int = 100) -> TradeStatsResponse:
        trades = await self.list_trades(limit=limit)
        return self._calculate_stats(trades)

    @staticmethod
    def _calculate_stats(trades: list[ClosedTradeResponse]) -> TradeStatsResponse:
        total = len(trades)
        wins = sum(1 for trade in trades if trade.realized_pnl > 0)
        losses = sum(1 for trade in trades if trade.realized_pnl < 0)
        breakeven = total - wins - losses
        gross_profit = sum((trade.realized_pnl for trade in trades if trade.realized_pnl > 0), Decimal("0"))
        gross_loss = sum((trade.realized_pnl for trade in trades if trade.realized_pnl < 0), Decimal("0"))
        total_pnl = gross_profit + gross_loss
        average = total_pnl / Decimal(total) if total else Decimal("0")
        win_rate = (Decimal(wins) / Decimal(total) * Decimal("100")) if total else Decimal("0")
        profit_factor = gross_profit / abs(gross_loss) if gross_loss < 0 else None
        return TradeStatsResponse(
            total_trades=total,
            winning_trades=wins,
            losing_trades=losses,
            breakeven_trades=breakeven,
            win_rate_pct=win_rate,
            total_realized_pnl=total_pnl,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            average_pnl=average,
            profit_factor=profit_factor,
        )
