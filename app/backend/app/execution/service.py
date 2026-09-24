from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

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

        try:
            order = await self._exchange.place_order(
                symbol=decision.symbol,
                side="Buy" if decision.side.value == "BUY" else "Sell",
                quantity=normalized.quantity,
                stop_loss=normalized.stop_loss,
                take_profit=normalized.take_profit,
                order_link_id=order_link_id,
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
                "message": "Bybit Demo accepted the order request; fill not yet assumed",
            }
        )
        self._persist(acknowledged)
        return acknowledged

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
