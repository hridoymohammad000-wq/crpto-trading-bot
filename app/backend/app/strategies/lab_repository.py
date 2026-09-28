"""Durable paper-trade storage for Strategy Lab.

Strategy Lab remains isolated from executable signal/activity tables. The paper
lifecycle below never submits an exchange order. It uses a transparent research
benchmark of 1% paper risk and 2% paper target (2R) so open/win/loss statistics
are real lifecycle counts rather than floating positive/negative snapshots.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.models.signal import StrategySignal
from app.persistence import PersistenceDatabase

PAPER_STOP_PCT = Decimal("0.01")
PAPER_TARGET_PCT = Decimal("0.02")


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
                    stop_loss TEXT,
                    take_profit TEXT,
                    closed_at TEXT,
                    exit_reason TEXT,
                    diagnostic_reason TEXT,
                    adx TEXT,
                    rsi TEXT,
                    crossover_age_candles INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_strategy_lab_signal_time
                    ON strategy_lab_signals(signal_time DESC);

                CREATE INDEX IF NOT EXISTS idx_strategy_lab_strategy
                    ON strategy_lab_signals(strategy, signal_time DESC);
                """
            )
            self._ensure_columns(conn)
            self._backfill_levels(conn)

    def _ensure_columns(self, conn: Any) -> None:
        if self._persistence.database_url:
            rows = conn.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name='strategy_lab_signals'
                """
            ).fetchall()
            existing = {str(row["column_name"]) for row in rows}
        else:
            rows = conn.execute("PRAGMA table_info(strategy_lab_signals)").fetchall()
            existing = {str(row[1]) for row in rows}

        additions = {
            "stop_loss": "TEXT",
            "take_profit": "TEXT",
            "closed_at": "TEXT",
            "exit_reason": "TEXT",
            "diagnostic_reason": "TEXT",
            "adx": "TEXT",
            "rsi": "TEXT",
            "crossover_age_candles": "INTEGER",
        }
        for column, column_type in additions.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE strategy_lab_signals ADD COLUMN {column} {column_type}")


    def _backfill_levels(self, conn: Any) -> None:
        """Give pre-patch OPEN paper rows the same explicit 1%/2% benchmark levels."""
        rows = conn.execute(
            """
            SELECT signal_id, side, entry_price
            FROM strategy_lab_signals
            WHERE stop_loss IS NULL OR take_profit IS NULL
            """
        ).fetchall()
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            entry = Decimal(str(row["entry_price"]))
            if entry <= 0:
                continue
            if str(row["side"]).upper() == "BUY":
                stop_loss = entry * (Decimal("1") - PAPER_STOP_PCT)
                take_profit = entry * (Decimal("1") + PAPER_TARGET_PCT)
            else:
                stop_loss = entry * (Decimal("1") + PAPER_STOP_PCT)
                take_profit = entry * (Decimal("1") - PAPER_TARGET_PCT)
            conn.execute(
                """
                UPDATE strategy_lab_signals
                SET stop_loss=?, take_profit=?, updated_at=?
                WHERE signal_id=?
                """,
                (str(stop_loss), str(take_profit), now, row["signal_id"]),
            )

    @staticmethod
    def _paper_levels(signal: StrategySignal) -> tuple[Decimal, Decimal]:
        entry = signal.reference_entry_price
        if signal.side.value == "BUY":
            return entry * (Decimal("1") - PAPER_STOP_PCT), entry * (Decimal("1") + PAPER_TARGET_PCT)
        return entry * (Decimal("1") + PAPER_STOP_PCT), entry * (Decimal("1") - PAPER_TARGET_PCT)

    def save_signal(self, signal: StrategySignal) -> bool:
        """Persist one distinct paper trade. Returns True only for a new row."""
        self.initialize()
        now = datetime.now(timezone.utc).isoformat()
        stop_loss, take_profit = self._paper_levels(signal)

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
                    signal_id, strategy, symbol, side, signal_time, entry_price,
                    confidence, status, stop_loss, take_profit, adx, rsi,
                    crossover_age_candles, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.signal_id, signal.strategy.value, signal.symbol, signal.side.value,
                    signal.signal_time.isoformat(), str(signal.reference_entry_price),
                    signal.confidence, str(stop_loss), str(take_profit), str(signal.adx),
                    str(signal.rsi), signal.crossover_age_candles, now, now,
                ),
            )
        return True

    def update_mark(
        self,
        signal_id: str,
        *,
        current_price: Decimal,
        pnl_pct: Decimal,
        status: str = "OPEN",
        exit_reason: str | None = None,
        diagnostic_reason: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        closed_at = now if status != "OPEN" else None
        with self._persistence._connect() as conn:
            conn.execute(
                """
                UPDATE strategy_lab_signals
                SET current_price=?, pnl_pct=?, last_marked_at=?, status=?,
                    closed_at=COALESCE(?, closed_at),
                    exit_reason=COALESCE(?, exit_reason),
                    diagnostic_reason=COALESCE(?, diagnostic_reason),
                    updated_at=?
                WHERE signal_id=?
                """,
                (
                    str(current_price), str(pnl_pct), now, status, closed_at,
                    exit_reason, diagnostic_reason, now, signal_id,
                ),
            )

    def list_signals(
        self, *, limit: int = 100, strategy: str | None = None,
        symbol: str | None = None, status: str | None = None,
    ) -> list[dict[str, Any]]:
        self.initialize()
        clauses: list[str] = []
        params: list[Any] = []
        if strategy:
            clauses.append("strategy=?"); params.append(strategy.upper())
        if symbol:
            clauses.append("symbol=?"); params.append(symbol.upper())
        if status:
            clauses.append("status=?"); params.append(status.upper())
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        with self._persistence._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT signal_id, strategy, symbol, side, signal_time, entry_price,
                       confidence, status, current_price, pnl_pct, last_marked_at,
                       stop_loss, take_profit, closed_at, exit_reason, diagnostic_reason,
                       adx, rsi, crossover_age_candles
                FROM strategy_lab_signals
                {where}
                ORDER BY signal_time DESC
                LIMIT ?
                """, params,
            ).fetchall()
        return [dict(row) for row in rows]

    def performance(self) -> list[dict[str, Any]]:
        rows = self.list_signals(limit=10000)
        grouped: dict[str, dict[str, Any]] = {}

        for row in rows:
            strategy = str(row["strategy"])
            item = grouped.setdefault(strategy, {
                "strategy": strategy,
                "total_signals": 0,
                "total_trades": 0,
                "open_signals": 0,
                "closed_trades": 0,
                "wins": 0,
                "losses": 0,
                "sl_hits": 0,
                "tp_hits": 0,
                "expired": 0,
                "win_rate_pct": "0",
                "net_pnl_pct": "0",
                "avg_r": None,
                "marked_signals": 0,
                "positive_marks": 0,
                "negative_marks": 0,
                "avg_pnl_pct": None,
                "best_pnl_pct": None,
                "worst_pnl_pct": None,
                "last_signal_time": None,
            })
            item["total_signals"] += 1
            item["total_trades"] += 1
            status = str(row["status"])
            if status == "OPEN": item["open_signals"] += 1
            else: item["closed_trades"] += 1
            if status == "TP_HIT":
                item["wins"] += 1; item["tp_hits"] += 1
            elif status == "SL_HIT":
                item["losses"] += 1; item["sl_hits"] += 1
            elif status == "EXPIRED":
                item["expired"] += 1
            if item["last_signal_time"] is None:
                item["last_signal_time"] = row["signal_time"]

            raw_pnl = row["pnl_pct"]
            if raw_pnl is None:
                continue
            pnl = Decimal(str(raw_pnl))
            item["marked_signals"] += 1
            if pnl > 0: item["positive_marks"] += 1
            elif pnl < 0: item["negative_marks"] += 1
            item.setdefault("_mark_total", Decimal("0")); item["_mark_total"] += pnl
            if status != "OPEN":
                item.setdefault("_closed_total", Decimal("0")); item["_closed_total"] += pnl
            if item["best_pnl_pct"] is None or pnl > Decimal(str(item["best_pnl_pct"])):
                item["best_pnl_pct"] = str(pnl)
            if item["worst_pnl_pct"] is None or pnl < Decimal(str(item["worst_pnl_pct"])):
                item["worst_pnl_pct"] = str(pnl)

        for item in grouped.values():
            marked = int(item["marked_signals"])
            mark_total = item.pop("_mark_total", Decimal("0"))
            closed_total = item.pop("_closed_total", Decimal("0"))
            closed = int(item["closed_trades"])
            resolved = int(item["wins"]) + int(item["losses"])
            item["avg_pnl_pct"] = str(mark_total / marked) if marked else None
            item["net_pnl_pct"] = str(closed_total)
            item["win_rate_pct"] = str((Decimal(item["wins"]) / Decimal(resolved) * 100) if resolved else Decimal("0"))
            # 1R == the 1% paper stop benchmark.
            item["avg_r"] = str((closed_total / Decimal(closed)) / (PAPER_STOP_PCT * 100)) if closed else None

        return sorted(grouped.values(), key=lambda item: item["strategy"])
