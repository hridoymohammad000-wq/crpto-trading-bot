from collections import deque
from threading import Lock

from app.models.activity import SignalActivityResponse
from app.models.execution import ExecutionResult
from app.models.risk import RiskDecision
from app.models.signal import StrategySignal
from app.persistence import PersistenceDatabase


class ActivityRepository:
    """Signal activity repository with optional durable SQLite persistence.

    Tests and isolated services can still use the lightweight in-memory mode.
    Production wiring supplies PersistenceDatabase so signal history and
    submitted-order dedupe survive application restarts.
    """

    def __init__(
        self,
        max_signals: int = 500,
        *,
        persistence: PersistenceDatabase | None = None,
    ) -> None:
        self._signals: deque[SignalActivityResponse] = deque(maxlen=max_signals)
        self._index: dict[str, SignalActivityResponse] = {}
        self._lock = Lock()
        self._persistence = persistence

    @property
    def persistent(self) -> bool:
        return self._persistence is not None

    def record_signal(
        self,
        signal: StrategySignal,
        risk: RiskDecision | None = None,
        execution: ExecutionResult | None = None,
    ) -> None:
        item = SignalActivityResponse(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            strategy=signal.strategy,
            side=signal.side,
            signal_time=signal.signal_time,
            reference_entry_price=signal.reference_entry_price,
            confidence=signal.confidence,
            risk_status=risk.status if risk is not None else None,
            execution_status=execution.status if execution is not None else None,
            order_id=execution.order_id if execution is not None else None,
        )
        if self._persistence is not None:
            self._persistence.upsert_signal(item, risk=risk, execution=execution)

        with self._lock:
            existing = self._index.get(item.signal_id)
            if existing is not None:
                try:
                    self._signals.remove(existing)
                except ValueError:
                    pass
            self._signals.append(item)
            self._index[item.signal_id] = item
            valid_ids = {entry.signal_id for entry in self._signals}
            stale = [key for key in self._index if key not in valid_ids]
            for key in stale:
                self._index.pop(key, None)

    def list_signals(self, *, limit: int = 100) -> list[SignalActivityResponse]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        if self._persistence is not None:
            return self._persistence.list_signals(limit)
        with self._lock:
            values = list(self._signals)
        values.reverse()
        return values[:limit]

    def submitted_signal_ids(self) -> set[str]:
        if self._persistence is None:
            return set()
        return self._persistence.submitted_signal_ids()
