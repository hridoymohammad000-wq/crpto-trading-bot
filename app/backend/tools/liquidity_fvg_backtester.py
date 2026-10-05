from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal, List, Dict, Tuple
import math

import numpy as np
import pandas as pd


Side = Literal["long", "short"]


@dataclass
class BacktestConfig:
    fractal_n: int = 5
    atr_period: int = 14
    fvg_min_atr: float = 0.30
    fvg_max_atr: float = 3.0
    fvg_max_age: int = 50
    sweep_epsilon_atr: float = 0.10
    sr_tolerance_atr: float = 0.25
    sr_min_touches: int = 2
    sr_lookback: int = 200
    sl_buffer_atr: float = 0.25
    rr_min: float = 1.5
    tp_r: Tuple[float, float, float] = (1.5, 2.5, 4.0)
    tp_size: Tuple[float, float, float] = (0.40, 0.35, 0.25)
    atr_ratio_min: float = 0.6
    atr_ratio_max: float = 2.5
    er_period: int = 14
    er_floor: float = 0.30
    volume_mult: float = 1.20
    use_volume_filter: bool = True
    use_session_filter: bool = False
    max_daily_sl_hits: int = 3
    max_daily_loss_r: float = 2.0
    htf_ema_period: int = 50
    confirm_timeout: int = 5
    initial_equity: float = 10_000.0
    risk_pct: float = 0.01
    max_leverage: float = 5.0
    fee_rate: float = 0.00055
    slippage_bps: float = 0.0
    conservative_intrabar: bool = True


@dataclass
class FVG:
    side: Side
    impulse_idx: int
    formed_idx: int
    upper: float
    lower: float
    midpoint: float
    expires_idx: int


@dataclass
class Trade:
    side: Side
    entry_idx: int
    entry_time: pd.Timestamp
    entry: float
    stop: float
    risk_per_unit: float
    qty: float
    equity_before: float
    tp1: float
    tp2: float
    tp3: float
    remaining_qty: float
    realized_pnl: float = 0.0
    fees: float = 0.0
    exit_idx: Optional[int] = None
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    tp1_done: bool = False
    tp2_done: bool = False
    tp3_done: bool = False
    trailing_active: bool = False
    trail_stop: Optional[float] = None
    r_multiple: Optional[float] = None


