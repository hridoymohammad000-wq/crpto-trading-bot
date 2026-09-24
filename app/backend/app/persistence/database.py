from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Any, Iterator

from app.models.activity import ClosedTradeResponse, SignalActivityResponse
from app.models.execution import (
    ExecutionResult,
    ExecutionStatus,
    NON_TERMINAL_EXECUTION_STATUSES,
)
from app.models.risk import RiskDecision


class _PostgresConnectionAdapter:
    """Tiny compatibility layer for the SQLite-shaped persistence API."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> Any:
        return self._conn.execute(PersistenceDatabase._postgres_sql(sql), params)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self._conn.execute(statement)


class PersistenceDatabase:
    """Durable persistence with SQLite locally and PostgreSQL/Neon in deployment.

    DATABASE_URL selects PostgreSQL. Without it, the original SQLite behavior
    remains unchanged for local development and the existing test suite.
    """

    def __init__(self, path: str, database_url: str = "") -> None:
        self.path = Path(path)
        self.database_url = database_url.strip()
        self._schema_lock = Lock()

    @property
    def backend(self) -> str:
        return "postgresql" if self.database_url else "sqlite"

    @staticmethod
    def _postgres_sql(sql: str) -> str:
        # Project SQL uses DB-API qmark placeholders for SQLite. Psycopg uses %s.
        return sql.replace("?", "%s")

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        if self.database_url:
            from psycopg import connect
            from psycopg.rows import dict_row

            conn = connect(self.database_url, row_factory=dict_row)
            try:
                yield _PostgresConnectionAdapter(conn)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _schema_sql(self) -> str:
        user_default = "TRUE" if self.database_url else "1"
        return f"""
        CREATE TABLE IF NOT EXISTS signal_activity (
            signal_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            strategy TEXT NOT NULL,
            side TEXT NOT NULL,
            signal_time TEXT NOT NULL,
            reference_entry_price TEXT NOT NULL,
            confidence INTEGER NOT NULL,
            risk_status TEXT,
            risk_reason TEXT,
            execution_status TEXT,
            order_id TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            login_id TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            is_active BOOLEAN NOT NULL DEFAULT {user_default}
        );

        CREATE INDEX IF NOT EXISTS idx_signal_activity_time
            ON signal_activity(signal_time DESC);

        CREATE TABLE IF NOT EXISTS execution_submissions (
            signal_id TEXT PRIMARY KEY,
            execution_intent_id TEXT,
            risk_decision_id TEXT,
            request_hash TEXT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            status TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            order_id TEXT,
            order_link_id TEXT,
            quantity TEXT,
            price TEXT,
            stop_loss TEXT,
            take_profit TEXT,
            leverage TEXT,
            cumulative_filled_quantity TEXT,
            average_fill_price TEXT,
            message TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_execution_submitted_at
            ON execution_submissions(submitted_at DESC);

        CREATE TABLE IF NOT EXISTS closed_trades (
            trade_key TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity TEXT NOT NULL,
            entry_price TEXT,
            exit_price TEXT,
            realized_pnl TEXT NOT NULL,
            open_fee TEXT,
            close_fee TEXT,
            order_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            synced_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_closed_trades_updated_at
            ON closed_trades(updated_at DESC, created_at DESC);

        CREATE TABLE IF NOT EXISTS daily_risk_state (
            trading_day TEXT PRIMARY KEY,
            start_equity TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runtime_metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS persistence_write_probe (
            probe_id INTEGER PRIMARY KEY CHECK (probe_id = 1),
            checked_at TEXT NOT NULL
        );
        """

    def initialize(self) -> None:
        with self._schema_lock, self._connect() as conn:
            conn.executescript(self._schema_sql())
            self._ensure_execution_columns(conn)
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_execution_intent_id "
                "ON execution_submissions(execution_intent_id) "
                "WHERE execution_intent_id IS NOT NULL"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_execution_order_link_id "
                "ON execution_submissions(order_link_id) "
                "WHERE order_link_id IS NOT NULL"
            )

    def _ensure_execution_columns(self, conn: Any) -> None:
        if self.database_url:
            rows = conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'execution_submissions'
                """
            ).fetchall()
            existing = {str(row["column_name"]) for row in rows}
        else:
            rows = conn.execute("PRAGMA table_info(execution_submissions)").fetchall()
            existing = {str(row[1]) for row in rows}

        additions = {
            "execution_intent_id": "TEXT",
            "risk_decision_id": "TEXT",
            "request_hash": "TEXT",
            "cumulative_filled_quantity": "TEXT",
            "average_fill_price": "TEXT",
        }
        for column, column_type in additions.items():
            if column not in existing:
                conn.execute(
                    f"ALTER TABLE execution_submissions ADD COLUMN {column} {column_type}"
                )

    def health(self) -> dict[str, object]:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM signal_activity").fetchone()
            submitted = conn.execute(
                "SELECT COUNT(*) AS n FROM execution_submissions WHERE status='SUBMITTED'"
            ).fetchone()
            trades = conn.execute("SELECT COUNT(*) AS n FROM closed_trades").fetchone()
        return {
            "status": "ok",
            "database": self.backend,
            "path": str(self.path) if not self.database_url else None,
            "persisted_signals": int(row["n"]),
            "persisted_submitted_orders": int(submitted["n"]),
            "persisted_closed_trades": int(trades["n"]),
        }

    def writable_health(self) -> dict[str, object]:
        """Prove that the main SQLite database can accept a durable write.

        New exposure must never rely on a read-only health check. This probe
        writes and removes a single well-known row in the main database inside
        a normal transaction. Any lock, read-only filesystem, corruption, or
        other SQLite write failure is deliberately allowed to propagate so the
        caller can fail closed.
        """
        self.initialize()
        checked_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO persistence_write_probe (probe_id, checked_at)
                VALUES (1, ?)
                ON CONFLICT(probe_id) DO UPDATE SET checked_at=excluded.checked_at
                """,
                (checked_at,),
            )
            conn.execute(
                "DELETE FROM persistence_write_probe WHERE probe_id=1"
            )
        return {
            "status": "ok",
            "database": self.backend,
            "path": str(self.path) if not self.database_url else None,
            "writable": True,
            "checked_at": checked_at,
        }

    def upsert_signal(
        self,
        item: SignalActivityResponse,
        *,
        risk: RiskDecision | None = None,
        execution: ExecutionResult | None = None,
    ) -> None:
        self.initialize()
        now = datetime.now(timezone.utc).isoformat()
        risk_reason = risk.reason.value if risk is not None and risk.reason is not None else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO signal_activity (
                    signal_id, symbol, strategy, side, signal_time,
                    reference_entry_price, confidence, risk_status, risk_reason,
                    execution_status, order_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(signal_id) DO UPDATE SET
                    symbol=excluded.symbol,
                    strategy=excluded.strategy,
                    side=excluded.side,
                    signal_time=excluded.signal_time,
                    reference_entry_price=excluded.reference_entry_price,
                    confidence=excluded.confidence,
                    risk_status=excluded.risk_status,
                    risk_reason=excluded.risk_reason,
                    execution_status=excluded.execution_status,
                    order_id=excluded.order_id,
                    updated_at=excluded.updated_at
                """,
                (
                    item.signal_id,
                    item.symbol,
                    item.strategy.value,
                    item.side.value,
                    item.signal_time.isoformat(),
                    str(item.reference_entry_price),
                    item.confidence,
                    item.risk_status.value if item.risk_status is not None else None,
                    risk_reason,
                    item.execution_status.value if item.execution_status is not None else None,
                    item.order_id,
                    now,
                ),
            )
        if execution is not None:
            self.record_execution(execution)

    def list_signals(self, limit: int) -> list[SignalActivityResponse]:
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*, e.stop_loss, e.take_profit
                FROM signal_activity s
                LEFT JOIN execution_submissions e ON s.signal_id = e.signal_id
                ORDER BY s.signal_time DESC LIMIT ?
                """, (limit,)
            ).fetchall()
        from app.models.execution import ExecutionStatus
        from app.models.risk import RiskDecisionStatus
        from app.models.signal import SignalSide, StrategyName

        return [
            SignalActivityResponse(
                signal_id=row["signal_id"],
                symbol=row["symbol"],
                strategy=StrategyName(row["strategy"]),
                side=SignalSide(row["side"]),
                signal_time=datetime.fromisoformat(row["signal_time"]),
                reference_entry_price=Decimal(row["reference_entry_price"]),
                confidence=int(row["confidence"]),
                risk_status=RiskDecisionStatus(row["risk_status"]) if row["risk_status"] else None,
                execution_status=ExecutionStatus(row["execution_status"]) if row["execution_status"] else None,
                order_id=row["order_id"],
                stop_loss=Decimal(row["stop_loss"]) if row["stop_loss"] is not None else None,
                take_profit=Decimal(row["take_profit"]) if row["take_profit"] is not None else None,
            )
            for row in rows
        ]

    def record_execution(self, result: ExecutionResult) -> None:
        """Durably upsert one execution lifecycle state.

        The caller must persist PENDING before any external order side effect.
        Subsequent ACK/UNKNOWN/FILL transitions update the same signal row.
        """
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO execution_submissions (
                    signal_id, execution_intent_id, risk_decision_id, request_hash,
                    symbol, side, status, submitted_at, order_id, order_link_id,
                    quantity, price, stop_loss, take_profit, leverage,
                    cumulative_filled_quantity, average_fill_price, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(signal_id) DO UPDATE SET
                    execution_intent_id=COALESCE(excluded.execution_intent_id, execution_submissions.execution_intent_id),
                    risk_decision_id=COALESCE(excluded.risk_decision_id, execution_submissions.risk_decision_id),
                    request_hash=COALESCE(excluded.request_hash, execution_submissions.request_hash),
                    status=excluded.status,
                    submitted_at=excluded.submitted_at,
                    order_id=COALESCE(excluded.order_id, execution_submissions.order_id),
                    order_link_id=COALESCE(excluded.order_link_id, execution_submissions.order_link_id),
                    quantity=COALESCE(excluded.quantity, execution_submissions.quantity),
                    price=COALESCE(excluded.price, execution_submissions.price),
                    stop_loss=COALESCE(excluded.stop_loss, execution_submissions.stop_loss),
                    take_profit=COALESCE(excluded.take_profit, execution_submissions.take_profit),
                    leverage=COALESCE(excluded.leverage, execution_submissions.leverage),
                    cumulative_filled_quantity=COALESCE(excluded.cumulative_filled_quantity, execution_submissions.cumulative_filled_quantity),
                    average_fill_price=COALESCE(excluded.average_fill_price, execution_submissions.average_fill_price),
                    message=excluded.message
                """,
                (
                    result.signal_id,
                    result.execution_intent_id,
                    result.risk_decision_id,
                    result.request_hash,
                    result.symbol,
                    result.side.value,
                    result.status.value,
                    result.submitted_at.isoformat(),
                    result.order_id,
                    result.order_link_id,
                    str(result.quantity) if result.quantity is not None else None,
                    str(result.price) if result.price is not None else None,
                    str(result.stop_loss) if result.stop_loss is not None else None,
                    str(result.take_profit) if result.take_profit is not None else None,
                    str(result.leverage) if result.leverage is not None else None,
                    str(result.cumulative_filled_quantity) if result.cumulative_filled_quantity is not None else None,
                    str(result.average_fill_price) if result.average_fill_price is not None else None,
                    result.message,
                ),
            )

    def get_execution(self, signal_id: str) -> ExecutionResult | None:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM execution_submissions WHERE signal_id=?",
                (signal_id,),
            ).fetchone()
        return self._execution_from_row(row) if row is not None else None

    def unresolved_executions(self) -> list[ExecutionResult]:
        self.initialize()
        statuses = tuple(status.value for status in NON_TERMINAL_EXECUTION_STATUSES)
        placeholders = ",".join("?" for _ in statuses)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM execution_submissions WHERE status IN ({placeholders}) ORDER BY submitted_at ASC",
                statuses,
            ).fetchall()
        return [self._execution_from_row(row) for row in rows]

    def latest_execution_for_symbol(self, symbol: str) -> ExecutionResult | None:
        """Return the most recent durable execution intent for a symbol.

        Reconciliation uses this only as local expected-protection metadata.
        The exchange position remains the source of truth for actual protection.
        """
        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM execution_submissions
                WHERE symbol=?
                ORDER BY submitted_at DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchone()
        return self._execution_from_row(row) if row is not None else None

    @staticmethod
    def _execution_from_row(row: sqlite3.Row) -> ExecutionResult:
        from app.models.signal import SignalSide

        return ExecutionResult(
            status=ExecutionStatus(row["status"]),
            signal_id=row["signal_id"],
            execution_intent_id=row["execution_intent_id"],
            risk_decision_id=row["risk_decision_id"],
            request_hash=row["request_hash"],
            symbol=row["symbol"],
            side=SignalSide(row["side"]),
            submitted_at=datetime.fromisoformat(row["submitted_at"]),
            order_id=row["order_id"],
            order_link_id=row["order_link_id"],
            quantity=Decimal(row["quantity"]) if row["quantity"] is not None else None,
            price=Decimal(row["price"]) if row["price"] is not None else None,
            stop_loss=Decimal(row["stop_loss"]) if row["stop_loss"] is not None else None,
            take_profit=Decimal(row["take_profit"]) if row["take_profit"] is not None else None,
            leverage=Decimal(row["leverage"]) if row["leverage"] is not None else None,
            cumulative_filled_quantity=(
                Decimal(row["cumulative_filled_quantity"])
                if row["cumulative_filled_quantity"] is not None
                else None
            ),
            average_fill_price=(
                Decimal(row["average_fill_price"])
                if row["average_fill_price"] is not None
                else None
            ),
            message=row["message"],
        )

    def submitted_signal_ids(self) -> set[str]:
        """Return every signal that has ever created a durable execution intent.

        A signal is never automatically re-submitted after restart merely
        because its previous exchange attempt became terminal.
        """
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT signal_id FROM execution_submissions"
            ).fetchall()
        return {str(row["signal_id"]) for row in rows}

    def upsert_closed_trades(self, trades: list[ClosedTradeResponse]) -> None:
        self.initialize()
        synced_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for trade in trades:
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
                conn.execute(
                    """
                    INSERT INTO closed_trades (
                        trade_key, symbol, side, quantity, entry_price, exit_price,
                        realized_pnl, open_fee, close_fee, order_id, created_at,
                        updated_at, synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trade_key) DO UPDATE SET
                        side=excluded.side,
                        realized_pnl=excluded.realized_pnl,
                        open_fee=excluded.open_fee,
                        close_fee=excluded.close_fee,
                        updated_at=excluded.updated_at,
                        synced_at=excluded.synced_at
                    """,
                    (
                        trade_key,
                        trade.symbol,
                        trade.side,
                        str(trade.quantity),
                        str(trade.entry_price) if trade.entry_price is not None else None,
                        str(trade.exit_price) if trade.exit_price is not None else None,
                        str(trade.realized_pnl),
                        str(trade.open_fee) if trade.open_fee is not None else None,
                        str(trade.close_fee) if trade.close_fee is not None else None,
                        trade.order_id,
                        trade.created_at.isoformat() if trade.created_at else None,
                        trade.updated_at.isoformat() if trade.updated_at else None,
                        synced_at,
                    ),
                )

    def list_closed_trades(self, limit: int = 100) -> list[ClosedTradeResponse]:
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM closed_trades
                ORDER BY COALESCE(updated_at, created_at, synced_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            ClosedTradeResponse(
                symbol=row["symbol"],
                side=row["side"],
                quantity=Decimal(row["quantity"]),
                entry_price=Decimal(row["entry_price"]) if row["entry_price"] is not None else None,
                exit_price=Decimal(row["exit_price"]) if row["exit_price"] is not None else None,
                realized_pnl=Decimal(row["realized_pnl"]),
                open_fee=Decimal(row["open_fee"]) if row["open_fee"] is not None else None,
                close_fee=Decimal(row["close_fee"]) if row["close_fee"] is not None else None,
                order_id=row["order_id"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
            )
            for row in rows
        ]

    def get_daily_baseline(self, trading_day: date) -> Decimal | None:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT start_equity FROM daily_risk_state WHERE trading_day=?",
                (trading_day.isoformat(),),
            ).fetchone()
        return Decimal(row["start_equity"]) if row is not None else None

    def set_daily_baseline(self, trading_day: date, equity: Decimal) -> None:
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_risk_state(trading_day, start_equity, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(trading_day) DO UPDATE SET
                    start_equity=excluded.start_equity,
                    updated_at=excluded.updated_at
                """,
                (trading_day.isoformat(), str(equity), datetime.now(timezone.utc).isoformat()),
            )

    def set_metadata(self, key: str, value: str | None) -> None:
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runtime_metadata(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, datetime.now(timezone.utc).isoformat()),
            )

    def get_metadata(self, key: str) -> str | None:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM runtime_metadata WHERE key=?", (key,)).fetchone()
        return None if row is None else row["value"]

    def get_all_metadata(self) -> dict[str, str]:
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM runtime_metadata").fetchall()
        return {row["key"]: row["value"] for row in rows}
    def get_user_by_login_id(self, login_id: str) -> dict | None:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE login_id = ?", (login_id,)).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict | None:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def count_users(self) -> int:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute("SELECT count(*) AS n FROM users").fetchone()
            return int(row["n"])

    def create_user(self, user_id: str, login_id: str, password_hash: str) -> dict:
        self.initialize()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users (id, login_id, password_hash, created_at, is_active) VALUES (?, ?, ?, ?, ?)",
                (user_id, login_id, password_hash, now, True)
            )
        return self.get_user_by_id(user_id)

    def update_user_password(self, user_id: str, new_hash: str) -> None:
        self.initialize()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (new_hash, now, user_id)
            )
