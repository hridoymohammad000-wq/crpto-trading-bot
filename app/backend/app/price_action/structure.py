from dataclasses import dataclass
from typing import Sequence, Literal

from .patterns import Candle


StructureLabel = Literal["HH", "HL", "LH", "LL"]
Direction = Literal["BULLISH", "BEARISH", "NEUTRAL"]


@dataclass(frozen=True)
class SwingPoint:
    index: int
    price: float
    kind: Literal["HIGH", "LOW"]
    label: StructureLabel | None = None


@dataclass(frozen=True)
class StructureResult:
    trend: Direction
    swings: tuple[SwingPoint, ...]
    bos: Direction | None
    choch: Direction | None
    last_swing_high: float | None
    last_swing_low: float | None


def find_swings(
    candles: Sequence[Candle],
    left: int = 3,
    right: int = 3,
) -> list[SwingPoint]:
    swings: list[SwingPoint] = []

    if len(candles) < left + right + 1:
        return swings

    for i in range(left, len(candles) - right):
        c = candles[i]

        left_slice = candles[i-left:i]
        right_slice = candles[i+1:i+right+1]

        is_high = all(c.high > x.high for x in left_slice) and all(
            c.high >= x.high for x in right_slice
        )

        is_low = all(c.low < x.low for x in left_slice) and all(
            c.low <= x.low for x in right_slice
        )

        if is_high:
            swings.append(SwingPoint(i, c.high, "HIGH"))

        if is_low:
            swings.append(SwingPoint(i, c.low, "LOW"))

    swings.sort(key=lambda x: x.index)
    return swings


def label_structure(swings: Sequence[SwingPoint]) -> list[SwingPoint]:
    out: list[SwingPoint] = []

    last_high: float | None = None
    last_low: float | None = None

    for s in swings:
        label: StructureLabel | None = None

        if s.kind == "HIGH":
            if last_high is not None:
                label = "HH" if s.price > last_high else "LH"
            last_high = s.price

        elif s.kind == "LOW":
            if last_low is not None:
                label = "HL" if s.price > last_low else "LL"
            last_low = s.price

        out.append(
            SwingPoint(
                index=s.index,
                price=s.price,
                kind=s.kind,
                label=label,
            )
        )

    return out


def infer_trend(swings: Sequence[SwingPoint]) -> Direction:
    labeled = [s for s in swings if s.label is not None]

    if len(labeled) < 2:
        return "NEUTRAL"

    recent = labeled[-4:]
    labels = [s.label for s in recent]

    bullish_count = sum(x in {"HH", "HL"} for x in labels)
    bearish_count = sum(x in {"LH", "LL"} for x in labels)

    if bullish_count >= 3 and bullish_count > bearish_count:
        return "BULLISH"

    if bearish_count >= 3 and bearish_count > bullish_count:
        return "BEARISH"

    return "NEUTRAL"


def detect_breaks(
    candles: Sequence[Candle],
    swings: Sequence[SwingPoint],
    prior_trend: Direction,
) -> tuple[Direction | None, Direction | None]:
    if not candles or not swings:
        return None, None

    close = candles[-1].close

    highs = [s for s in swings if s.kind == "HIGH" and s.index < len(candles) - 1]
    lows = [s for s in swings if s.kind == "LOW" and s.index < len(candles) - 1]

    if not highs or not lows:
        return None, None

    last_high = highs[-1].price
    last_low = lows[-1].price

    bos: Direction | None = None
    choch: Direction | None = None

    if close > last_high:
        if prior_trend == "BULLISH":
            bos = "BULLISH"
        elif prior_trend == "BEARISH":
            choch = "BULLISH"
        else:
            bos = "BULLISH"

    elif close < last_low:
        if prior_trend == "BEARISH":
            bos = "BEARISH"
        elif prior_trend == "BULLISH":
            choch = "BEARISH"
        else:
            bos = "BEARISH"

    return bos, choch


def analyze_structure(
    candles: Sequence[Candle],
    left: int = 3,
    right: int = 3,
) -> StructureResult:

    raw_swings = find_swings(candles, left=left, right=right)
    swings = label_structure(raw_swings)

    trend = infer_trend(swings)
    bos, choch = detect_breaks(candles, swings, trend)

    highs = [s.price for s in swings if s.kind == "HIGH"]
    lows = [s.price for s in swings if s.kind == "LOW"]

    return StructureResult(
        trend=trend,
        swings=tuple(swings),
        bos=bos,
        choch=choch,
        last_swing_high=highs[-1] if highs else None,
        last_swing_low=lows[-1] if lows else None,
    )
