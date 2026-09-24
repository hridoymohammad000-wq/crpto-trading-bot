from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class SymbolEligibility(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    REJECTED = "REJECTED"


class MarketRegime(str, Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_ACTIVITY = "LOW_ACTIVITY"
    UNKNOWN = "UNKNOWN"


class SetupState(str, Enum):
    DISCOVERED = "DISCOVERED"
    WATCHING = "WATCHING"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    EXECUTED = "EXECUTED"
    INVALIDATED = "INVALIDATED"
    COOLDOWN = "COOLDOWN"


@dataclass
class SymbolState:
    symbol: str
    state: SetupState = SetupState.DISCOVERED
    regime: MarketRegime = MarketRegime.UNKNOWN
    bias: str | None = None
    market_quality_score: int = 0
    setup_quality_score: int = 0
    execution_allowed: bool = False
    last_processed_15m: datetime | None = None
    last_processed_5m: datetime | None = None
    last_processed_1m: datetime | None = None
    context_15m: dict[str, Any] = field(default_factory=dict)
    setup_5m: dict[str, Any] = field(default_factory=dict)
    trigger_1m: dict[str, Any] = field(default_factory=dict)
    execution_diagnostics: dict[str, Any] = field(default_factory=dict)
    spread_pct: Decimal = Decimal("0")
    atr_pct: Decimal | None = None
    reason_codes: list[str] = field(default_factory=list)
    cooldown_until: datetime | None = None


@dataclass(frozen=True)
class ScannerOpportunity:
    symbol: str
    price: Decimal
    spread_pct: Decimal
    turnover_24h: Decimal
    volume_24h: Decimal
    atr_pct: Decimal | None
    rvol: Decimal | None
    adx: Decimal | None
    regime: MarketRegime
    bias: str | None
    market_quality_score: int
    setup_quality_score: int
    state: SetupState
    reason_codes: tuple[str, ...]


@dataclass
class WatchlistState:
    core_symbols: set[str] = field(default_factory=lambda: {"BTCUSDT", "ETHUSDT", "SOLUSDT"})
    dynamic_symbols: set[str] = field(default_factory=set)
    open_position_symbols: set[str] = field(default_factory=set)
    cooldown_symbols: dict[str, datetime] = field(default_factory=dict)
    symbol_states: dict[str, SymbolState] = field(default_factory=dict)

    @property
    def all_monitored(self) -> set[str]:
        return self.core_symbols | self.dynamic_symbols | self.open_position_symbols | set(self.cooldown_symbols)
