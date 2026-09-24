from decimal import Decimal

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
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        if self._persistence is not None:
            self._persistence.upsert_closed_trades(trades)
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
