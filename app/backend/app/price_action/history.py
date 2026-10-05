import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


HISTORY_FILE = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "price_action_signal_history.json"
)


class PriceActionSignalHistory:

    def __init__(self, market_data_service):
        self.market = market_data_service
        HISTORY_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._active_keys: set[str] = set()

        if not HISTORY_FILE.exists():
            self._save([])

    # ---------------------------------------------------------
    # File helpers
    # ---------------------------------------------------------

    def _load(self) -> list[dict]:
        try:
            data = json.loads(
                HISTORY_FILE.read_text(
                    encoding="utf-8"
                )
            )

            return data if isinstance(data, list) else []

        except Exception:
            return []

    def _save(self, rows: list[dict]) -> None:
        HISTORY_FILE.write_text(
            json.dumps(
                rows,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _key(signal) -> str:
        return (
            f"{signal.symbol}:"
            f"{signal.side}:"
            f"{signal.pattern}"
        )

    # ---------------------------------------------------------
    # Save NEW signals only
    # ---------------------------------------------------------

    def record_new_signals(
        self,
        signals,
        *,
        now: datetime | None = None,
    ) -> int:

        now = now or datetime.now(timezone.utc)

        rows = self._load()

        current_keys = {
            self._key(x)
            for x in signals
        }

        added = 0

        for signal in signals:

            key = self._key(signal)

            if key in self._active_keys:
                continue

            # Protect against duplicate after app restart.
            duplicate_recent = False

            for row in reversed(rows):

                if row.get("key") != key:
                    continue

                try:
                    created = datetime.fromisoformat(
                        row["created_at"]
                    )
                except Exception:
                    continue

                if (
                    row.get("status") == "OPEN"
                    and now - created < timedelta(hours=1)
                ):
                    duplicate_recent = True

                break

            if duplicate_recent:
                continue

            risk = abs(
                float(signal.entry)
                - float(signal.stop_loss)
            )

            tp1 = (
                float(signal.entry) + risk
                if signal.side == "LONG"
                else float(signal.entry) - risk
            )

            tp2 = (
                float(signal.entry) + risk * 2
                if signal.side == "LONG"
                else float(signal.entry) - risk * 2
            )

            rows.append(
                {
                    "id": (
                        f"{signal.symbol}-"
                        f"{int(now.timestamp())}"
                    ),
                    "key": key,
                    "created_at": now.isoformat(),

                    "symbol": signal.symbol,
                    "side": signal.side,
                    "score": signal.score,
                    "pattern": signal.pattern,

                    "entry": float(signal.entry),
                    "stop_loss": float(
                        signal.stop_loss
                    ),
                    "tp1": tp1,
                    "tp2": tp2,

                    "htf_bias": signal.htf_bias,
                    "structure_bias":
                        signal.structure_bias,

                    "reasons": list(
                        signal.reasons
                    ),

                    "status": "OPEN",
                    "result_r": None,
                    "closed_at": None,
                    "exit_price": None,

                    "price_1h": None,
                    "return_1h_pct": None,

                    "price_4h": None,
                    "return_4h_pct": None,

                    "price_24h": None,
                    "return_24h_pct": None,
                }
            )

            added += 1

        self._active_keys = current_keys

        if added:
            self._save(rows)

        return added

    # ---------------------------------------------------------
    # Performance calculation
    # ---------------------------------------------------------

    @staticmethod
    def _directional_return(
        side: str,
        entry: float,
        price: float,
    ) -> float:

        if not entry:
            return 0.0

        if side == "LONG":
            value = (
                (price - entry)
                / entry
                * 100
            )
        else:
            value = (
                (entry - price)
                / entry
                * 100
            )

        return round(value, 4)

    async def evaluate_open_signals(self) -> int:

        rows = self._load()

        changed = 0
        now = datetime.now(timezone.utc)

        for row in rows:

            if row.get("status") != "OPEN":
                continue

            symbol = row["symbol"]

            try:
                created = datetime.fromisoformat(
                    row["created_at"]
                )

                candles = await self.market.fetch_candles(
                    symbol,
                    "5m",
                    limit=320,
                    closed_only=True,
                )

            except Exception:
                continue

            future = [
                x for x in candles
                if x.start_time >= created
            ]

            if not future:
                continue

            entry = float(row["entry"])
            sl = float(row["stop_loss"])
            tp2 = float(row["tp2"])
            side = row["side"]

            # -------------------------------------------------
            # TP / SL resolution
            # -------------------------------------------------

            for candle in future:

                high = float(candle.high)
                low = float(candle.low)

                if side == "LONG":

                    sl_hit = low <= sl
                    tp_hit = high >= tp2

                else:

                    sl_hit = high >= sl
                    tp_hit = low <= tp2

                # Conservative handling if both touched
                # inside the same 5m candle.
                if sl_hit and tp_hit:

                    row["status"] = "LOSS"
                    row["result_r"] = -1.0
                    row["exit_price"] = sl
                    row["closed_at"] = (
                        candle.start_time.isoformat()
                    )

                    changed += 1
                    break

                if sl_hit:

                    row["status"] = "LOSS"
                    row["result_r"] = -1.0
                    row["exit_price"] = sl
                    row["closed_at"] = (
                        candle.start_time.isoformat()
                    )

                    changed += 1
                    break

                if tp_hit:

                    row["status"] = "WIN"
                    row["result_r"] = 2.0
                    row["exit_price"] = tp2
                    row["closed_at"] = (
                        candle.start_time.isoformat()
                    )

                    changed += 1
                    break

            # -------------------------------------------------
            # 1H / 4H / 24H snapshots
            # -------------------------------------------------

            horizons = (
                ("1h", 1),
                ("4h", 4),
                ("24h", 24),
            )

            for label, hours in horizons:

                price_key = f"price_{label}"
                return_key = (
                    f"return_{label}_pct"
                )

                if row.get(price_key) is not None:
                    continue

                target = (
                    created
                    + timedelta(hours=hours)
                )

                if now < target:
                    continue

                eligible = [
                    x for x in future
                    if x.start_time <= target
                ]

                if not eligible:
                    continue

                price = float(
                    eligible[-1].close
                )

                row[price_key] = price

                row[return_key] = (
                    self._directional_return(
                        side,
                        entry,
                        price,
                    )
                )

                changed += 1

            # After 24 hours, unresolved setup expires.
            if (
                row.get("status") == "OPEN"
                and now >= created
                + timedelta(hours=24)
            ):

                row["status"] = "EXPIRED"
                changed += 1

        if changed:
            self._save(rows)

        return changed

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    def summary(self) -> dict:

        rows = self._load()

        wins = sum(
            1 for x in rows
            if x.get("status") == "WIN"
        )

        losses = sum(
            1 for x in rows
            if x.get("status") == "LOSS"
        )

        open_count = sum(
            1 for x in rows
            if x.get("status") == "OPEN"
        )

        expired = sum(
            1 for x in rows
            if x.get("status") == "EXPIRED"
        )

        resolved = wins + losses

        win_rate = (
            round(
                wins / resolved * 100,
                2,
            )
            if resolved
            else 0.0
        )

        total_r = sum(
            float(x.get("result_r") or 0)
            for x in rows
        )

        return {
            "total_signals": len(rows),
            "open": open_count,
            "wins": wins,
            "losses": losses,
            "expired": expired,
            "resolved": resolved,
            "win_rate_pct": win_rate,
            "total_r": round(
                total_r,
                2,
            ),
        }

    def records(self) -> list[dict]:
        return list(
            reversed(
                self._load()
            )
        )
