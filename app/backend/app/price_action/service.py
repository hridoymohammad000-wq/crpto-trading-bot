from dataclasses import dataclass
from decimal import Decimal
import asyncio

from .patterns import Candle
from .setup import build_setup


@dataclass(frozen=True)
class ScanSignal:
    symbol: str
    side: str
    score: int
    entry: float
    stop_loss: float
    pattern: str | None
    htf_bias: str
    structure_bias: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ScanResult:
    total_tickers: int
    eligible_symbols: int
    scanned_symbols: int
    failed_symbols: int
    signals: tuple[ScanSignal, ...]


class PriceActionScanner:

    STABLE_EXCLUDES = {
        "USDCUSDT",
        "BUSDUSDT",
        "DAIUSDT",
        "TUSDUSDT",
        "USDEUSDT",
        "FDUSDUSDT",
    }

    def __init__(
        self,
        market_data_service,
        *,
        min_turnover: Decimal = Decimal("10000000"),
        max_spread_pct: Decimal = Decimal("0.15"),
        max_symbols: int = 50,
        concurrency: int = 8,
    ):
        self.market = market_data_service
        self.min_turnover = min_turnover
        self.max_spread_pct = max_spread_pct
        self.max_symbols = max_symbols
        self.sem = asyncio.Semaphore(concurrency)

    @staticmethod
    def _convert(rows):
        return [
            Candle(
                open=float(x.open),
                high=float(x.high),
                low=float(x.low),
                close=float(x.close),
            )
            for x in rows
        ]

    async def _scan_symbol(self, symbol: str):
        try:
            async with self.sem:
                c1h, c15, c5 = await asyncio.gather(
                    self.market.fetch_candles(
                        symbol,
                        "1H",
                        limit=80,
                        closed_only=True,
                    ),
                    self.market.fetch_candles(
                        symbol,
                        "15m",
                        limit=100,
                        closed_only=True,
                    ),
                    self.market.fetch_candles(
                        symbol,
                        "5m",
                        limit=150,
                        closed_only=True,
                    ),
                )

            setup = build_setup(
                self._convert(c1h),
                self._convert(c15),
                self._convert(c5),
            )

            if setup is None:
                return symbol, None, None

            return (
                symbol,
                ScanSignal(
                    symbol=symbol,
                    side=setup.side,
                    score=setup.score,
                    entry=setup.entry,
                    stop_loss=setup.stop_loss,
                    pattern=setup.pattern,
                    htf_bias=setup.htf_bias,
                    structure_bias=setup.structure_bias,
                    reasons=setup.reason,
                ),
                None,
            )

        except Exception as exc:
            return symbol, None, f"{type(exc).__name__}: {exc}"

    async def scan(self) -> ScanResult:

        tickers, instruments = await asyncio.gather(
            self.market.fetch_all_tickers(),
            self.market.fetch_all_instruments(),
        )

        valid_instruments = {
            x.symbol for x in instruments
        }

        eligible = []

        for t in tickers:
            if t.symbol not in valid_instruments:
                continue

            if t.symbol in self.STABLE_EXCLUDES:
                continue

            if not t.symbol.endswith("USDT"):
                continue

            turnover = t.turnover_24h or Decimal(0)

            if turnover < self.min_turnover:
                continue

            bid = t.bid_price or Decimal(0)
            ask = t.ask_price or Decimal(0)

            if bid <= 0 or ask <= 0:
                continue

            spread = (ask - bid) / bid * Decimal(100)

            if spread > self.max_spread_pct:
                continue

            eligible.append((t.symbol, turnover))

        # Highest liquidity first.
        eligible.sort(
            key=lambda x: x[1],
            reverse=True,
        )

        symbols = [
            x[0]
            for x in eligible[: self.max_symbols]
        ]

        results = await asyncio.gather(
            *(self._scan_symbol(symbol) for symbol in symbols)
        )

        signals = []
        failed = 0

        for symbol, signal, error in results:

            if error:
                failed += 1
                print(
                    "FETCH FAIL:",
                    symbol,
                    error,
                )
                continue

            if signal:
                signals.append(signal)

        signals.sort(
            key=lambda x: x.score,
            reverse=True,
        )

        return ScanResult(
            total_tickers=len(tickers),
            eligible_symbols=len(eligible),
            scanned_symbols=len(symbols),
            failed_symbols=failed,
            signals=tuple(signals),
        )




