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
            message TEXT,
            entry_timeframe TEXT,
            trend_timeframe TEXT,
            ema_fast TEXT,
            ema_slow TEXT,
            rsi TEXT,
            adx TEXT,
            atr TEXT,
            volume TEXT,
            average_volume TEXT,
            higher_tf_ema_fast TEXT,
            higher_tf_ema_slow TEXT,
            higher_tf_ema_fast_previous TEXT,
            crossover_age_candles INTEGER,
            signal_confidence INTEGER,
            slippage_abs TEXT,
            slippage_pct TEXT,
            intended_risk_amount TEXT,
            actual_risk_amount TEXT,
            final_rr TEXT,
            fees TEXT
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
            order_link_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            synced_at TEXT NOT NULL,
            strategy TEXT,
            stop_loss TEXT,
            take_profit TEXT,
            exit_reason TEXT,
            diagnostic_reason TEXT
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

        
        CREATE TABLE IF NOT EXISTS position_management (
            symbol TEXT PRIMARY KEY,
            be_triggered BOOLEAN NOT NULL DEFAULT FALSE,
            be_trigger_price TEXT,
            be_triggered_at TEXT,
            original_stop_loss TEXT,
            current_stop_loss TEXT,
            be_order_id TEXT,
            be_status TEXT NOT NULL,
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
            self._ensure_closed_trade_columns(conn)
            self._ensure_mae_mfe_columns(conn)
            self._ensure_indexes(conn)

    def _ensure_indexes(self, conn: Any) -> None:
        if self.database_url:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_order_link_id ON execution_submissions(order_link_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_order_id ON execution_submissions(order_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exec_symbol ON execution_submissions(symbol);")
        else:
            conn.executescript("""
                CREATE INDEX IF NOT EXISTS idx_exec_order_link_id ON execution_submissions(order_link_id);
                CREATE INDEX IF NOT EXISTS idx_exec_order_id ON execution_submissions(order_id);
                CREATE INDEX IF NOT EXISTS idx_exec_symbol ON execution_submissions(symbol);
            """)


    def _ensure_mae_mfe_columns(self, conn: Any) -> None:
        """Additive migration for persisted intratrade diagnostics."""
        if self.database_url:
            rows = conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'closed_trades'
                """
            ).fetchall()
            existing = {str(row["column_name"]) for row in rows}
        else:
            existing = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(closed_trades)").fetchall()
            }

        columns = {
            "mae_price": "TEXT",
            "mfe_price": "TEXT",
            "mae_pct": "TEXT",
            "mfe_pct": "TEXT",
            "mae_r": "TEXT",
            "mfe_r": "TEXT",
            "sl_distance": "TEXT",
            "sl_distance_atr": "TEXT",
            "mae_at": "TEXT",
            "mfe_at": "TEXT",
            "root_cause": "TEXT",
            "root_cause_evidence": "TEXT",
            "excursion_status": "TEXT",
        }

        for name, sql_type in columns.items():
            if name not in existing:
                conn.execute(
                    f"ALTER TABLE closed_trades ADD COLUMN {name} {sql_type}"
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
            "entry_timeframe": "TEXT",
            "trend_timeframe": "TEXT",
            "ema_fast": "TEXT",
            "ema_slow": "TEXT",
            "rsi": "TEXT",
            "adx": "TEXT",
            "atr": "TEXT",
            "volume": "TEXT",
            "average_volume": "TEXT",
            "higher_tf_ema_fast": "TEXT",
            "higher_tf_ema_slow": "TEXT",
            "higher_tf_ema_fast_previous": "TEXT",
            "crossover_age_candles": "INTEGER",
            "signal_confidence": "INTEGER",
            "slippage_abs": "TEXT",
            "slippage_pct": "TEXT",
            "intended_risk_amount": "TEXT",
            "actual_risk_amount": "TEXT",
            "final_rr": "TEXT",
            "fees": "TEXT",
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

    def _ensure_closed_trade_columns(self, conn: Any) -> None:
        if self.database_url:
            rows = conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'closed_trades'
                """
            ).fetchall()
            existing = {str(row["column_name"]) for row in rows}
        else:
            rows = conn.execute("PRAGMA table_info(closed_trades)").fetchall()
            existing = {str(row[1]) for row in rows}

        additions = {
            "strategy": "TEXT",
            "stop_loss": "TEXT",
            "take_profit": "TEXT",
            "exit_reason": "TEXT",
            "diagnostic_reason": "TEXT",
            "order_link_id": "TEXT",
        }
        for column, column_type in additions.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE closed_trades ADD COLUMN {column} {column_type}")

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
                    cumulative_filled_quantity, average_fill_price, message,
                    slippage_abs, slippage_pct, intended_risk_amount, actual_risk_amount, final_rr, fees
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    message=excluded.message,
                    slippage_abs=COALESCE(excluded.slippage_abs, execution_submissions.slippage_abs),
                    slippage_pct=COALESCE(excluded.slippage_pct, execution_submissions.slippage_pct),
                    intended_risk_amount=COALESCE(excluded.intended_risk_amount, execution_submissions.intended_risk_amount),
                    actual_risk_amount=COALESCE(excluded.actual_risk_amount, execution_submissions.actual_risk_amount),
                    final_rr=COALESCE(excluded.final_rr, execution_submissions.final_rr),
                    fees=COALESCE(excluded.fees, execution_submissions.fees)
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
                    str(result.slippage_abs) if result.slippage_abs is not None else None,
                    str(result.slippage_pct) if result.slippage_pct is not None else None,
                    str(result.intended_risk_amount) if result.intended_risk_amount is not None else None,
                    str(result.actual_risk_amount) if result.actual_risk_amount is not None else None,
                    str(result.final_rr) if result.final_rr is not None else None,
                    str(result.fees) if result.fees is not None else None,
                ),
            )

    def attach_signal_snapshot(self, signal) -> None:
        """Persist immutable entry-time strategy context for later diagnostics."""
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE execution_submissions
                SET
                    entry_timeframe=?,
                    trend_timeframe=?,
                    ema_fast=?,
                    ema_slow=?,
                    rsi=?,
                    adx=?,
                    atr=?,
                    volume=?,
                    average_volume=?,
                    higher_tf_ema_fast=?,
                    higher_tf_ema_slow=?,
                    higher_tf_ema_fast_previous=?,
                    crossover_age_candles=?,
                    signal_confidence=?
                WHERE signal_id=?
                """,
                (
                    signal.entry_timeframe,
                    signal.trend_timeframe,
                    str(signal.ema_fast),
                    str(signal.ema_slow),
                    str(signal.rsi),
                    str(signal.adx),
                    str(signal.atr) if signal.atr is not None else None,
                    str(signal.volume),
                    str(signal.average_volume),
                    str(signal.higher_tf_ema_fast),
                    str(signal.higher_tf_ema_slow),
                    str(signal.higher_tf_ema_fast_previous),
                    int(signal.crossover_age_candles),
                    int(signal.confidence),
                    signal.signal_id,
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
            slippage_abs=Decimal(row["slippage_abs"]) if "slippage_abs" in row.keys() and row["slippage_abs"] is not None else None,
            slippage_pct=Decimal(row["slippage_pct"]) if "slippage_pct" in row.keys() and row["slippage_pct"] is not None else None,
            intended_risk_amount=Decimal(row["intended_risk_amount"]) if "intended_risk_amount" in row.keys() and row["intended_risk_amount"] is not None else None,
            actual_risk_amount=Decimal(row["actual_risk_amount"]) if "actual_risk_amount" in row.keys() and row["actual_risk_amount"] is not None else None,
            final_rr=Decimal(row["final_rr"]) if "final_rr" in row.keys() and row["final_rr"] is not None else None,
            fees=Decimal(row["fees"]) if "fees" in row.keys() and row["fees"] is not None else None,
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
                trade_order_link_id = getattr(trade, "order_link_id", None)
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
                        realized_pnl, open_fee, close_fee, order_id, order_link_id,
                        created_at, updated_at, synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trade_key) DO UPDATE SET
                        side=excluded.side,
                        realized_pnl=excluded.realized_pnl,
                        open_fee=excluded.open_fee,
                        close_fee=excluded.close_fee,
                        order_link_id=COALESCE(excluded.order_link_id, closed_trades.order_link_id),
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
                        trade.order_link_id if hasattr(trade, 'order_link_id') else None,
                        trade.created_at.isoformat() if trade.created_at else None,
                        trade.updated_at.isoformat() if trade.updated_at else None,
                        synced_at,
                    ),
                )
                if trade_order_link_id:
                    try:
                        conn.execute(
                            "UPDATE closed_trades SET order_link_id=? WHERE trade_key=? AND order_link_id IS NULL",
                            (trade_order_link_id, trade_key),
                        )
                    except Exception:
                        pass

    @staticmethod
    def _diagnose_sl_root_cause(
        execution: Any | None,
        *,
        side: str,
    ) -> str:
        """Explain an SL hit from persisted entry-time facts only.

        The result is deterministic. It never claims a cause when the
        supporting entry snapshot is unavailable.
        """
        if execution is None:
            return (
                "Primary: UNKNOWN_INSUFFICIENT_EVIDENCE | "
                "Evidence: no matched execution snapshot was available."
            )

        def dec(name: str) -> Decimal | None:
            try:
                value = execution[name]
            except Exception:
                return None
            if value in (None, ""):
                return None
            try:
                return Decimal(str(value))
            except Exception:
                return None

        def integer(name: str) -> int | None:
            try:
                value = execution[name]
            except Exception:
                return None
            if value in (None, ""):
                return None
            try:
                return int(value)
            except Exception:
                return None

        rsi = dec("rsi")
        adx = dec("adx")
        atr_value = dec("atr")
        execution_entry = dec("price")
        execution_stop = dec("stop_loss")
        volume = dec("volume")
        average_volume = dec("average_volume")
        ema_fast = dec("ema_fast")
        ema_slow = dec("ema_slow")
        htf_fast = dec("higher_tf_ema_fast")
        htf_slow = dec("higher_tf_ema_slow")
        crossover_age = integer("crossover_age_candles")
        confidence = integer("signal_confidence")

        has_snapshot = any(
            value is not None
            for value in (
                rsi,
                adx,
                atr_value,
                volume,
                average_volume,
                ema_fast,
                ema_slow,
                htf_fast,
                htf_slow,
                crossover_age,
                confidence,
            )
        )

        if not has_snapshot:
            return (
                "Primary: UNKNOWN_INSUFFICIENT_EVIDENCE | "
                "Evidence: this historical trade has no persisted entry-time diagnostic snapshot."
            )

        reasons: list[str] = []
        evidence: list[str] = []

        if (
            atr_value is not None
            and atr_value > 0
            and execution_entry is not None
            and execution_stop is not None
        ):
            stop_distance = abs(execution_entry - execution_stop)
            stop_atr_ratio = stop_distance / atr_value

            evidence.append(f"ATR={atr_value}")
            evidence.append(f"stop_distance={stop_distance}")
            evidence.append(f"stop_ATR={stop_atr_ratio:.2f}x")

            if stop_atr_ratio < Decimal("1"):
                reasons.append("SL_TOO_TIGHT_FOR_ATR")

        if adx is not None:
            evidence.append(f"ADX={adx}")
            if adx < Decimal("20"):
                reasons.append("LOW_ADX_RANGING_MARKET")

        if crossover_age is not None:
            evidence.append(f"crossover_age={crossover_age}")
            if crossover_age >= 2:
                reasons.append("LATE_ENTRY")

        if volume is not None and average_volume is not None and average_volume > 0:
            volume_ratio = volume / average_volume
            evidence.append(f"volume_ratio={volume_ratio:.2f}")
            if volume_ratio < Decimal("1"):
                reasons.append("LOW_VOLUME_CONFIRMATION")

        if rsi is not None:
            evidence.append(f"RSI={rsi}")
            if side == "LONG" and rsi >= Decimal("70"):
                reasons.append("OVEREXTENDED_RSI")
            elif side == "SHORT" and rsi <= Decimal("30"):
                reasons.append("OVEREXTENDED_RSI")

        if htf_fast is not None and htf_slow is not None:
            evidence.append(f"HTF_EMA_fast={htf_fast}")
            evidence.append(f"HTF_EMA_slow={htf_slow}")

            if side == "LONG" and htf_fast <= htf_slow:
                reasons.append("COUNTER_TREND_ENTRY")
            elif side == "SHORT" and htf_fast >= htf_slow:
                reasons.append("COUNTER_TREND_ENTRY")

        if ema_fast is not None and ema_slow is not None:
            evidence.append(f"EMA_fast={ema_fast}")
            evidence.append(f"EMA_slow={ema_slow}")

            if side == "LONG" and ema_fast <= ema_slow:
                reasons.append("MOMENTUM_REVERSAL")
            elif side == "SHORT" and ema_fast >= ema_slow:
                reasons.append("MOMENTUM_REVERSAL")

        if confidence is not None:
            evidence.append(f"confidence={confidence}%")

        # Keep first occurrence only while preserving priority order.
        reasons = list(dict.fromkeys(reasons))

        if not reasons:
            reasons = ["UNKNOWN_INSUFFICIENT_EVIDENCE"]

        primary = reasons[0]
        secondary = reasons[1:]

        parts = [f"Primary: {primary}"]

        if secondary:
            parts.append("Secondary: " + ", ".join(secondary))

        if evidence:
            parts.append("Evidence: " + "; ".join(evidence))

        return " | ".join(parts)

    def update_trade_path_metrics(
        self,
        trade_key: str,
        *,
        mae_price: Decimal | None = None,
        mfe_price: Decimal | None = None,
        mae_pct: Decimal | None = None,
        mfe_pct: Decimal | None = None,
        mae_r: Decimal | None = None,
        mfe_r: Decimal | None = None,
        sl_distance: Decimal | None = None,
        sl_distance_atr: Decimal | None = None,
        mae_at: datetime | None = None,
        mfe_at: datetime | None = None,
        excursion_status: str | None = None,
    ) -> None:
        self.initialize()
        with self._connect() as conn:
            # 1) Get the trade
            row = conn.execute("SELECT * FROM closed_trades WHERE trade_key=?", (trade_key,)).fetchone()
            if not row:
                return
            
            realized_pnl = Decimal(str(row["realized_pnl"]))
            side = str(row["side"])

            # 2) Get the execution for entry-time evidence
            execution = None
            if row["order_id"]:
                execution = conn.execute(
                    "SELECT * FROM execution_submissions WHERE order_id=? ORDER BY submitted_at DESC LIMIT 1",
                    (row["order_id"],),
                ).fetchone()
            if not execution:
                closed_at = row["updated_at"] or row["created_at"] or row["synced_at"]
                execution = conn.execute(
                    "SELECT * FROM execution_submissions WHERE symbol=? AND CAST(quantity AS REAL)=CAST(? AS REAL) AND submitted_at<=? ORDER BY submitted_at DESC LIMIT 1",
                    (row["symbol"], row["quantity"], closed_at),
                ).fetchone()

            # 3) Gather base entry-time reasons and evidence
            entry_reason_str = self._diagnose_sl_root_cause(execution, side=side)
            
            # Extract basic parts
            primary_cause = "UNKNOWN_INSUFFICIENT_EVIDENCE"
            evidence_parts = []
            
            if "Primary: " in entry_reason_str:
                primary_cause = entry_reason_str.split("Primary: ")[1].split(" |")[0]
            if "Evidence: " in entry_reason_str:
                ev_str = entry_reason_str.split("Evidence: ")[1]
                evidence_parts = ev_str.split("; ")

            # 4) Add MAE/MFE evidence
            if mfe_r is not None:
                evidence_parts.append(f"MFE: {mfe_r:+.2f}R")
            if mae_r is not None:
                evidence_parts.append(f"MAE: {mae_r:+.2f}R")
            if sl_distance_atr is not None:
                evidence_parts.append(f"SL distance: {sl_distance_atr:.2f} ATR")
            elif sl_distance is not None:
                evidence_parts.append(f"SL distance: {sl_distance}")

            # 5) Apply MAE/MFE root cause rules if losing trade
            if realized_pnl < 0 and excursion_status != "HISTORICAL_DATA_UNAVAILABLE":
                new_cause = None
                
                # Rule: IMMEDIATE_ADVERSE_MOVE
                if mfe_r is not None and mfe_r < Decimal("0.20") and mae_r is not None and mae_r <= Decimal("-0.90"):
                    new_cause = "IMMEDIATE_ADVERSE_MOVE"
                
                # Rule: REVERSAL_AFTER_FAVORABLE_MOVE
                elif mfe_r is not None and mfe_r >= Decimal("0.50") and mae_r is not None and mae_r <= Decimal("-0.90"):
                    new_cause = "REVERSAL_AFTER_FAVORABLE_MOVE"
                
                # Rule: STOP_TOO_TIGHT
                elif sl_distance_atr is not None and sl_distance_atr < Decimal("1.0"):
                    new_cause = "STOP_TOO_TIGHT"
                
                # Combine evidence: Do not overwrite stronger already-proven reasons blindly.
                # LATE_ENTRY, COUNTER_TREND_ENTRY, MOMENTUM_REVERSAL are typically stronger.
                strong_reasons = {"LATE_ENTRY", "COUNTER_TREND_ENTRY", "MOMENTUM_REVERSAL"}
                if new_cause:
                    if primary_cause in strong_reasons:
                        evidence_parts.append(f"Secondary MAE/MFE cause: {new_cause}")
                    else:
                        if primary_cause != "UNKNOWN_INSUFFICIENT_EVIDENCE":
                            evidence_parts.append(f"Secondary entry cause: {primary_cause}")
                        primary_cause = new_cause

            root_cause = primary_cause
            root_cause_evidence = "; ".join(evidence_parts)

            conn.execute(
                """
                UPDATE closed_trades
                SET mae_price=?,
                    mfe_price=?,
                    mae_pct=?,
                    mfe_pct=?,
                    mae_r=?,
                    mfe_r=?,
                    sl_distance=?,
                    sl_distance_atr=?,
                    mae_at=?,
                    mfe_at=?,
                    root_cause=?,
                    root_cause_evidence=?,
                    excursion_status=?
                WHERE trade_key=?
                """,
                (
                    str(mae_price) if mae_price is not None else None,
                    str(mfe_price) if mfe_price is not None else None,
                    str(mae_pct) if mae_pct is not None else None,
                    str(mfe_pct) if mfe_pct is not None else None,
                    str(mae_r) if mae_r is not None else None,
                    str(mfe_r) if mfe_r is not None else None,
                    str(sl_distance) if sl_distance is not None else None,
                    str(sl_distance_atr) if sl_distance_atr is not None else None,
                    mae_at.isoformat() if mae_at else None,
                    mfe_at.isoformat() if mfe_at else None,
                    root_cause,
                    root_cause_evidence,
                    excursion_status,
                    trade_key,
                ),
            )

    def list_closed_trades(self, limit: int = 100) -> list[ClosedTradeResponse]:
        """Return persisted closed trades enriched with the closest durable entry intent."""
        self.initialize()
        
        def safe_get(r, key, default=None):
            try:
                val = r[key]
                return val if val is not None else default
            except (KeyError, IndexError, TypeError, ValueError):
                return default

        def has_key(r, key):
            try:
                _ = r[key]
                return True
            except (KeyError, IndexError, TypeError, ValueError):
                return False

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM closed_trades
                ORDER BY COALESCE(updated_at, created_at, synced_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            if not rows:
                return []

            link_ids = list({safe_get(r, "order_link_id") for r in rows if safe_get(r, "order_link_id")})
            order_ids = list({safe_get(r, "order_id") for r in rows if safe_get(r, "order_id")})

            executions_by_link = {}
            if link_ids:
                placeholders = ",".join(["?"] * len(link_ids))
                q = f"""
                    SELECT e.*, s.strategy 
                    FROM execution_submissions e
                    LEFT JOIN signal_activity s ON s.signal_id=e.signal_id
                    WHERE e.order_link_id IN ({placeholders})
                    ORDER BY e.submitted_at ASC
                """
                for r in conn.execute(q, link_ids).fetchall():
                    executions_by_link[safe_get(r, "order_link_id")] = r

            executions_by_order = {}
            if order_ids:
                placeholders = ",".join(["?"] * len(order_ids))
                q = f"""
                    SELECT e.*, s.strategy 
                    FROM execution_submissions e
                    LEFT JOIN signal_activity s ON s.signal_id=e.signal_id
                    WHERE e.order_id IN ({placeholders})
                    ORDER BY e.submitted_at ASC
                """
                for r in conn.execute(q, order_ids).fetchall():
                    executions_by_order[safe_get(r, "order_id")] = r

            unmatched = [r for r in rows if (
                not (safe_get(r, "order_link_id") and safe_get(r, "order_link_id") in executions_by_link) and 
                not (safe_get(r, "order_id") and safe_get(r, "order_id") in executions_by_order)
            )]
            
            executions_by_sym_qty = {}
            if unmatched:
                where_clauses = []
                params = []
                for r in unmatched:
                    where_clauses.append("(e.symbol=? AND CAST(e.quantity AS REAL)=CAST(? AS REAL))")
                    params.extend([safe_get(r, "symbol"), safe_get(r, "quantity")])
                
                if where_clauses:
                    for i in range(0, len(where_clauses), 400):
                        chunk_clauses = where_clauses[i:i+400]
                        chunk_params = params[i*2:(i+400)*2]
                        q = f"""
                            SELECT e.*, s.strategy 
                            FROM execution_submissions e
                            LEFT JOIN signal_activity s ON s.signal_id=e.signal_id
                            WHERE {' OR '.join(chunk_clauses)}
                            ORDER BY e.submitted_at DESC
                        """
                        for r in conn.execute(q, chunk_params).fetchall():
                            try:
                                qty_val = float(safe_get(r, "quantity", 0))
                            except Exception:
                                qty_val = 0.0
                            executions_by_sym_qty.setdefault((safe_get(r, "symbol"), qty_val), []).append(r)

            output: list[ClosedTradeResponse] = []
            for row in rows:
                closed_at = safe_get(row, "updated_at") or safe_get(row, "created_at") or safe_get(row, "synced_at")
                execution = None

                trade_order_link_id = safe_get(row, "order_link_id")
                if trade_order_link_id and trade_order_link_id in executions_by_link:
                    execution = executions_by_link[trade_order_link_id]
                
                trade_order_id = safe_get(row, "order_id")
                if execution is None and trade_order_id and trade_order_id in executions_by_order:
                    execution = executions_by_order[trade_order_id]
                
                if execution is None:
                    try:
                        r_qty = float(safe_get(row, "quantity", 0))
                    except Exception:
                        r_qty = 0.0
                    cands = executions_by_sym_qty.get((safe_get(row, "symbol"), r_qty), [])
                    for cand in cands:
                        if safe_get(cand, "submitted_at") <= closed_at:
                            execution = cand
                            break

                stop_loss = (
                    Decimal(safe_get(execution, "stop_loss"))
                    if execution is not None and safe_get(execution, "stop_loss") is not None
                    else None
                )
                take_profit = (
                    Decimal(safe_get(execution, "take_profit"))
                    if execution is not None and safe_get(execution, "take_profit") is not None
                    else None
                )
                exit_price = Decimal(safe_get(row, "exit_price")) if safe_get(row, "exit_price") is not None else None
                realized_pnl = Decimal(safe_get(row, "realized_pnl"))
                side = str(safe_get(row, "side"))

                exit_reason: str
                diagnostic_reason: str
                tolerance = Decimal("0.003")

                def _near(a: Decimal | None, b: Decimal | None) -> bool:
                    if a is None or b is None or b == 0:
                        return False
                    return abs(a - b) / abs(b) <= tolerance

                if realized_pnl < 0 and _near(exit_price, stop_loss):
                    exit_reason = "LIKELY_SL_HIT"
                    diagnostic_reason = self._diagnose_sl_root_cause(
                        execution,
                        side=side,
                    )
                elif realized_pnl > 0 and _near(exit_price, take_profit):
                    exit_reason = "LIKELY_TP_HIT"
                    diagnostic_reason = "Exit price matched the configured take-profit within 0.3%."
                elif realized_pnl < 0:
                    exit_reason = "LOSS_EXIT"
                    diagnostic_reason = (
                        "Closed at a loss, but the persisted data does not prove an SL hit. "
                        "Manual/other exchange exits cannot be distinguished for this trade."
                    )
                elif realized_pnl > 0:
                    exit_reason = "PROFIT_EXIT"
                    diagnostic_reason = (
                        "Closed in profit; persisted data does not prove that the configured TP caused the exit."
                    )
                else:
                    exit_reason = "BREAKEVEN"
                    diagnostic_reason = "Trade closed approximately flat."

                output.append(
                    ClosedTradeResponse(
                        trade_key=safe_get(row, "trade_key"),
                        symbol=safe_get(row, "symbol"),
                        order_id=safe_get(row, "order_id"),
                        order_link_id=safe_get(row, "order_link_id"),
                        side=side,
                        quantity=Decimal(safe_get(row, "quantity")),
                        entry_price=Decimal(safe_get(row, "entry_price")) if safe_get(row, "entry_price") else None,
                        exit_price=exit_price,
                        realized_pnl=realized_pnl,
                        fees=Decimal(safe_get(row, "fees", "0")),
                        exit_reason=exit_reason,
                        diagnostic_reason=diagnostic_reason,
                        strategy=str(safe_get(execution, "strategy")) if execution and safe_get(execution, "strategy") else None,
                        signal_id=str(safe_get(execution, "signal_id")) if execution else None,
                        closed_at=closed_at,
                    )
                )

            return output

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



    def get_position_management_state(self, symbol: str) -> dict | None:
        self.initialize()
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM position_management WHERE symbol = ?",
                (symbol,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "symbol": row["symbol"],
                "be_triggered": bool(row["be_triggered"]),
                "be_trigger_price": Decimal(row["be_trigger_price"]) if row["be_trigger_price"] else None,
                "be_triggered_at": row["be_triggered_at"],
                "original_stop_loss": Decimal(row["original_stop_loss"]) if row["original_stop_loss"] else None,
                "current_stop_loss": Decimal(row["current_stop_loss"]) if row["current_stop_loss"] else None,
                "be_order_id": row["be_order_id"],
                "be_status": row["be_status"],
                "updated_at": row["updated_at"]
            }

    def upsert_position_management_state(self, state: dict) -> None:
        self.initialize()
        with self._connect() as conn:
            conn.execute(
                '''
                INSERT INTO position_management (
                    symbol, be_triggered, be_trigger_price, be_triggered_at,
                    original_stop_loss, current_stop_loss, be_order_id, be_status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    be_triggered = excluded.be_triggered,
                    be_trigger_price = excluded.be_trigger_price,
                    be_triggered_at = excluded.be_triggered_at,
                    original_stop_loss = excluded.original_stop_loss,
                    current_stop_loss = excluded.current_stop_loss,
                    be_order_id = excluded.be_order_id,
                    be_status = excluded.be_status,
                    updated_at = excluded.updated_at
                ''',
                (
                    state["symbol"],
                    int(state["be_triggered"]),
                    str(state["be_trigger_price"]) if state["be_trigger_price"] is not None else None,
                    state["be_triggered_at"],
                    str(state["original_stop_loss"]) if state["original_stop_loss"] is not None else None,
                    str(state["current_stop_loss"]) if state["current_stop_loss"] is not None else None,
                    state["be_order_id"],
                    state["be_status"],
                    state["updated_at"],
                )
            )