class LiquiditySweepFVGBacktester:
    """
    Backtester for:
    Liquidity Sweep + Fair Value Gap Reversion

    Required input columns:
        timestamp, open, high, low, close
    Optional:
        volume

    entry_df should be the execution timeframe (e.g. 5m/15m).
    htf_df should be the higher timeframe (1H) used for EMA(50) bias.

    Important deterministic implementation choices not fully specified by the source:
    1) When multiple valid FVGs exist, the most recent matching-side FVG is used.
    2) Swing levels become usable only after fractal confirmation at i+n.
    3) If SL and TP are both touched within the same bar and ordering is unknowable,
       conservative_intrabar=True assumes adverse price is hit first.
    4) "Nearest significant S/R blocks TP1" is implemented from clustered confirmed
       significant pivots in the prior sr_lookback window.
    """

    def __init__(
        self,
        entry_df: pd.DataFrame,
        htf_df: pd.DataFrame,
        config: Optional[BacktestConfig] = None,
    ):
        self.cfg = config or BacktestConfig()
        self.df = self._prepare(entry_df.copy())
        self.htf = self._prepare(htf_df.copy())

        self._add_indicators()
        self._align_htf_bias()

        self.fvgs: List[FVG] = []
        self.trades: List[Trade] = []
        self.equity = self.cfg.initial_equity

        self.daily_sl_hits: Dict[pd.Timestamp, int] = {}
        self.daily_r_pnl: Dict[pd.Timestamp, float] = {}

    @staticmethod
    def _prepare(df: pd.DataFrame) -> pd.DataFrame:
        needed = {"timestamp", "open", "high", "low", "close"}
        missing = needed - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {sorted(missing)}")

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)

        for c in ["open", "high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

        return df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

    def _add_indicators(self) -> None:
        d = self.df
        p = self.cfg.atr_period

        prev_close = d["close"].shift(1)
        tr = pd.concat(
            [
                d["high"] - d["low"],
                (d["high"] - prev_close).abs(),
                (d["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        d["atr"] = tr.rolling(p, min_periods=p).mean()
        d["atr20avg"] = d["atr"].rolling(20, min_periods=20).mean()
        d["atr_ratio"] = d["atr"] / d["atr20avg"]

        rng = d["high"] - d["low"]
        d["body_ratio"] = np.where(
            rng > 0,
            (d["close"] - d["open"]).abs() / rng,
            0.0,
        )

        ep = self.cfg.er_period
        direction = (d["close"] - d["close"].shift(ep)).abs()
        volatility = d["close"].diff().abs().rolling(ep, min_periods=ep).sum()
        d["er"] = np.where(volatility > 0, direction / volatility, np.nan)

        if "volume" in d.columns:
            d["vol_avg20"] = d["volume"].rolling(20, min_periods=20).mean()
        else:
            d["vol_avg20"] = np.nan

        self._identify_swings()

    def _align_htf_bias(self) -> None:
        h = self.htf.copy()
        h["htf_ema"] = h["close"].ewm(
            span=self.cfg.htf_ema_period,
            adjust=False,
            min_periods=self.cfg.htf_ema_period,
        ).mean()

        h = h[["timestamp", "close", "htf_ema"]].rename(columns={"close": "htf_close"})
        self.df = pd.merge_asof(
            self.df.sort_values("timestamp"),
            h.sort_values("timestamp"),
            on="timestamp",
            direction="backward",
        )
        self.df["htf_bull"] = self.df["htf_close"] > self.df["htf_ema"]
        self.df["htf_bear"] = self.df["htf_close"] < self.df["htf_ema"]

    def _identify_swings(self) -> None:
        n = self.cfg.fractal_n
        d = self.df
        m = len(d)

        swing_high = np.zeros(m, dtype=bool)
        swing_low = np.zeros(m, dtype=bool)
        sig_high = np.zeros(m, dtype=bool)
        sig_low = np.zeros(m, dtype=bool)
        confirmed_at = np.full(m, -1, dtype=int)

        highs = d["high"].to_numpy()
        lows = d["low"].to_numpy()
        atr = d["atr"].to_numpy()

        for i in range(n, m - n):
            hi = highs[i]
            lo = lows[i]

            is_sh = (
                hi == np.max(highs[i - n : i + n + 1])
                and hi > highs[i - 1]
                and hi > highs[i + 1]
            )
            is_sl = (
                lo == np.min(lows[i - n : i + n + 1])
                and lo < lows[i - 1]
                and lo < lows[i + 1]
            )

            swing_high[i] = is_sh
            swing_low[i] = is_sl
            confirmed_at[i] = i + n if (is_sh or is_sl) else -1

            if not np.isnan(atr[i]):
                candle_range = hi - lo
                sig_high[i] = is_sh and candle_range >= atr[i] * 0.5
                sig_low[i] = is_sl and candle_range >= atr[i] * 0.5

        d["swing_high"] = swing_high
        d["swing_low"] = swing_low
        d["sig_swing_high"] = sig_high
        d["sig_swing_low"] = sig_low
        d["swing_confirmed_at"] = confirmed_at

    def _discover_fvg_at(self, impulse_i: int) -> None:
        d = self.df
        if impulse_i - 1 < 0 or impulse_i + 1 >= len(d):
            return

        atr = d.at[impulse_i, "atr"]
        if pd.isna(atr) or atr <= 0:
            return

        prev_h = d.at[impulse_i - 1, "high"]
        prev_l = d.at[impulse_i - 1, "low"]
        next_h = d.at[impulse_i + 1, "high"]
        next_l = d.at[impulse_i + 1, "low"]

        o = d.at[impulse_i, "open"]
        c = d.at[impulse_i, "close"]

        # Bullish FVG
        if next_l > prev_h and (c - o) >= atr * 1.0:
            lower = prev_h
            upper = next_l
            width = upper - lower
            if atr * self.cfg.fvg_min_atr <= width <= atr * self.cfg.fvg_max_atr:
                self.fvgs.append(
                    FVG(
                        side="long",
                        impulse_idx=impulse_i,
                        formed_idx=impulse_i + 1,
                        upper=upper,
                        lower=lower,
                        midpoint=(upper + lower) / 2,
                        expires_idx=(impulse_i + 1) + self.cfg.fvg_max_age,
                    )
                )

        # Bearish FVG
        if next_h < prev_l and (o - c) >= atr * 1.0:
            lower = next_h
            upper = prev_l
            width = upper - lower
            if atr * self.cfg.fvg_min_atr <= width <= atr * self.cfg.fvg_max_atr:
                self.fvgs.append(
                    FVG(
                        side="short",
                        impulse_idx=impulse_i,
                        formed_idx=impulse_i + 1,
                        upper=upper,
                        lower=lower,
                        midpoint=(upper + lower) / 2,
                        expires_idx=(impulse_i + 1) + self.cfg.fvg_max_age,
                    )
                )

    def _fvg_is_expired(self, fvg: FVG, current_i: int) -> bool:
        if current_i > fvg.expires_idx:
            return True

        # expired if price CLOSED inside zone for >=2 consecutive bars
        start = max(fvg.formed_idx, current_i - 1)
        if current_i - start + 1 < 2:
            return False

        closes = self.df.loc[current_i - 1 : current_i, "close"]
        inside = (closes >= fvg.lower) & (closes <= fvg.upper)
        return bool(inside.all())

    def _recent_valid_fvg(self, side: Side, current_i: int) -> Optional[FVG]:
        candidates = [
            f
            for f in self.fvgs
            if f.side == side
            and f.formed_idx <= current_i
            and not self._fvg_is_expired(f, current_i)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x.formed_idx)

    def _confirmed_sig_swings(self, current_i: int, side: Side) -> List[int]:
        d = self.df
        col = "sig_swing_low" if side == "long" else "sig_swing_high"

        idxs = []
        for i in range(max(0, current_i - self.cfg.sr_lookback), current_i + 1):
            if bool(d.at[i, col]) and int(d.at[i, "swing_confirmed_at"]) <= current_i:
                idxs.append(i)
        return idxs

    def _most_recent_swing_price(self, current_i: int, side: Side) -> Optional[float]:
        idxs = self._confirmed_sig_swings(current_i, side)
        if not idxs:
            return None
        i = idxs[-1]
        return float(self.df.at[i, "low"] if side == "long" else self.df.at[i, "high"])

    def _detect_sweep(self, i: int, side: Side) -> bool:
        d = self.df
        atr = d.at[i, "atr"]
        if pd.isna(atr) or atr <= 0:
            return False

        level = self._most_recent_swing_price(i - 1, side)
        if level is None:
            return False

        h, l, c = d.at[i, "high"], d.at[i, "low"], d.at[i, "close"]
        rng = h - l
        if rng <= 0:
            return False

        eps = atr * self.cfg.sweep_epsilon_atr

        if side == "long":
            return (
                l < level
                and c > level
                and l < level - eps
                and (c - l) >= rng * 0.5
            )
        else:
            return (
                h > level
                and c < level
                and h > level + eps
                and (h - c) >= rng * 0.5
            )

    def _session_allowed(self, ts: pd.Timestamp) -> bool:
        if not self.cfg.use_session_filter:
            return True
        h = ts.hour
        return (7 <= h < 11) or (12 <= h < 14) or (13 <= h < 17)

    def _filters_ok(self, sweep_i: int) -> bool:
        d = self.df

        atr_ratio = d.at[sweep_i, "atr_ratio"]
        er = d.at[sweep_i, "er"]
        body_ratio = d.at[sweep_i, "body_ratio"]

        if pd.isna(atr_ratio) or not (self.cfg.atr_ratio_min <= atr_ratio <= self.cfg.atr_ratio_max):
            return False
        if pd.isna(er) or er < self.cfg.er_floor:
            return False
        if body_ratio < 0.35:
            return False
        if not self._session_allowed(d.at[sweep_i, "timestamp"]):
            return False

        if self.cfg.use_volume_filter and "volume" in d.columns:
            v = d.at[sweep_i, "volume"]
            vavg = d.at[sweep_i, "vol_avg20"]
            if pd.notna(vavg) and v < vavg * self.cfg.volume_mult:
                return False

        return True

    def _cluster_sr_levels(self, current_i: int) -> List[float]:
        d = self.df
        start = max(0, current_i - self.cfg.sr_lookback)
        pts: List[float] = []

        for i in range(start, current_i + 1):
            if int(d.at[i, "swing_confirmed_at"]) > current_i:
                continue
            if bool(d.at[i, "sig_swing_high"]):
                pts.append(float(d.at[i, "high"]))
            if bool(d.at[i, "sig_swing_low"]):
                pts.append(float(d.at[i, "low"]))

        if len(pts) < self.cfg.sr_min_touches:
            return []

        atr = d.at[current_i, "atr"]
        if pd.isna(atr) or atr <= 0:
            return []

        delta = atr * self.cfg.sr_tolerance_atr
        pts = sorted(pts)

        clusters: List[List[float]] = []
        for p in pts:
            placed = False
            for c in clusters:
                center = float(np.mean(c))
                if abs(p - center) <= delta:
                    c.append(p)
                    placed = True
                    break
            if not placed:
                clusters.append([p])

        return [
            float(np.mean(c))
            for c in clusters
            if len(c) >= self.cfg.sr_min_touches
        ]

    def _nearest_sr_blocks_tp1(self, entry: float, r: float, current_i: int, side: Side) -> bool:
        levels = self._cluster_sr_levels(current_i)
        if side == "long":
            resistances = [x for x in levels if x > entry]
            if not resistances:
                return False
            nearest = min(resistances)
            return (nearest - entry) < r * self.cfg.rr_min
        else:
            supports = [x for x in levels if x < entry]
            if not supports:
                return False
            nearest = max(supports)
            return (entry - nearest) < r * self.cfg.rr_min

    def _daily_halt(self, ts: pd.Timestamp) -> bool:
        day = ts.normalize()
        return (
            self.daily_sl_hits.get(day, 0) >= self.cfg.max_daily_sl_hits
            or self.daily_r_pnl.get(day, 0.0) <= -self.cfg.max_daily_loss_r
        )

    def _entry_conditions(self, sweep_i: int, confirm_i: int, side: Side) -> Optional[Dict]:
        d = self.df
        if confirm_i >= len(d):
            return None
        if self._daily_halt(d.at[confirm_i, "timestamp"]):
            return None
        if not self._filters_ok(sweep_i):
            return None
        if not self._detect_sweep(sweep_i, side):
            return None

        fvg = self._recent_valid_fvg(side, sweep_i)
        if fvg is None:
            return None

        o2, h2, l2, c2 = (
            d.at[confirm_i, "open"],
            d.at[confirm_i, "high"],
            d.at[confirm_i, "low"],
            d.at[confirm_i, "close"],
        )
        c1 = d.at[sweep_i, "close"]
        l1 = d.at[sweep_i, "low"]
        h1 = d.at[sweep_i, "high"]
        atr2 = d.at[confirm_i, "atr"]

        if pd.isna(atr2) or atr2 <= 0:
            return None

        if side == "long":
            if not (c1 >= fvg.lower):
                return None
            if not (c2 > o2 and c2 > c1 and l2 > l1):
                return None
            if not bool(d.at[confirm_i, "htf_bull"]):
                return None

            recent_sl = self._most_recent_swing_price(sweep_i - 1, "long")
            if recent_sl is None or not (l1 <= recent_sl and recent_sl < c2):
                return None

            stop = min(l1, l2) - atr2 * self.cfg.sl_buffer_atr
            entry = c2
            r = entry - stop
            if r <= 0:
                return None

            if self._nearest_sr_blocks_tp1(entry, r, confirm_i, "long"):
                return None

            return {"entry": entry, "stop": stop, "r": r, "fvg": fvg}

        else:
            if not (c1 <= fvg.upper):
                return None
            if not (c2 < o2 and c2 < c1 and h2 < h1):
                return None
            if not bool(d.at[confirm_i, "htf_bear"]):
                return None

            recent_sh = self._most_recent_swing_price(sweep_i - 1, "short")
            if recent_sh is None or not (h1 >= recent_sh and recent_sh > c2):
                return None

            stop = max(h1, h2) + atr2 * self.cfg.sl_buffer_atr
            entry = c2
            r = stop - entry
            if r <= 0:
                return None

            if self._nearest_sr_blocks_tp1(entry, r, confirm_i, "short"):
                return None

            return {"entry": entry, "stop": stop, "r": r, "fvg": fvg}

    def _apply_slippage(self, price: float, side: Side, entry: bool) -> float:
        bps = self.cfg.slippage_bps / 10_000.0
        if bps == 0:
            return price
        if side == "long":
            return price * (1 + bps if entry else 1 - bps)
        return price * (1 - bps if entry else 1 + bps)

    def _open_trade(self, i: int, side: Side, levels: Dict) -> Trade:
        entry = self._apply_slippage(float(levels["entry"]), side, entry=True)
        stop = float(levels["stop"])
        r = abs(entry - stop)

        risk_amount = self.equity * self.cfg.risk_pct

        estimated_fee_per_unit = (
            entry * self.cfg.fee_rate
            + stop * self.cfg.fee_rate
        )

        effective_risk_per_unit = r + estimated_fee_per_unit

        if effective_risk_per_unit <= 0:
            raise ValueError("Effective risk per unit must be positive")

        risk_based_qty = risk_amount / effective_risk_per_unit

        max_notional = self.equity * self.cfg.max_leverage
        leverage_based_qty = max_notional / entry

        qty = min(risk_based_qty, leverage_based_qty)

        if side == "long":
            tp1 = entry + r * self.cfg.tp_r[0]
            tp2 = entry + r * self.cfg.tp_r[1]
            tp3 = entry + r * self.cfg.tp_r[2]
        else:
            tp1 = entry - r * self.cfg.tp_r[0]
            tp2 = entry - r * self.cfg.tp_r[1]
            tp3 = entry - r * self.cfg.tp_r[2]

        trade = Trade(
            side=side,
            entry_idx=i,
            entry_time=self.df.at[i, "timestamp"],
            entry=entry,
            stop=stop,
            risk_per_unit=r,
            qty=qty,
            equity_before=self.equity,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            remaining_qty=qty,
        )

        entry_fee = qty * entry * self.cfg.fee_rate
        trade.fees += entry_fee
        trade.realized_pnl -= entry_fee
        self.equity -= entry_fee

        return trade

    def _realize(self, trade: Trade, qty: float, price: float) -> float:
        px = self._apply_slippage(price, trade.side, entry=False)
        if trade.side == "long":
            pnl = (px - trade.entry) * qty
        else:
            pnl = (trade.entry - px) * qty

        fee = qty * px * self.cfg.fee_rate
        trade.realized_pnl += pnl - fee
        trade.fees += fee
        trade.remaining_qty -= qty
        self.equity += pnl - fee
        return pnl - fee

    def _close_all(self, trade: Trade, i: int, price: float, reason: str) -> None:
        if trade.remaining_qty > 1e-12:
            self._realize(trade, trade.remaining_qty, price)
        trade.exit_idx = i
        trade.exit_time = self.df.at[i, "timestamp"]
        trade.exit_price = price
        trade.exit_reason = reason
        trade.r_multiple = trade.realized_pnl / (trade.qty * trade.risk_per_unit)

        day = trade.entry_time.normalize()
        self.daily_r_pnl[day] = self.daily_r_pnl.get(day, 0.0) + trade.r_multiple

        if reason == "SL":
            self.daily_sl_hits[day] = self.daily_sl_hits.get(day, 0) + 1

    def _opposite_sweep(self, i: int, trade: Trade) -> bool:
        return self._detect_sweep(i, "short" if trade.side == "long" else "long")

    def _manage_trade(self, trade: Trade, i: int) -> bool:
        d = self.df
        h = float(d.at[i, "high"])
        l = float(d.at[i, "low"])
        c = float(d.at[i, "close"])
        atr = float(d.at[i, "atr"]) if pd.notna(d.at[i, "atr"]) else np.nan

        # Post-entry invalidation: HTF bias flip
        if trade.side == "long" and not bool(d.at[i, "htf_bull"]):
            self._close_all(trade, i, c, "HTF_BIAS_FLIP")
            return True
        if trade.side == "short" and not bool(d.at[i, "htf_bear"]):
            self._close_all(trade, i, c, "HTF_BIAS_FLIP")
            return True

        if self._opposite_sweep(i, trade):
            self._close_all(trade, i, c, "OPPOSITE_SWEEP")
            return True

        # Conservative ambiguity handling
        if trade.side == "long":
            stop_hit = l <= (trade.trail_stop if trade.trailing_active and trade.trail_stop is not None else trade.stop)
            tp1_hit = h >= trade.tp1
            tp2_hit = h >= trade.tp2
            tp3_hit = h >= trade.tp3
        else:
            stop_hit = h >= (trade.trail_stop if trade.trailing_active and trade.trail_stop is not None else trade.stop)
            tp1_hit = l <= trade.tp1
            tp2_hit = l <= trade.tp2
            tp3_hit = l <= trade.tp3

        if self.cfg.conservative_intrabar and stop_hit:
            stop_px = trade.trail_stop if trade.trailing_active and trade.trail_stop is not None else trade.stop
            self._close_all(trade, i, stop_px, "SL")
            return True

        # TP1: close 40%, move SL to breakeven
        if not trade.tp1_done and tp1_hit:
            qty = trade.qty * self.cfg.tp_size[0]
            self._realize(trade, min(qty, trade.remaining_qty), trade.tp1)
            trade.tp1_done = True
            trade.stop = trade.entry

        # TP2: close 35%, activate trailing stop
        if not trade.tp2_done and tp2_hit and trade.remaining_qty > 1e-12:
            qty = trade.qty * self.cfg.tp_size[1]
            self._realize(trade, min(qty, trade.remaining_qty), trade.tp2)
            trade.tp2_done = True
            trade.trailing_active = True

        # TP3: close remaining if target touched
        if not trade.tp3_done and tp3_hit and trade.remaining_qty > 1e-12:
            self._close_all(trade, i, trade.tp3, "TP3")
            trade.tp3_done = True
            return True

        # trailing stop after TP2
        if trade.trailing_active and pd.notna(atr):
            if trade.side == "long":
                new_trail = h - atr * 1.5
                trade.trail_stop = (
                    new_trail
                    if trade.trail_stop is None
                    else max(trade.trail_stop, new_trail)
                )
            else:
                new_trail = l + atr * 1.5
                trade.trail_stop = (
                    new_trail
                    if trade.trail_stop is None
                    else min(trade.trail_stop, new_trail)
                )

        # non-conservative mode: stop after taking same-bar profits
        if not self.cfg.conservative_intrabar:
            if trade.side == "long":
                effective_stop = trade.trail_stop if trade.trailing_active and trade.trail_stop is not None else trade.stop
                if l <= effective_stop:
                    self._close_all(trade, i, effective_stop, "SL")
                    return True
            else:
                effective_stop = trade.trail_stop if trade.trailing_active and trade.trail_stop is not None else trade.stop
                if h >= effective_stop:
                    self._close_all(trade, i, effective_stop, "SL")
                    return True

        return False

    def run(self) -> pd.DataFrame:
        d = self.df
        n = len(d)
        open_trade: Optional[Trade] = None

        # FVG uses i-1, i, i+1; discovering impulse at i requires i+1 observed.
        for i in range(2, n):
            self._discover_fvg_at(i - 1)

            if open_trade is not None:
                closed = self._manage_trade(open_trade, i)
                if closed:
                    self.trades.append(open_trade)
                    open_trade = None
                continue

            # Confirmation is next candle after sweep: sweep=t, confirm=t+1.
            sweep_i = i - 1
            confirm_i = i

            # Long
            levels = self._entry_conditions(sweep_i, confirm_i, "long")
            if levels is not None:
                open_trade = self._open_trade(confirm_i, "long", levels)
                continue

            # Short
            levels = self._entry_conditions(sweep_i, confirm_i, "short")
            if levels is not None:
                open_trade = self._open_trade(confirm_i, "short", levels)
                continue

        # close open trade at final close for accounting completeness
        if open_trade is not None:
            i = len(d) - 1
            self._close_all(open_trade, i, float(d.at[i, "close"]), "EOD")
            self.trades.append(open_trade)

        return self.trades_frame()

    def trades_frame(self) -> pd.DataFrame:
        rows = []
        for t in self.trades:
            rows.append(
                {
                    "side": t.side,
                    "entry_time": t.entry_time,
                    "exit_time": t.exit_time,
                    "entry": t.entry,
                    "exit": t.exit_price,
                    "stop": t.stop,
                    "tp1": t.tp1,
                    "tp2": t.tp2,
                    "tp3": t.tp3,
                    "qty": t.qty,
                    "realized_pnl": t.realized_pnl,
                    "fees": t.fees,
                    "r_multiple": t.r_multiple,
                    "exit_reason": t.exit_reason,
                    "equity_before": t.equity_before,
                }
            )
        return pd.DataFrame(rows)

    def summary(self) -> Dict[str, float]:
        t = self.trades_frame()
        if t.empty:
            return {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate_pct": 0.0,
                "net_pnl": 0.0,
                "profit_factor": 0.0,
                "avg_r": 0.0,
                "ending_equity": self.equity,
            }

        wins = t[t["realized_pnl"] > 0]
        losses = t[t["realized_pnl"] < 0]
        gross_profit = wins["realized_pnl"].sum()
        gross_loss = abs(losses["realized_pnl"].sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else math.inf

        return {
            "trades": int(len(t)),
            "wins": int(len(wins)),
            "losses": int(len(losses)),
            "win_rate_pct": float(len(wins) / len(t) * 100.0),
            "net_pnl": float(t["realized_pnl"].sum()),
            "profit_factor": float(pf),
            "avg_r": float(t["r_multiple"].mean()),
            "ending_equity": float(self.equity),
        }


def load_ohlcv_csv(path: str) -> pd.DataFrame:
    """
    Expects CSV columns:
    timestamp, open, high, low, close[, volume]

    timestamp may be ISO datetime or millisecond epoch.
    """
    df = pd.read_csv(path)

    if "timestamp" not in df.columns:
        raise ValueError("CSV must contain a 'timestamp' column.")

    # auto-detect numeric epoch timestamps
    if pd.api.types.is_numeric_dtype(df["timestamp"]):
        sample = float(df["timestamp"].dropna().iloc[0])
        unit = "ms" if sample > 10_000_000_000 else "s"
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit=unit, utc=True)
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    return df


if __name__ == "__main__":
    # Example:
    #
    # entry = load_ohlcv_csv("BTCUSDT_5m.csv")
    # htf = load_ohlcv_csv("BTCUSDT_1h.csv")
    #
    # cfg = BacktestConfig(
    #     initial_equity=10_000,
    #     risk_pct=0.01,
    #     use_volume_filter=True,
    #     use_session_filter=False,
    #     fee_rate=0.00055,
    #     slippage_bps=0.0,
    # )
    #
    # bt = LiquiditySweepFVGBacktester(entry, htf, cfg)
    # trades = bt.run()
    # print(trades.tail(20))
    # print(bt.summary())
    #
    pass
