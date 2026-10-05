from dataclasses import dataclass
from typing import Sequence, Literal

from .patterns import Candle, detect_patterns
from .structure import analyze_structure
from .context import (
    build_sr_zones,
    detect_fvgs,
    detect_liquidity_sweeps,
    nearest_zone,
)


Side = Literal["LONG", "SHORT"]


@dataclass(frozen=True)
class PriceActionSetup:
    side: Side
    score: int
    entry: float
    stop_loss: float
    reason: tuple[str, ...]
    pattern: str | None
    htf_bias: str
    structure_bias: str
    sweep_level: float | None
    context_zone: str | None


def ema(values: Sequence[float], period: int) -> list[float]:
    if not values:
        return []

    alpha = 2 / (period + 1)
    out = [float(values[0])]

    for value in values[1:]:
        out.append(alpha * float(value) + (1 - alpha) * out[-1])

    return out


def htf_bias(candles: Sequence[Candle], period: int = 50) -> str:
    if len(candles) < period:
        return "NEUTRAL"

    closes = [c.close for c in candles]
    ema_values = ema(closes, period)

    if closes[-1] > ema_values[-1]:
        return "BULLISH"

    if closes[-1] < ema_values[-1]:
        return "BEARISH"

    return "NEUTRAL"


def build_setup(
    candles_1h: Sequence[Candle],
    candles_15m: Sequence[Candle],
    candles_5m: Sequence[Candle],
) -> PriceActionSetup | None:

    if len(candles_1h) < 50 or len(candles_15m) < 20 or len(candles_5m) < 20:
        return None

    bias_1h = htf_bias(candles_1h)
    structure_15m = analyze_structure(candles_15m)

    sweeps = detect_liquidity_sweeps(candles_5m)

    sr_zones = build_sr_zones(
        candles_15m,
        structure_15m.swings,
    )

    fvg_zones = detect_fvgs(candles_5m)

    current = candles_5m[-1]
    price = current.close

    latest_sweep = sweeps[-1] if sweeps else None

    # Freshness rule:
    # Sweep must have happened within the latest 3 CLOSED 5m candles.
    if latest_sweep is not None:
        last_index = len(candles_5m) - 1
        # Fresh liquidity event:
        # accept sweep from current closed candle back through last 4 candles.
        if latest_sweep.candle_index < last_index - 4:
            latest_sweep = None

    bullish_pattern = None
    bearish_pattern = None

    # Confirmation may form ON the sweep candle
    # or within the following 1-2 closed 5m candles.
    if latest_sweep is not None:

        sweep_i = latest_sweep.candle_index
        end_i = min(len(candles_5m) - 1, sweep_i + 2)

        confirmation_hits = []

        for i in range(sweep_i, end_i + 1):

            # detect_patterns needs up to 3 candles
            start_i = max(0, i - 2)

            window = candles_5m[start_i:i + 1]

            if len(window) < 3:
                continue

            hits = detect_patterns(window)

            for hit in hits:
                confirmation_hits.append(
                    (i, hit)
                )

        bullish_candidates = [
            hit
            for _, hit in confirmation_hits
            if hit.direction == "LONG"
        ]

        bearish_candidates = [
            hit
            for _, hit in confirmation_hits
            if hit.direction == "SHORT"
        ]

        bullish_pattern = max(
            bullish_candidates,
            key=lambda x: x.score,
            default=None,
        )

        bearish_pattern = max(
            bearish_candidates,
            key=lambda x: x.score,
            default=None,
        )

    support = nearest_zone(
        price,
        sr_zones,
        {"SUPPORT"},
    )

    resistance = nearest_zone(
        price,
        sr_zones,
        {"RESISTANCE"},
    )

    bullish_fvg = nearest_zone(
        price,
        fvg_zones,
        {"BULLISH_FVG"},
    )

    bearish_fvg = nearest_zone(
        price,
        fvg_zones,
        {"BEARISH_FVG"},
    )

    # ---------------------------------------------------------
    # LONG SETUP
    # ---------------------------------------------------------

    if (
        bias_1h == "BULLISH"
        and structure_15m.trend in {"BULLISH", "NEUTRAL"}
        and latest_sweep is not None
        and latest_sweep.direction == "BULLISH"
        and bullish_pattern is not None
    ):
        score = 0
        reasons: list[str] = []

        score += 25
        reasons.append("1H_BULLISH_BIAS")

        if structure_15m.trend == "BULLISH":
            score += 20
            reasons.append("15M_BULLISH_STRUCTURE")

        if structure_15m.choch == "BULLISH":
            score += 10
            reasons.append("15M_BULLISH_CHOCH")

        score += 25
        reasons.append("5M_BULLISH_LIQUIDITY_SWEEP")

        score += min(20, bullish_pattern.score // 5)
        reasons.append(bullish_pattern.name)

        context_zone = None

        if bullish_fvg is not None and (
            bullish_fvg.low <= price <= bullish_fvg.high
            or abs(price - bullish_fvg.high) / max(price, 1e-12) <= 0.0015
        ):
            score += 10
            reasons.append("BULLISH_FVG_CONTEXT")
            context_zone = "BULLISH_FVG"

        elif support is not None and (
            support.low <= price <= support.high
            or min(abs(price - support.low), abs(price - support.high))
               / max(price, 1e-12) <= 0.0015
        ):
            score += 10
            reasons.append("SUPPORT_CONTEXT")
            context_zone = "SUPPORT"

        else:
            return None

        score = min(score, 100)

        stop_loss = min(
            current.low,
            latest_sweep.level,
        )

        return PriceActionSetup(
            side="LONG",
            score=score,
            entry=price,
            stop_loss=stop_loss,
            reason=tuple(reasons),
            pattern=bullish_pattern.name,
            htf_bias=bias_1h,
            structure_bias=structure_15m.trend,
            sweep_level=latest_sweep.level,
            context_zone=context_zone,
        )

    # ---------------------------------------------------------
    # SHORT SETUP
    # ---------------------------------------------------------

    if (
        bias_1h == "BEARISH"
        and structure_15m.trend in {"BEARISH", "NEUTRAL"}
        and latest_sweep is not None
        and latest_sweep.direction == "BEARISH"
        and bearish_pattern is not None
    ):
        score = 0
        reasons: list[str] = []

        score += 25
        reasons.append("1H_BEARISH_BIAS")

        if structure_15m.trend == "BEARISH":
            score += 20
            reasons.append("15M_BEARISH_STRUCTURE")

        if structure_15m.choch == "BEARISH":
            score += 10
            reasons.append("15M_BEARISH_CHOCH")

        score += 25
        reasons.append("5M_BEARISH_LIQUIDITY_SWEEP")

        score += min(20, bearish_pattern.score // 5)
        reasons.append(bearish_pattern.name)

        context_zone = None

        if bearish_fvg is not None and (
            bearish_fvg.low <= price <= bearish_fvg.high
            or abs(price - bearish_fvg.low) / max(price, 1e-12) <= 0.0015
        ):
            score += 10
            reasons.append("BEARISH_FVG_CONTEXT")
            context_zone = "BEARISH_FVG"

        elif resistance is not None and (
            resistance.low <= price <= resistance.high
            or min(abs(price - resistance.low), abs(price - resistance.high))
               / max(price, 1e-12) <= 0.0015
        ):
            score += 10
            reasons.append("RESISTANCE_CONTEXT")
            context_zone = "RESISTANCE"

        else:
            return None

        score = min(score, 100)

        stop_loss = max(
            current.high,
            latest_sweep.level,
        )

        return PriceActionSetup(
            side="SHORT",
            score=score,
            entry=price,
            stop_loss=stop_loss,
            reason=tuple(reasons),
            pattern=bearish_pattern.name,
            htf_bias=bias_1h,
            structure_bias=structure_15m.trend,
            sweep_level=latest_sweep.level,
            context_zone=context_zone,
        )

    return None
