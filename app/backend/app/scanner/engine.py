import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from app.market_data.service import MarketDataService
from app.scanner.models import MarketRegime, ScannerOpportunity, SetupState, SymbolState, WatchlistState
from app.scanner.state_machine import PipelineStateMachine
from app.strategies.indicators import adx, ema, moving_average, rsi


class ScannerEngine:
    def __init__(self, market_data: MarketDataService, *, min_turnover: Decimal = Decimal("10000000"), max_spread_pct: Decimal = Decimal("0.10"), dynamic_limit: int = 12, cooldown_minutes: int = 60, execution_allowlist: set[str] | None = None, execution_selection_mode: str = "STATIC"):
        self._market_data = market_data
        self._min_turnover = min_turnover
        self._max_spread_pct = max_spread_pct
        self._dynamic_limit = dynamic_limit
        self._cooldown_minutes = cooldown_minutes
        self._execution_allowlist = execution_allowlist or {"BTCUSDT"}
        self._execution_selection_mode = execution_selection_mode.strip().upper()
        self.watchlist = WatchlistState()
        self.universe: list[ScannerOpportunity] = []
        self._last_universe_refresh: datetime | None = None

    def _is_execution_allowed(self, symbol: str) -> bool:
        if symbol in self.watchlist.cooldown_symbols:
            return False
        if self._execution_selection_mode == "STATIC":
            return symbol in self._execution_allowlist
        # SCANNER mode: only the current monitored opportunity pool may execute.
        # This is Core 3 + ranked dynamic candidates; Risk Engine still decides READY/REJECTED.
        return symbol in self.watchlist.core_symbols or symbol in self.watchlist.dynamic_symbols

    def get_or_create_state(self, symbol: str) -> SymbolState:
        state = self.watchlist.symbol_states.get(symbol)
        allowed = self._is_execution_allowed(symbol)
        if state is None:
            state = SymbolState(symbol=symbol, execution_allowed=allowed)
            self.watchlist.symbol_states[symbol] = state
        else:
            state.execution_allowed = allowed
        return state

    def refresh_execution_permissions(self) -> None:
        for symbol, state in self.watchlist.symbol_states.items():
            state.execution_allowed = self._is_execution_allowed(symbol)

    def release_expired_cooldowns(self, *, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        for symbol, until in list(self.watchlist.cooldown_symbols.items()):
            state = self.get_or_create_state(symbol)
            state.cooldown_until = until
            if PipelineStateMachine.release_cooldown(state, now=now):
                self.watchlist.cooldown_symbols.pop(symbol, None)

    def enter_cooldown(self, symbol: str, *, now: datetime | None = None) -> datetime:
        state = self.get_or_create_state(symbol)
        until = PipelineStateMachine.enter_cooldown(state, self._cooldown_minutes, now=now)
        self.watchlist.cooldown_symbols[symbol] = until
        return until

    async def refresh_universe(self) -> None:
        tickers, instruments = await asyncio.gather(self._market_data.fetch_all_tickers(), self._market_data.fetch_all_instruments())
        instrument_symbols = {inst.symbol for inst in instruments}
        stable_excludes = {"USDCUSDT", "BUSDUSDT", "DAIUSDT", "TUSDUSDT", "USDEUSDT", "FDUSDUSDT"}
        sem = asyncio.Semaphore(10)

        async def evaluate(t):
            reasons: list[str] = []
            turnover = t.turnover_24h or Decimal(0)
            bid, ask = t.bid_price or Decimal(0), t.ask_price or Decimal(0)
            spread = ((ask - bid) / bid * Decimal(100)) if bid > 0 and ask > 0 else Decimal(999)
            if t.symbol not in instrument_symbols: reasons.append("INVALID_INSTRUMENT")
            if t.symbol in stable_excludes: reasons.append("STABLECOIN_PAIR")
            if turnover < self._min_turnover: reasons.append("LOW_TURNOVER")
            if bid <= 0 or ask <= 0: reasons.append("NO_LIQUIDITY")
            elif spread > self._max_spread_pct: reasons.append("HIGH_SPREAD")
            if reasons and t.symbol not in self.watchlist.core_symbols:
                state = self.get_or_create_state(t.symbol)
                return ScannerOpportunity(t.symbol, t.last_price, spread, turnover, t.volume_24h or Decimal(0), None, None, None, MarketRegime.UNKNOWN, None, 0, 0, state.state, tuple(reasons))
            try:
                async with sem:
                    candles = await self._market_data.fetch_candles(t.symbol, "15m", limit=30, closed_only=True)
            except Exception:
                state = self.get_or_create_state(t.symbol)
                return ScannerOpportunity(t.symbol, t.last_price, spread, turnover, t.volume_24h or Decimal(0), None, None, None, MarketRegime.UNKNOWN, None, 0, 0, state.state, ("FETCH_ERROR",))
            if len(candles) < 22:
                state = self.get_or_create_state(t.symbol)
                return ScannerOpportunity(t.symbol, t.last_price, spread, turnover, t.volume_24h or Decimal(0), None, None, None, MarketRegime.UNKNOWN, None, 0, 0, state.state, ("INSUFFICIENT_HISTORY",))
            closes = tuple(c.close for c in candles); highs=tuple(c.high for c in candles); lows=tuple(c.low for c in candles); volumes=tuple(c.volume for c in candles)
            fast=ema(closes,9)[-1]; slow=ema(closes,21)[-1]; adx_val=adx(highs,lows,closes,14)[-1]; avg=moving_average(volumes,20)[-1]; rsi_val=rsi(closes,14)[-1]
            trs=[]
            for i in range(1,len(candles)):
                trs.append(max(candles[i].high-candles[i].low, abs(candles[i].high-candles[i-1].close), abs(candles[i].low-candles[i-1].close)))
            atr=sum(trs[-14:])/Decimal(len(trs[-14:])) if trs else Decimal(0)
            atr_pct=(atr/closes[-1]*Decimal(100)) if closes[-1]>0 else Decimal(0)
            rvol=(volumes[-1]/avg) if avg and avg>0 else Decimal(0)
            
            # RSI confirmation logic
            rsi_score = 0
            if rsi_val is not None:
                if fast is not None and slow is not None and fast > slow and rsi_val > Decimal(50):
                    rsi_score = 15
                elif fast is not None and slow is not None and fast < slow and rsi_val < Decimal(50):
                    rsi_score = 15

            if atr_pct > Decimal("2.5"): regime=MarketRegime.HIGH_VOLATILITY
            elif adx_val is not None and adx_val < Decimal("20"): regime=MarketRegime.RANGING
            elif fast is not None and slow is not None and fast>slow and closes[-1]>fast and adx_val is not None and adx_val>=Decimal("20"): regime=MarketRegime.TRENDING_UP
            elif fast is not None and slow is not None and fast<slow and closes[-1]<fast and adx_val is not None and adx_val>=Decimal("20"): regime=MarketRegime.TRENDING_DOWN
            else: regime=MarketRegime.LOW_ACTIVITY
            bias="LONG" if fast is not None and slow is not None and fast>slow else "SHORT" if fast is not None and slow is not None and fast<slow else "NEUTRAL"
            turnover_score=min(50, int(turnover/Decimal("10000000")))
            spread_score=50 if spread < Decimal("0.02") else max(0,50-int(spread*1000))
            market_score=min(100,turnover_score+spread_score)
            
            # Incorporate RSI into setup_score
            base_setup = (min(40,int(adx_val)) if adx_val else 0)+(min(30,int(rvol*10)) if rvol else 0)+(30 if regime in {MarketRegime.TRENDING_UP,MarketRegime.TRENDING_DOWN} else 0)
            setup_score = min(100, base_setup + rsi_score)
            state=self.get_or_create_state(t.symbol); state.regime=regime; state.bias=bias; state.market_quality_score=market_score; state.setup_quality_score=setup_score; state.spread_pct=spread; state.atr_pct=atr_pct
            return ScannerOpportunity(t.symbol,t.last_price,spread,turnover,t.volume_24h or Decimal(0),atr_pct,rvol,adx_val,regime,bias,market_score,setup_score,state.state,tuple(reasons))

        self.release_expired_cooldowns()
        self.universe = list(await asyncio.gather(*(evaluate(t) for t in tickers)))
        self._last_universe_refresh = datetime.now(timezone.utc)
        self._update_watchlist()

    def _update_watchlist(self) -> None:
        # Preserve active states even if ranking changes.
        preserved = {s for s, st in self.watchlist.symbol_states.items() if st.state in {SetupState.ARMED, SetupState.TRIGGERED, SetupState.EXECUTED, SetupState.COOLDOWN}}
        eligible=[o for o in self.universe if not o.reason_codes]
        # Deliberate lexicographic ranking keeps market/setup scores separately interpretable.
        eligible.sort(key=lambda o: (o.setup_quality_score, o.market_quality_score), reverse=True)
        dynamic=[]
        for o in eligible:
            if o.symbol in self.watchlist.core_symbols or o.symbol in self.watchlist.open_position_symbols or o.symbol in self.watchlist.cooldown_symbols:
                continue
            dynamic.append(o.symbol)
            if len(dynamic)>=self._dynamic_limit: break
        self.watchlist.dynamic_symbols = (set(dynamic) | (preserved - self.watchlist.core_symbols - self.watchlist.open_position_symbols))
        for symbol in self.watchlist.all_monitored:
            self.get_or_create_state(symbol)
        self.refresh_execution_permissions()
