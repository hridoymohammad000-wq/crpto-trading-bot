from __future__ import annotations

import hashlib
import json
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from app.core.config import Settings

from app.exchange.bybit import BybitDemoClient
from app.exchange.bybit.exceptions import BybitAPIError, BybitConnectionError
from app.models.execution import ExecutionResult, ExecutionStatus
from app.models.risk import RiskDecision, RiskDecisionStatus
from app.persistence import PersistenceDatabase


class ExecutionService:
    """Single authority for opening Bybit Demo orders.

    A durable execution intent is written before the external order side effect
    when persistence is configured. Ambiguous network outcomes are never
    blindly retried; they are persisted as UNKNOWN_RECONCILING and must be
    resolved from exchange state using the deterministic orderLinkId.
    """

    def __init__(
        self,
        exchange: BybitDemoClient,
        persistence: PersistenceDatabase | None = None,
    ) -> None:
        self._exchange = exchange
        self._persistence = persistence

    async def execute(self, decision: RiskDecision) -> ExecutionResult:
        now = datetime.now(timezone.utc)
        if decision.status is not RiskDecisionStatus.READY:
            return ExecutionResult(
                status=ExecutionStatus.REJECTED,
                signal_id=decision.signal_id,
                symbol=decision.symbol,
                side=decision.side,
                submitted_at=now,
                message="Risk decision is not READY",
            )

        # New exposure requires durable local storage before any exchange-side
        # preparation or order request. Without persistence we cannot guarantee
        # idempotency or restart recovery, so fail closed.
        if self._persistence is None:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                signal_id=decision.signal_id,
                symbol=decision.symbol,
                side=decision.side,
                submitted_at=now,
                message="Persistence is required for new entry execution",
            )

        try:
            writable = self._persistence.writable_health()
            if not (
                writable.get("status") == "ok"
                and writable.get("writable") is True
            ):
                raise RuntimeError("persistence write probe did not confirm writable storage")
        except Exception as exc:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                signal_id=decision.signal_id,
                symbol=decision.symbol,
                side=decision.side,
                submitted_at=now,
                message=(
                    "Persistence is not writable; new entry blocked before exchange side effect. "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        required = (
            decision.quantity,
            decision.stop_loss,
            decision.take_profit,
            decision.leverage,
        )
        if any(value is None for value in required):
            return ExecutionResult(
                status=ExecutionStatus.REJECTED,
                signal_id=decision.signal_id,
                symbol=decision.symbol,
                side=decision.side,
                submitted_at=now,
                message="READY decision is missing execution fields",
            )

        assert decision.quantity is not None
        assert decision.stop_loss is not None
        assert decision.take_profit is not None
        assert decision.leverage is not None

        normalized = await self._exchange.normalize_order_values(
            symbol=decision.symbol,
            side="Buy" if decision.side.value == "BUY" else "Sell",
            quantity=decision.quantity,
            reference_entry_price=decision.entry,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
        )

        execution_intent_id = self._execution_intent_id(decision.signal_id)
        order_link_id = self._order_link_id(decision.signal_id)
        request_hash = self._request_hash(
            signal_id=decision.signal_id,
            symbol=decision.symbol,
            side=decision.side.value,
            quantity=normalized.quantity,
            entry=decision.entry,
            stop_loss=normalized.stop_loss,
            take_profit=normalized.take_profit,
            leverage=decision.leverage,
        )
        risk_decision_id = self._risk_decision_id(decision, request_hash)

        existing = (
            self._persistence.get_execution(decision.signal_id)
            if self._persistence is not None
            else None
        )
        if existing is not None:
            # Idempotency boundary: once a durable intent exists for this
            # signal, execute() never creates another exchange order.
            return existing

        pending = ExecutionResult(
            status=ExecutionStatus.PENDING,
            signal_id=decision.signal_id,
            execution_intent_id=execution_intent_id,
            risk_decision_id=risk_decision_id,
            request_hash=request_hash,
            symbol=decision.symbol,
            side=decision.side,
            submitted_at=now,
            order_link_id=order_link_id,
            quantity=normalized.quantity,
            price=decision.entry,
            stop_loss=normalized.stop_loss,
            take_profit=normalized.take_profit,
            leverage=decision.leverage,
            message="Durable execution intent created before exchange submission",
        )
        self._persist(pending)

        try:
            await self._exchange.set_leverage(decision.symbol, decision.leverage)
        except Exception as exc:
            failed = pending.model_copy(
                update={
                    "status": ExecutionStatus.FAILED,
                    "submitted_at": datetime.now(timezone.utc),
                    "message": f"Pre-submit leverage setup failed: {type(exc).__name__}: {exc}",
                }
            )
            self._persist(failed)
            return failed

        submitted = pending.model_copy(
            update={
                "status": ExecutionStatus.SUBMITTED,
                "submitted_at": datetime.now(timezone.utc),
                "message": "Order request is being submitted to Bybit Demo",
            }
        )
        self._persist(submitted)

        # Step A: Place the market entry order WITHOUT attaching final SL/TP.
        try:
            order = await self._exchange.place_order(
                symbol=decision.symbol,
                side="Buy" if decision.side.value == "BUY" else "Sell",
                quantity=normalized.quantity,
                stop_loss=None, # Two-step execution
                take_profit=None, # Two-step execution
                order_link_id=order_link_id,
                allow_unprotected_entry=True,
            )
        except BybitConnectionError as exc:
            unknown = submitted.model_copy(
                update={
                    "status": ExecutionStatus.UNKNOWN_RECONCILING,
                    "submitted_at": datetime.now(timezone.utc),
                    "message": (
                        "Ambiguous Bybit submit outcome; do not retry blindly. "
                        f"Resolve by orderLinkId. {type(exc).__name__}: {exc}"
                    ),
                }
            )
            self._persist(unknown)
            return unknown
        except BybitAPIError as exc:
            rejected = submitted.model_copy(
                update={
                    "status": ExecutionStatus.REJECTED,
                    "submitted_at": datetime.now(timezone.utc),
                    "message": f"Bybit rejected order request: {exc}",
                }
            )
            self._persist(rejected)
            return rejected
        except ValueError as exc:
            failed = submitted.model_copy(
                update={
                    "status": ExecutionStatus.FAILED,
                    "submitted_at": datetime.now(timezone.utc),
                    "message": f"Local execution validation failed: {exc}",
                }
            )
            self._persist(failed)
            return failed
        except Exception as exc:
            unknown = submitted.model_copy(
                update={
                    "status": ExecutionStatus.UNKNOWN_RECONCILING,
                    "submitted_at": datetime.now(timezone.utc),
                    "message": (
                        "Unexpected submit outcome is ambiguous; do not retry blindly. "
                        f"{type(exc).__name__}: {exc}"
                    ),
                }
            )
            self._persist(unknown)
            return unknown

        acknowledged = submitted.model_copy(
            update={
                "status": ExecutionStatus.ACKNOWLEDGED,
                "submitted_at": datetime.now(timezone.utc),
                "order_id": order.order_id,
                "order_link_id": order.order_link_id or order_link_id,
                "message": "Bybit Demo accepted the order request; awaiting fill data",
            }
        )
        self._persist(acknowledged)

        # Step B: Wait for fill and get actual_avg_fill_price
        fill_price = None
        filled_qty = Decimal("0")
        for _ in range(10):
            await asyncio.sleep(0.5)
            try:
                row = await self._exchange.get_order_by_link_id(
                    symbol=decision.symbol,
                    order_link_id=order_link_id,
                )
                if row and row.get("orderStatus") in ("Filled", "PartiallyFilled"):
                    fill_price_str = row.get("avgPrice")
                    if fill_price_str:
                        fill_price = Decimal(str(fill_price_str))
                    qty_str = row.get("cumExecQty")
                    if qty_str:
                        filled_qty = Decimal(str(qty_str))
                    if fill_price and fill_price > 0:
                        break
            except Exception as e:
                pass

        if not fill_price or fill_price <= 0:
            unknown = acknowledged.model_copy(
                update={
                    "status": ExecutionStatus.UNKNOWN_RECONCILING,
                    "message": "Market order sent but fill price not received. Position protection unverified.",
                }
            )
            self._persist(unknown)
            return unknown

        # Calculate Slippage
        intended_entry = decision.entry
        slippage_abs = (fill_price - intended_entry) if decision.side.value == "BUY" else (intended_entry - fill_price)
        slippage_pct = (slippage_abs / intended_entry) * 100

        # Validate Max Slippage
        settings = Settings()
        max_slippage = Decimal(settings.MAX_SLIPPAGE_PCT)
        if slippage_pct > max_slippage:
            # Slippage exceeded, emergency close
            try:
                await self._exchange.place_order(
                    symbol=decision.symbol,
                    side="Sell" if decision.side.value == "BUY" else "Buy",
                    quantity=filled_qty,
                    reduce_only=True,
                    order_link_id=f"close-{order_link_id}",
                )
            except Exception:
                pass
            failed = acknowledged.model_copy(
                update={
                    "status": ExecutionStatus.FAILED,
                    "message": f"Slippage exceeded limit ({slippage_pct:.2f}% > {max_slippage}%). Emergency closed.",
                    "average_fill_price": fill_price,
                    "cumulative_filled_quantity": filled_qty,
                    "slippage_abs": slippage_abs,
                    "slippage_pct": slippage_pct,
                }
            )
            self._persist(failed)
            return failed

        # Recalculate intended risk distance (absolute difference between signal price and intended stop loss)
        intended_risk_distance = abs(intended_entry - decision.stop_loss)
        
        # Calculate new SL and TP anchored to actual fill price
        if decision.side.value == "BUY":
            final_stop_loss = fill_price - intended_risk_distance
            final_take_profit = fill_price + (intended_risk_distance * decision.risk_reward_ratio)
        else:
            final_stop_loss = fill_price + intended_risk_distance
            final_take_profit = fill_price - (intended_risk_distance * decision.risk_reward_ratio)

        # Ensure correct formatting
        final_stop_loss = final_stop_loss.quantize(decision.stop_loss)
        final_take_profit = final_take_profit.quantize(decision.take_profit)

        # Actual Risk Amount calculation
        actual_risk_distance = abs(fill_price - final_stop_loss)
        actual_risk_amount = actual_risk_distance * filled_qty
        
        # Check against tolerance (account risk amount + max tolerance)
        max_allowed_risk = decision.max_open_risk_amount if decision.max_open_risk_amount else decision.risk_amount * Decimal("1.5")
        if actual_risk_amount > max_allowed_risk:
            # Risk too high due to slippage, emergency close
            try:
                await self._exchange.place_order(
                    symbol=decision.symbol,
                    side="Sell" if decision.side.value == "BUY" else "Buy",
                    quantity=filled_qty,
                    reduce_only=True,
                    order_link_id=f"close-risk-{order_link_id}",
                )
            except Exception:
                pass
            failed = acknowledged.model_copy(
                update={
                    "status": ExecutionStatus.FAILED,
                    "message": f"Actual risk amount {actual_risk_amount} exceeds limit {max_allowed_risk}. Emergency closed.",
                    "average_fill_price": fill_price,
                    "cumulative_filled_quantity": filled_qty,
                    "slippage_abs": slippage_abs,
                    "slippage_pct": slippage_pct,
                    "actual_risk_amount": actual_risk_amount,
                }
            )
            self._persist(failed)
            return failed

        # Final R:R validation (including taker fee assumption)
        taker_fee_rate = Decimal("0.00055") # 0.055% bybit standard
        fee_amount = (fill_price * filled_qty) * taker_fee_rate * 2 # Entry + Exit
        effective_profit = abs(final_take_profit - fill_price) * filled_qty - fee_amount
        effective_loss = actual_risk_amount + fee_amount
        
        final_rr = effective_profit / effective_loss if effective_loss > 0 else decision.risk_reward_ratio
        min_rr = Decimal(settings.MINIMUM_RR)
        
        if final_rr < min_rr:
            # RR degraded too much, emergency close
            try:
                await self._exchange.place_order(
                    symbol=decision.symbol,
                    side="Sell" if decision.side.value == "BUY" else "Buy",
                    quantity=filled_qty,
                    reduce_only=True,
                    order_link_id=f"close-rr-{order_link_id}",
                )
            except Exception:
                pass
            failed = acknowledged.model_copy(
                update={
                    "status": ExecutionStatus.FAILED,
                    "message": f"Final effective RR {final_rr:.2f} < {min_rr}. Emergency closed.",
                    "average_fill_price": fill_price,
                    "cumulative_filled_quantity": filled_qty,
                    "slippage_abs": slippage_abs,
                    "slippage_pct": slippage_pct,
                    "actual_risk_amount": actual_risk_amount,
                    "final_rr": final_rr,
                    "fees": fee_amount,
                }
            )
            self._persist(failed)
            return failed

        # Safety loop: Try to place the Trading Stop (SL/TP)
        stop_success = False
        for attempt in range(3):
            try:
                await self._exchange.set_trading_stop(
                    symbol=decision.symbol,
                    stop_loss=final_stop_loss,
                    take_profit=final_take_profit,
                )
                stop_success = True
                break
            except Exception as e:
                await asyncio.sleep(1.0)
                
        if not stop_success:
            # CRITICAL execution protection failure -> close position
            try:
                await self._exchange.place_order(
                    symbol=decision.symbol,
                    side="Sell" if decision.side.value == "BUY" else "Buy",
                    quantity=filled_qty,
                    reduce_only=True,
                    order_link_id=f"close-prot-{order_link_id}",
                )
            except Exception:
                pass
            failed = acknowledged.model_copy(
                update={
                    "status": ExecutionStatus.FAILED,
                    "message": "CRITICAL execution_protection_failure: Could not set SL/TP. Emergency closed.",
                    "average_fill_price": fill_price,
                    "cumulative_filled_quantity": filled_qty,
                    "slippage_abs": slippage_abs,
                    "slippage_pct": slippage_pct,
                    "actual_risk_amount": actual_risk_amount,
                    "final_rr": final_rr,
                }
            )
            self._persist(failed)
            return failed

        # Final success
        filled = acknowledged.model_copy(
            update={
                "status": ExecutionStatus.FILLED,
                "message": "Order filled and SL/TP applied successfully based on actual fill price.",
                "average_fill_price": fill_price,
                "cumulative_filled_quantity": filled_qty,
                "stop_loss": final_stop_loss,
                "take_profit": final_take_profit,
                "slippage_abs": slippage_abs,
                "slippage_pct": slippage_pct,
                "intended_risk_amount": decision.risk_amount,
                "actual_risk_amount": actual_risk_amount,
                "final_rr": final_rr,
                "fees": fee_amount,
            }
        )
        self._persist(filled)
        return filled

    async def recover_unresolved(self) -> list[ExecutionResult]:
        """Resolve durable non-terminal intents from Bybit state after restart.

        No order is submitted from this method. If exchange state cannot prove
        a terminal/known state, the intent remains UNKNOWN_RECONCILING.
        """
        if self._persistence is None:
            return []

        recovered: list[ExecutionResult] = []
        for intent in self._persistence.unresolved_executions():
            if not intent.order_link_id:
                unknown = intent.model_copy(
                    update={
                        "status": ExecutionStatus.UNKNOWN_RECONCILING,
                        "submitted_at": datetime.now(timezone.utc),
                        "message": "Unresolved intent has no orderLinkId; manual reconciliation required",
                    }
                )
                self._persist(unknown)
                recovered.append(unknown)
                continue

            try:
                row = await self._exchange.get_order_by_link_id(
                    symbol=intent.symbol,
                    order_link_id=intent.order_link_id,
                )
            except Exception as exc:
                unknown = intent.model_copy(
                    update={
                        "status": ExecutionStatus.UNKNOWN_RECONCILING,
                        "submitted_at": datetime.now(timezone.utc),
                        "message": f"Recovery lookup failed: {type(exc).__name__}: {exc}",
                    }
                )
                self._persist(unknown)
                recovered.append(unknown)
                continue

            if row is None:
                unknown = intent.model_copy(
                    update={
                        "status": ExecutionStatus.UNKNOWN_RECONCILING,
                        "submitted_at": datetime.now(timezone.utc),
                        "message": "No exchange order found for durable intent; no automatic resubmit",
                    }
                )
                self._persist(unknown)
                recovered.append(unknown)
                continue

            resolved = self._result_from_exchange_row(intent, row)
            self._persist(resolved)
            recovered.append(resolved)

        return recovered

    @staticmethod
    def _result_from_exchange_row(
        intent: ExecutionResult,
        row: dict[str, object],
    ) -> ExecutionResult:
        raw_status = str(row.get("orderStatus") or "")
        status_map = {
            "New": ExecutionStatus.ACKNOWLEDGED,
            "Created": ExecutionStatus.ACKNOWLEDGED,
            "Untriggered": ExecutionStatus.ACKNOWLEDGED,
            "PartiallyFilled": ExecutionStatus.PARTIALLY_FILLED,
            "Filled": ExecutionStatus.FILLED,
            "Cancelled": ExecutionStatus.CANCELLED,
            "Canceled": ExecutionStatus.CANCELLED,
            "Rejected": ExecutionStatus.REJECTED,
            "Deactivated": ExecutionStatus.CANCELLED,
        }
        mapped = status_map.get(raw_status, ExecutionStatus.UNKNOWN_RECONCILING)

        def decimal_or_none(value: object) -> Decimal | None:
            if value is None or value == "":
                return None
            try:
                return Decimal(str(value))
            except Exception:
                return None

        return intent.model_copy(
            update={
                "status": mapped,
                "submitted_at": datetime.now(timezone.utc),
                "order_id": (
                    str(row.get("orderId")) if row.get("orderId") else intent.order_id
                ),
                "cumulative_filled_quantity": decimal_or_none(row.get("cumExecQty")),
                "average_fill_price": decimal_or_none(row.get("avgPrice")),
                "message": f"Recovered from Bybit order state: {raw_status or 'UNKNOWN'}",
            }
        )

    async def get_positions(self) -> list[dict]:
        """Fetch open positions from the exchange."""
        return await self._exchange.get_positions()

    def _persist(self, result: ExecutionResult) -> None:
        if self._persistence is not None:
            self._persistence.record_execution(result)

    @staticmethod
    def _execution_intent_id(signal_id: str) -> str:
        digest = hashlib.sha256(signal_id.encode("utf-8")).hexdigest()
        return f"exec-{digest[:27]}"

    @staticmethod
    def _order_link_id(signal_id: str) -> str:
        digest = hashlib.sha256(signal_id.encode("utf-8")).hexdigest()
        return f"bot-{digest[:32]}"

    @staticmethod
    def _request_hash(
        *,
        signal_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        entry: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        leverage: Decimal,
    ) -> str:
        payload = {
            "signal_id": signal_id,
            "symbol": symbol,
            "side": side,
            "quantity": str(quantity),
            "entry": str(entry),
            "stop_loss": str(stop_loss),
            "take_profit": str(take_profit),
            "leverage": str(leverage),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _risk_decision_id(decision: RiskDecision, request_hash: str) -> str:
        raw = f"{decision.signal_id}|{request_hash}|{decision.status.value}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"risk-{digest[:27]}"
