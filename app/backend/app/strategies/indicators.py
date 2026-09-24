from decimal import Decimal


IndicatorSeries = tuple[Decimal | None, ...]


def ema(values: tuple[Decimal, ...], period: int) -> IndicatorSeries:
    """Return an EMA seeded by the first period's SMA, without future values."""
    if period < 1:
        raise ValueError("period must be positive")
    result: list[Decimal | None] = [None] * len(values)
    if len(values) < period:
        return tuple(result)

    current = sum(values[:period], Decimal(0)) / Decimal(period)
    result[period - 1] = current
    multiplier = Decimal(2) / Decimal(period + 1)
    for index in range(period, len(values)):
        current = (values[index] - current) * multiplier + current
        result[index] = current
    return tuple(result)


def rsi(values: tuple[Decimal, ...], period: int = 14) -> IndicatorSeries:
    """Return Wilder RSI values; the first valid value is at index ``period``."""
    if period < 1:
        raise ValueError("period must be positive")
    result: list[Decimal | None] = [None] * len(values)
    if len(values) <= period:
        return tuple(result)

    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(change, Decimal(0)) for change in changes]
    losses = [max(-change, Decimal(0)) for change in changes]
    average_gain = sum(gains[:period], Decimal(0)) / Decimal(period)
    average_loss = sum(losses[:period], Decimal(0)) / Decimal(period)
    result[period] = _rsi_value(average_gain, average_loss)

    for index in range(period + 1, len(values)):
        change_index = index - 1
        average_gain = (
            average_gain * Decimal(period - 1) + gains[change_index]
        ) / Decimal(period)
        average_loss = (
            average_loss * Decimal(period - 1) + losses[change_index]
        ) / Decimal(period)
        result[index] = _rsi_value(average_gain, average_loss)
    return tuple(result)


def adx(
    highs: tuple[Decimal, ...],
    lows: tuple[Decimal, ...],
    closes: tuple[Decimal, ...],
    period: int = 14,
) -> IndicatorSeries:
    """Return Wilder ADX; 28 candles are needed for the first ADX(14)."""
    if period < 1:
        raise ValueError("period must be positive")
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("high, low, and close series must have equal lengths")

    length = len(closes)
    result: list[Decimal | None] = [None] * length
    if length < period * 2:
        return tuple(result)

    true_ranges = [Decimal(0)] * length
    plus_dm = [Decimal(0)] * length
    minus_dm = [Decimal(0)] * length
    for index in range(1, length):
        up_move = highs[index] - highs[index - 1]
        down_move = lows[index - 1] - lows[index]
        plus_dm[index] = up_move if up_move > down_move and up_move > 0 else Decimal(0)
        minus_dm[index] = down_move if down_move > up_move and down_move > 0 else Decimal(0)
        true_ranges[index] = max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        )

    smoothed_tr = sum(true_ranges[1 : period + 1], Decimal(0))
    smoothed_plus = sum(plus_dm[1 : period + 1], Decimal(0))
    smoothed_minus = sum(minus_dm[1 : period + 1], Decimal(0))
    dx_values: list[Decimal] = []

    for index in range(period, length):
        if index > period:
            smoothed_tr = (
                smoothed_tr - smoothed_tr / Decimal(period) + true_ranges[index]
            )
            smoothed_plus = (
                smoothed_plus - smoothed_plus / Decimal(period) + plus_dm[index]
            )
            smoothed_minus = (
                smoothed_minus - smoothed_minus / Decimal(period) + minus_dm[index]
            )
        dx_values.append(_dx(smoothed_tr, smoothed_plus, smoothed_minus))
        if len(dx_values) == period:
            result[index] = sum(dx_values, Decimal(0)) / Decimal(period)
        elif len(dx_values) > period:
            previous_adx = result[index - 1]
            assert previous_adx is not None
            result[index] = (
                previous_adx * Decimal(period - 1) + dx_values[-1]
            ) / Decimal(period)
    return tuple(result)


def moving_average(values: tuple[Decimal, ...], period: int) -> IndicatorSeries:
    """Return a trailing simple average using only the current and prior values."""
    if period < 1:
        raise ValueError("period must be positive")
    result: list[Decimal | None] = [None] * len(values)
    running = Decimal(0)
    for index, value in enumerate(values):
        running += value
        if index >= period:
            running -= values[index - period]
        if index >= period - 1:
            result[index] = running / Decimal(period)
    return tuple(result)


def _rsi_value(average_gain: Decimal, average_loss: Decimal) -> Decimal:
    if average_loss == 0:
        return Decimal(50) if average_gain == 0 else Decimal(100)
    relative_strength = average_gain / average_loss
    return Decimal(100) - Decimal(100) / (Decimal(1) + relative_strength)


def _dx(
    smoothed_tr: Decimal,
    smoothed_plus: Decimal,
    smoothed_minus: Decimal,
) -> Decimal:
    if smoothed_tr == 0:
        return Decimal(0)
    plus_di = Decimal(100) * smoothed_plus / smoothed_tr
    minus_di = Decimal(100) * smoothed_minus / smoothed_tr
    total = plus_di + minus_di
    return Decimal(0) if total == 0 else Decimal(100) * abs(plus_di - minus_di) / total
