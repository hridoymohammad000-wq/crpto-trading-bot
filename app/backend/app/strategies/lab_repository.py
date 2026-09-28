"""Durable paper-signal storage for Strategy Lab.

Strategy Lab data is intentionally isolated from executable signal/activity tables.
Nothing in this repository submits orders or changes demo execution state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.models.signal import StrategySignal
from app.persistence import PersistenceDatabase


class StrategyLabRepository:
    def __init__(self, persistence: PersistenceDatabase) -> None:
        self._persistence = persistence
        self.initialize()

    def initialize(self) -> None:
        with self._persistence._schema_lock, self._persistence._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS strategy_lab_signals (
                    signal_id TEXT PRIMARY KEY,
                    strategy TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    signal_time TEXT NOT NULL,
                    entry_price TEXT NOT NULL,
                    confidence INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    current_price TEXT,
                    pnl_pct TEXT,
                    last_marked_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_strategy_lab_signal_time
                    ON strategy_lab_signals(signal_time DESC);

                CREATE INDEX IF NOT EXISTS idx_strategy_lab_strategy
                    ON strategy_lab_signals(strategy, signal_time DESC);
                """
            )

    def save_signal(self, signal: StrategySignal) -> bool:
        """Persist a distinct paper signal. Returns True only for a new row."""
        self.initialize()
        now = datetime.now(timezone.utc).isoformat()

        with self._persistence._connect() as conn:
            existing = conn.execute(
                "SELECT signal_id FROM strategy_lab_signals WHERE signal_id=?",
                (signal.signal_id,),
            ).fetchone()

            if existing is not None:
                return False

            conn.execute(
                """
                INSERT INTO strategy_lab_signals (
                    signal_id,
                    strategy,
                    symbol,
                    side,
                    signal_time,
                    entry_price,
                    confidence,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
                """,
                (
                    signal.signal_id,
                    signal.strategy.value,
                    signal.symbol,
                    signal.side.value,
                    signal.signal_time.isoformat(),
                    str(signal.reference_entry_price),
                    signal.confidence,
                    now,
                    now,
                ),
            )

        return True

    def update_mark(
        self,
        signal_id: str,
        *,
        current_price: Decimal,
        pnl_pct: Decimal,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()

        with self._persistence._connect() as conn:
            conn.execute(
                """
                UPDATE strategy_lab_signals
                SET
                    current_price=?,
                    pnl_pct=?,
                    last_marked_at=?,
                    updated_at=?
                WHERE signal_id=?
                """,
                (
                    str(current_price),
                    str(pnl_pct),
                    now,
                    now,
                    signal_id,
                ),
            )

    def list_signals(
        self,
        *,
        limit: int = 100,
        strategy: str | None = None,
        symbol: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        self.initialize()

        clauses: list[str] = []
        params: list[Any] = []

        if strategy:
            clauses.append("strategy=?")
            params.append(strategy.upper())

        if symbol:
            clauses.append("symbol=?")
            params.append(symbol.upper())

        if status:
            clauses.append("status=?")
            params.append(status.upper())

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        params.append(limit)

        with self._persistence._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    signal_id,
                    strategy,
                    symbol,
                    side,
                    signal_time,
                    entry_price,
                    confidence,
                    status,
                    current_price,
                    pnl_pct,
                    last_marked_at
                FROM strategy_lab_signals
                {where}
                ORDER BY signal_time DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [dict(row) for row in rows]

    def performance(self) -> list[dict[str, Any]]:
        rows = self.list_signals(limit=10000)

        grouped: dict[str, dict[str, Any]] = {}

        for row in rows:
            strategy = str(row["strategy"])

            item = grouped.setdefault(
                strategy,
                {
                    "strategy": strategy,
                    "total_signals": 0,
                    "open_signals": 0,
                    "marked_signals": 0,
                    "positive_marks": 0,
                    "negative_marks": 0,
                    "avg_pnl_pct": None,
                    "best_pnl_pct": None,
                    "worst_pnl_pct": None,
                    "last_signal_time": None,
                },
            )

            item["total_signals"] += 1

            if row["status"] == "OPEN":
                item["open_signals"] += 1

            if item["last_signal_time"] is None:
                item["last_signal_time"] = row["signal_time"]

            raw_pnl = row["pnl_pct"]
            if raw_pnl is None:
                continue

            pnl = Decimal(str(raw_pnl))
            item["marked_signals"] += 1

            if pnl > 0:
                item["positive_marks"] += 1
            elif pnl < 0:
                item["negative_marks"] += 1

            item.setdefault("_pnl_total", Decimal("0"))
            item["_pnl_total"] += pnl

            if (
                item["best_pnl_pct"] is None
                or pnl > Decimal(str(item["best_pnl_pct"]))
            ):
                item["best_pnl_pct"] = str(pnl)

            if (
                item["worst_pnl_pct"] is None
                or pnl < Decimal(str(item["worst_pnl_pct"]))
            ):
                item["worst_pnl_pct"] = str(pnl)

        for item in grouped.values():
            marked = int(item["marked_signals"])
            total = item.pop("_pnl_total", Decimal("0"))
            item["avg_pnl_pct"] = str(total / marked) if marked else None

        return sorted(
            grouped.values(),
            key=lambda item: item["strategy"],
        )