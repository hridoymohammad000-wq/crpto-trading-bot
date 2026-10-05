from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Candle:
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class PatternHit:
    name: str
    direction: str
    score: int


def body(c: Candle) -> float:
    return abs(c.close - c.open)


def candle_range(c: Candle) -> float:
    return max(c.high - c.low, 1e-12)


def upper_wick(c: Candle) -> float:
    return c.high - max(c.open, c.close)


def lower_wick(c: Candle) -> float:
    return min(c.open, c.close) - c.low


def bullish(c: Candle) -> bool:
    return c.close > c.open


def bearish(c: Candle) -> bool:
    return c.close < c.open


def bullish_engulfing(prev: Candle, cur: Candle) -> bool:
    return (
        bearish(prev)
        and bullish(cur)
        and cur.open <= prev.close
        and cur.close >= prev.open
    )


def bearish_engulfing(prev: Candle, cur: Candle) -> bool:
    return (
        bullish(prev)
        and bearish(cur)
        and cur.open >= prev.close
        and cur.close <= prev.open
    )


def hammer(c: Candle) -> bool:
    b = body(c)
    return (
        b > 0
        and lower_wick(c) >= b * 2
        and upper_wick(c) <= b * 0.75
        and max(c.open, c.close) >= c.low + candle_range(c) * 0.55
    )


def shooting_star(c: Candle) -> bool:
    b = body(c)
    return (
        b > 0
        and upper_wick(c) >= b * 2
        and lower_wick(c) <= b * 0.75
        and min(c.open, c.close) <= c.low + candle_range(c) * 0.45
    )


def bullish_harami(prev: Candle, cur: Candle) -> bool:
    return (
        bearish(prev)
        and bullish(cur)
        and cur.open >= prev.close
        and cur.close <= prev.open
    )


def bearish_harami(prev: Candle, cur: Candle) -> bool:
    return (
        bullish(prev)
        and bearish(cur)
        and cur.open <= prev.close
        and cur.close >= prev.open
    )


def bullish_outside(prev: Candle, cur: Candle) -> bool:
    return bullish(cur) and cur.high > prev.high and cur.low < prev.low


def bearish_outside(prev: Candle, cur: Candle) -> bool:
    return bearish(cur) and cur.high > prev.high and cur.low < prev.low


def inside_bar(prev: Candle, cur: Candle) -> bool:
    return cur.high < prev.high and cur.low > prev.low


def tweezer_bottom(prev: Candle, cur: Candle, tolerance: float = 0.0015) -> bool:
    base = max(abs(prev.low), 1e-12)
    return (
        bearish(prev)
        and bullish(cur)
        and abs(prev.low - cur.low) / base <= tolerance
    )


def tweezer_top(prev: Candle, cur: Candle, tolerance: float = 0.0015) -> bool:
    base = max(abs(prev.high), 1e-12)
    return (
        bullish(prev)
        and bearish(cur)
        and abs(prev.high - cur.high) / base <= tolerance
    )


def morning_star(c1: Candle, c2: Candle, c3: Candle) -> bool:
    midpoint = (c1.open + c1.close) / 2
    return (
        bearish(c1)
        and body(c2) <= body(c1) * 0.5
        and bullish(c3)
        and c3.close > midpoint
    )


def evening_star(c1: Candle, c2: Candle, c3: Candle) -> bool:
    midpoint = (c1.open + c1.close) / 2
    return (
        bullish(c1)
        and body(c2) <= body(c1) * 0.5
        and bearish(c3)
        and c3.close < midpoint
    )


def three_white_soldiers(c1: Candle, c2: Candle, c3: Candle) -> bool:
    return (
        bullish(c1) and bullish(c2) and bullish(c3)
        and c2.close > c1.close
        and c3.close > c2.close
        and c2.low >= c1.low
        and c3.low >= c2.low
    )


def three_black_crows(c1: Candle, c2: Candle, c3: Candle) -> bool:
    return (
        bearish(c1) and bearish(c2) and bearish(c3)
        and c2.close < c1.close
        and c3.close < c2.close
        and c2.high <= c1.high
        and c3.high <= c2.high
    )


def detect_patterns(candles: Sequence[Candle]) -> list[PatternHit]:
    if len(candles) < 3:
        return []

    a, b, c = candles[-3], candles[-2], candles[-1]
    hits: list[PatternHit] = []

    if bullish_engulfing(b, c):
        hits.append(PatternHit("Bullish Engulfing", "LONG", 90))

    if bearish_engulfing(b, c):
        hits.append(PatternHit("Bearish Engulfing", "SHORT", 90))

    if hammer(c):
        hits.append(PatternHit("Hammer / Bullish Pin Bar", "LONG", 80))

    if shooting_star(c):
        hits.append(PatternHit("Shooting Star / Bearish Pin Bar", "SHORT", 80))

    if bullish_harami(b, c):
        hits.append(PatternHit("Bullish Harami", "LONG", 65))

    if bearish_harami(b, c):
        hits.append(PatternHit("Bearish Harami", "SHORT", 65))

    if bullish_outside(b, c):
        hits.append(PatternHit("Bullish Outside Bar", "LONG", 85))

    if bearish_outside(b, c):
        hits.append(PatternHit("Bearish Outside Bar", "SHORT", 85))

    if inside_bar(b, c):
        hits.append(PatternHit("Inside Bar", "NEUTRAL", 50))

    if tweezer_bottom(b, c):
        hits.append(PatternHit("Tweezer Bottom", "LONG", 70))

    if tweezer_top(b, c):
        hits.append(PatternHit("Tweezer Top", "SHORT", 70))

    if morning_star(a, b, c):
        hits.append(PatternHit("Morning Star", "LONG", 90))

    if evening_star(a, b, c):
        hits.append(PatternHit("Evening Star", "SHORT", 90))

    if three_white_soldiers(a, b, c):
        hits.append(PatternHit("Three White Soldiers", "LONG", 85))

    if three_black_crows(a, b, c):
        hits.append(PatternHit("Three Black Crows", "SHORT", 85))

    return hits
