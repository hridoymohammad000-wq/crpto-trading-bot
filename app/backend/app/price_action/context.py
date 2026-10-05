from dataclasses import dataclass
from typing import Sequence, Literal

from .patterns import Candle
from .structure import SwingPoint, analyze_structure


Direction = Literal["BULLISH", "BEARISH"]


@dataclass(frozen=True)
class Zone:
    kind: Literal["SUPPORT", "RESISTANCE", "BULLISH_FVG", "BEARISH_FVG"]
    low: float
    high: float
    source_index: int


@dataclass(frozen=True)
class Sweep:
    direction: Direction
    level: float
    candle_index: int
    reclaimed: bool


def atr(candles: Sequence[Candle], period: int = 14) -> list[float]:
    if not candles:
        return []

    values: list[float] = [candles[0].high - candles[0].low]

    for i in range(1, len(candles)):
        c = candles[i]
        prev = candles[i - 1]
        tr = max(
            c.high - c.low,
            abs(c.high - prev.close),
            abs(c.low - prev.close),
        )
        values.append(tr)

    out: list[float] = []

    for i in range(len(values)):
        if i + 1 < period:
            out.append(sum(values[: i + 1]) / (i + 1))
        else:
            out.append(sum(values[i - period + 1 : i + 1]) / period)

    return out


def build_sr_zones(
    candles: Sequence[Candle],
    swings: Sequence[SwingPoint] | None = None,
    atr_mult: float = 0.25,
) -> list[Zone]:

    if swings is None:
        swings = analyze_structure(candles).swings

    atr_values = atr(candles)
    zones: list[Zone] = []

    for s in swings:
        if s.index >= len(atr_values):
            continue

        width = atr_values[s.index] * atr_mult

        if s.kind == "LOW":
            zones.append(
                Zone(
                    kind="SUPPORT",
                    low=s.price - width,
                    high=s.price + width,
                    source_index=s.index,
                )
            )

        elif s.kind == "HIGH":
            zones.append(
                Zone(
                    kind="RESISTANCE",
                    low=s.price - width,
                    high=s.price + width,
                    source_index=s.index,
                )
            )

    return zones


def detect_fvgs(
    candles: Sequence[Candle],
    min_atr_mult: float = 0.30,
    max_atr_mult: float = 3.0,
) -> list[Zone]:

    if len(candles) < 3:
        return []

    atr_values = atr(candles)
    zones: list[Zone] = []

    for i in range(1, len(candles) - 1):
        prev = candles[i - 1]
        nxt = candles[i + 1]

        a = atr_values[i]
        if a <= 0:
            continue

        # Bullish FVG: candle i+1 low > candle i-1 high
        if nxt.low > prev.high:
            width = nxt.low - prev.high

            if a * min_atr_mult <= width <= a * max_atr_mult:
                zones.append(
                    Zone(
                        kind="BULLISH_FVG",
                        low=prev.high,
                        high=nxt.low,
                        source_index=i + 1,
                    )
                )

        # Bearish FVG: candle i+1 high < candle i-1 low
        if nxt.high < prev.low:
            width = prev.low - nxt.high

            if a * min_atr_mult <= width <= a * max_atr_mult:
                zones.append(
                    Zone(
                        kind="BEARISH_FVG",
                        low=nxt.high,
                        high=prev.low,
                        source_index=i + 1,
                    )
                )

    return zones


def detect_liquidity_sweeps(
    candles: Sequence[Candle],
    swings: Sequence[SwingPoint] | None = None,
    min_atr_fraction: float = 0.10,
) -> list[Sweep]:

    if len(candles) < 2:
        return []

    if swings is None:
        swings = analyze_structure(candles).swings

    atr_values = atr(candles)
    sweeps: list[Sweep] = []

    confirmed_swings = [s for s in swings if s.index < len(candles) - 1]

    for i in range(1, len(candles)):
        c = candles[i]
        a = atr_values[i]

        if a <= 0:
            continue

        prior_highs = [
            s for s in confirmed_swings
            if s.kind == "HIGH" and s.index < i
        ]

        prior_lows = [
            s for s in confirmed_swings
            if s.kind == "LOW" and s.index < i
        ]

        if prior_lows:
            level = prior_lows[-1].price

            swept = c.low < level - (a * min_atr_fraction)
            reclaimed = c.close > level

            if swept and reclaimed:
                sweeps.append(
                    Sweep(
                        direction="BULLISH",
                        level=level,
                        candle_index=i,
                        reclaimed=True,
                    )
                )

        if prior_highs:
            level = prior_highs[-1].price

            swept = c.high > level + (a * min_atr_fraction)
            reclaimed = c.close < level

            if swept and reclaimed:
                sweeps.append(
                    Sweep(
                        direction="BEARISH",
                        level=level,
                        candle_index=i,
                        reclaimed=True,
                    )
                )

    return sweeps


def price_in_zone(price: float, zone: Zone) -> bool:
    return zone.low <= price <= zone.high


def nearest_zone(
    price: float,
    zones: Sequence[Zone],
    kinds: set[str] | None = None,
) -> Zone | None:

    candidates = list(zones)

    if kinds is not None:
        candidates = [z for z in candidates if z.kind in kinds]

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda z: min(abs(price - z.low), abs(price - z.high)),
    )
