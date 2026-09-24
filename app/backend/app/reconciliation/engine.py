import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.account import AccountService
from app.exchange.bybit.client import BybitDemoClient
from app.persistence import PersistenceDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ReconciliationStatus(str, Enum):
    SYNCED = "SYNCED"
    RECONCILING = "RECONCILING"
    ACCOUNT_UNAVAILABLE = "ACCOUNT_UNAVAILABLE"
    BALANCE_MISMATCH = "BALANCE_MISMATCH"
    POSITION_MISMATCH = "POSITION_MISMATCH"
    ORDER_MISMATCH = "ORDER_MISMATCH"
    TRADE_MISMATCH = "TRADE_MISMATCH"
    PROTECTION_MISMATCH = "PROTECTION_MISMATCH"
    LOCAL_STATE_STALE = "LOCAL_STATE_STALE"


class ReconciliationResult(BaseModel):
    status: ReconciliationStatus
    last_reconciled_at: datetime | None
    mismatches: list[str]
    warnings: list[str] = Field(default_factory=list)
    wallet: dict[str, Any]
    positions: dict[str, Any]
    orders: dict[str, Any]
    local_state: dict[str, Any]


class ReconciliationEngine:
    def __init__(
        self,
        account_service: AccountService,
        exchange_client: BybitDemoClient,
        persistence: PersistenceDatabase,
    ) -> None:
        self._account = account_service
        self._exchange = exchange_client
        self._persistence = persistence
        self._last_result: ReconciliationResult | None = None
        self._last_time: datetime | None = None
        self._status = ReconciliationStatus.RECONCILING
        self._has_completed_once = False
        self._lock = asyncio.Lock()

    @property
    def status(self) -> ReconciliationStatus:
        return self._status

    @property
    def has_completed_once(self) -> bool:
        return self._has_completed_once

    def is_safe(self) -> bool:
        return self._has_completed_once and self._status == ReconciliationStatus.SYNCED

    async def get_latest_result(self) -> ReconciliationResult:
        if self._last_result is None:
            await self.reconcile()
        assert self._last_result is not None
        return self._last_result

    async def reconcile(self) -> None:
        async with self._lock:
            self._status = ReconciliationStatus.RECONCILING
            mismatches: list[str] = []
            warnings: list[str] = []
            wallet_data: dict[str, Any] = {}
            positions_data: dict[str, Any] = {}
            orders_data: dict[str, Any] = {}
            local_data: dict[str, Any] = {}

            try:
                # 1. Fetch Bybit data
                try:
                    summary, positions, open_orders = await asyncio.gather(
                        self._account.get_summary(),
                        self._account.get_positions(),
                        self._account.get_open_orders(),
                    )
                except Exception as exc:
                    self._status = ReconciliationStatus.ACCOUNT_UNAVAILABLE
                    self._last_result = ReconciliationResult(
                        status=self._status,
                        last_reconciled_at=datetime.now(timezone.utc),
                        mismatches=[f"Failed to fetch account data: {exc}"],
                        warnings=[],
                        wallet={},
                        positions={},
                        orders={},
                        local_state={}
                    )
                    return

                # Build wallet data
                wallet_data = {
                    "balance": float(summary.balance) if summary.balance is not None else None,
                    "equity": float(summary.equity) if summary.equity is not None else None,
                    "margin_balance": float(summary.margin_balance) if summary.margin_balance is not None else None,
                    "available_margin": float(summary.available_margin) if summary.available_margin is not None else None,
                    "available": float(summary.available_balance) if summary.available_balance is not None else None,
                    "available_trading_capacity": float(summary.available_trading_capacity) if summary.available_trading_capacity is not None else None,
                    "initial_margin": float(summary.initial_margin) if summary.initial_margin is not None else None,
                    "maintenance_margin": float(summary.maintenance_margin) if summary.maintenance_margin is not None else None,
                    "unrealized_pnl": float(summary.unrealized_pnl) if summary.unrealized_pnl is not None else None,
                    "account_type": summary.account_type,
                    "unified_margin_status": summary.unified_margin_status,
                    "margin_mode": summary.margin_mode,
                    "capacity_source": summary.capacity_source,
                }

                # Build positions data
                for p in positions:
                    if p.size > 0:
                        positions_data[p.symbol] = {
                            "symbol": p.symbol,
                            "side": p.side,
                            "quantity": float(p.size),
                            "entry_price": float(p.entry_price) if p.entry_price else None,
                            "mark_price": float(p.mark_price) if p.mark_price else None,
                            "leverage": float(p.leverage) if p.leverage else None,
                            "stop_loss": float(p.stop_loss) if p.stop_loss else None,
                            "take_profit": float(p.take_profit) if p.take_profit else None,
                            "unrealized_pnl": float(p.unrealized_pnl) if p.unrealized_pnl else None,
                        }

                # Build orders data
                for order in open_orders:
                    order_id = str(order.get("orderId", ""))
                    if order_id:
                        orders_data[order_id] = {
                            "order_id": order_id,
                            "symbol": order.get("symbol"),
                            "side": order.get("side"),
                            "qty": float(order.get("qty", 0.0)),
                            "status": order.get("orderStatus"),
                            "reduceOnly": order.get("reduceOnly"),
                        }

                # 2. Fetch Local data
                try:
                    submitted_ids = list(self._persistence.submitted_signal_ids())
                    signals = [
                        {"signal_id": s.signal_id, "symbol": s.symbol, "side": s.side.value}
                        for s in self._persistence.list_signals(limit=100)
                    ]
                    closed_trades = [
                        {"order_id": t.order_id, "symbol": t.symbol, "realized_pnl": float(t.realized_pnl)}
                        for t in self._persistence.list_closed_trades(limit=100)
                    ]
                    daily_baseline = self._persistence.get_daily_baseline(datetime.now(timezone.utc).date())
                    metadata = self._persistence.get_all_metadata()
                    
                    local_data = {
                        "submitted_order_ids": submitted_ids,
                        "persisted_signals": signals,
                        "closed_trades": closed_trades,
                        "realized_pnl": sum(t["realized_pnl"] for t in closed_trades) if closed_trades else 0.0,
                        "daily_baseline": float(daily_baseline) if daily_baseline else None,
                        "runtime_metadata": metadata,
                    }
                except Exception as db_exc:
                    mismatches.append(f"Local DB read failure: {db_exc}")
                    self._status = ReconciliationStatus.LOCAL_STATE_STALE
                    self._last_result = ReconciliationResult(
                        status=self._status,
                        last_reconciled_at=datetime.now(timezone.utc),
                        mismatches=mismatches,
                        warnings=warnings,
                        wallet=wallet_data,
                        positions=positions_data,
                        orders=orders_data,
                        local_state=local_data
                    )
                    return

                # 3. Compare and Determine Status
                
                # Check for unexpected positions
                local_symbols = set()
                for s in signals:
                    local_symbols.add(s["symbol"])
                for t in closed_trades:
                    local_symbols.add(t["symbol"])

                # We could have a position mismatch if Bybit has a position we have NO local record for.
                for sym in positions_data:
                    if sym not in local_symbols:
                        mismatches.append(f"Position mismatch: {sym} is open on Bybit but has no local history.")

                # Verify actual exchange-side protective levels against the latest
                # durable execution intent for each locally managed open position.
                # A missing/mismatched SL is CRITICAL because downside protection
                # is not established. TP drift is WARNING-only: it must be surfaced
                # and repaired, but it is not equivalent to missing stop protection.
                for position in positions:
                    if position.size <= 0 or position.symbol not in local_symbols:
                        continue
                    expected = self._persistence.latest_execution_for_symbol(position.symbol)
                    if expected is None:
                        continue

                    if expected.stop_loss is not None:
                        if position.stop_loss is None or position.stop_loss <= 0:
                            mismatches.append(
                                f"Protection mismatch: {position.symbol} is missing required stop loss "
                                f"(expected {expected.stop_loss})."
                            )
                        elif position.stop_loss != expected.stop_loss:
                            mismatches.append(
                                f"Protection mismatch: {position.symbol} stop loss is {position.stop_loss} "
                                f"but local execution expects {expected.stop_loss}."
                            )

                    if expected.take_profit is not None:
                        if position.take_profit is None or position.take_profit <= 0:
                            warnings.append(
                                f"TP warning: {position.symbol} is missing take profit "
                                f"(expected {expected.take_profit})."
                            )
                        elif position.take_profit != expected.take_profit:
                            warnings.append(
                                f"TP warning: {position.symbol} take profit is {position.take_profit} "
                                f"but local execution expects {expected.take_profit}."
                            )

                # Check for unexpected open orders
                for oid, o in orders_data.items():
                    if o["symbol"] not in local_symbols and oid not in submitted_ids:
                        mismatches.append(f"Order mismatch: Order {oid} for {o['symbol']} exists on Bybit but has no local history.")

                if any("Protection mismatch" in m for m in mismatches):
                    self._status = ReconciliationStatus.PROTECTION_MISMATCH
                elif any("Position mismatch" in m for m in mismatches):
                    self._status = ReconciliationStatus.POSITION_MISMATCH
                elif any("Order mismatch" in m for m in mismatches):
                    self._status = ReconciliationStatus.ORDER_MISMATCH
                else:
                    self._status = ReconciliationStatus.SYNCED

                self._last_time = datetime.now(timezone.utc)
                self._last_result = ReconciliationResult(
                    status=self._status,
                    last_reconciled_at=self._last_time,
                    mismatches=mismatches,
                    warnings=warnings,
                    wallet=wallet_data,
                    positions=positions_data,
                    orders=orders_data,
                    local_state=local_data
                )

            except Exception as exc:
                logger.exception("Reconciliation engine error")
                self._status = ReconciliationStatus.LOCAL_STATE_STALE
                self._last_result = ReconciliationResult(
                    status=self._status,
                    last_reconciled_at=datetime.now(timezone.utc),
                    mismatches=[f"Unexpected error: {exc}"],
                    warnings=[],
                    wallet={},
                    positions={},
                    orders={},
                    local_state={}
                )
            finally:
                self._has_completed_once = self._last_result is not None

