from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN

from app.account import AccountService
from app.market_data import MarketDataService
from app.models.account import PositionResponse
from app.models.risk import RiskDecision, RiskDecisionStatus, RiskRejectReason
from app.models.signal import SignalSide, StrategySignal
from app.persistence import PersistenceDatabase


class RiskService:
    """Pre-execution risk authority.

    Position size is derived from structural stop distance and per-trade risk.
    Portfolio risk is measured as stop-distance loss for each managed open
    position plus a configurable fee/slippage allowance on notional exposure.
    The same allowance is applied to a proposed entry before margin and total
    open-risk checks.
    """

    def __init__(
        self,
        account_service: AccountService,
        market_data: MarketDataService,
        *,
        risk_per_trade_pct: Decimal = Decimal("1"),
        daily_loss_limit_pct: Decimal = Decimal("3"),
        minimum_rr: Decimal = Decimal("2"),
        leverage: Decimal = Decimal("3"),
        max_leverage: Decimal = Decimal("10"),
        max_active_positions: int = 3,
        max_open_risk_pct: Decimal = Decimal("3"),
        fee_buffer_pct: Decimal = Decimal("0.20"),
        slippage_buffer_pct: Decimal = Decimal("0.10"),
        structure_lookback: int = 5,
        structure_buffer_pct: Decimal = Decimal("0.10"),
        persistence: PersistenceDatabase | None = None,
    ) -> None:
        if not Decimal("0") < risk_per_trade_pct <= Decimal("100"):
            raise ValueError("risk_per_trade_pct must be in (0, 100]")
        if not Decimal("0") < daily_loss_limit_pct <= Decimal("100"):
            raise ValueError("daily_loss_limit_pct must be in (0, 100]")
        if minimum_rr < Decimal("2"):
            raise ValueError("minimum_rr must be at least 2")
        if leverage <= 0 or leverage > max_leverage or max_leverage > Decimal("10"):
            raise ValueError("leverage must be > 0 and max_leverage must be <= 10")
        if max_active_positions <= 0:
            raise ValueError("max_active_positions must be positive")
        if not Decimal("0") < max_open_risk_pct <= Decimal("100"):
            raise ValueError("max_open_risk_pct must be in (0, 100]")
        if fee_buffer_pct < 0:
            raise ValueError("fee_buffer_pct cannot be negative")
        if slippage_buffer_pct < 0:
            raise ValueError("slippage_buffer_pct cannot be negative")
        if structure_lookback < 2:
            raise ValueError("structure_lookback must be at least 2")
        if structure_buffer_pct < 0:
            raise ValueError("structure_buffer_pct cannot be negative")

        self._account_service = account_service
        self._market_data = market_data
        self.risk_per_trade_pct = risk_per_trade_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.minimum_rr = minimum_rr
        self.leverage = leverage
        self.max_leverage = max_leverage
        self.max_active_positions = max_active_positions
        self.max_open_risk_pct = max_open_risk_pct
        self.fee_buffer_pct = fee_buffer_pct
        self.slippage_buffer_pct = slippage_buffer_pct
        self.structure_lookback = structure_lookback
        self.structure_buffer_pct = structure_buffer_pct
        self._baseline_day: date | None = None
        self._day_start_equity: Decimal | None = None
        self._persistence = persistence

    async def evaluate(self, signal: StrategySignal) -> RiskDecision:
        now = datetime.now(timezone.utc)
        account = await self._account_service.get_summary()
        positions = await self._account_service.get_positions()
        equity = account.equity
        available = account.available_trading_capacity
        active_positions = len(positions)

        if equity is None or not equity.is_finite() or equity <= 0:
            return self._reject(
                signal, now, RiskRejectReason.INVALID_ACCOUNT_EQUITY,
                equity, available, active_positions,
            )
        if available is None or not available.is_finite() or available <= 0:
            return self._reject(
                signal, now, RiskRejectReason.INSUFFICIENT_AVAILABLE_BALANCE,
                equity, available, active_positions,
            )

        daily_drawdown_pct = self._daily_drawdown(now.date(), equity)
        if daily_drawdown_pct >= self.daily_loss_limit_pct:
            return self._reject(
                signal, now, RiskRejectReason.DAILY_LOSS_LIMIT,
                equity, available, active_positions,
                daily_drawdown_pct=daily_drawdown_pct,
            )

        if active_positions >= self.max_active_positions:
            return self._reject(
                signal, now, RiskRejectReason.MAX_ACTIVE_POSITIONS,
                equity, available, active_positions,
                daily_drawdown_pct=daily_drawdown_pct,
            )
        if any(position.symbol == signal.symbol for position in positions):
            return self._reject(
                signal, now, RiskRejectReason.DUPLICATE_SYMBOL_POSITION,
                equity, available, active_positions,
                daily_drawdown_pct=daily_drawdown_pct,
            )
        if self.leverage <= 0 or self.leverage > self.max_leverage or self.max_leverage > Decimal("10"):
            return self._reject(
                signal, now, RiskRejectReason.LEVERAGE_LIMIT_EXCEEDED,
                equity, available, active_positions,
                daily_drawdown_pct=daily_drawdown_pct,
            )

        portfolio_open_risk_before = self._portfolio_open_risk(positions)
        max_open_risk_amount = equity * (self.max_open_risk_pct / Decimal("100"))
        if portfolio_open_risk_before is None:
            return self._reject(
                signal, now, RiskRejectReason.OPEN_POSITION_RISK_UNKNOWN,
                equity, available, active_positions,
                daily_drawdown_pct=daily_drawdown_pct,
                max_open_risk_amount=max_open_risk_amount,
            )

        candles = await self._market_data.fetch_candles(
            signal.symbol,
            "5m",
            limit=max(self.structure_lookback, 10),
            closed_only=True,
        )
        if len(candles) < self.structure_lookback:
            return self._reject(
                signal, now, RiskRejectReason.INSUFFICIENT_STRUCTURE_DATA,
                equity, available, active_positions,
                daily_drawdown_pct=daily_drawdown_pct,
                portfolio_open_risk_before=portfolio_open_risk_before,
                max_open_risk_amount=max_open_risk_amount,
            )

        recent = candles[-self.structure_lookback :]
        entry = signal.reference_entry_price
        buffer_rate = self.structure_buffer_pct / Decimal("100")
        if signal.side == SignalSide.BUY:
            structure = min(candle.low for candle in recent)
            stop_loss = structure * (Decimal("1") - buffer_rate)
            if stop_loss <= 0 or stop_loss >= entry:
                return self._reject(
                    signal, now, RiskRejectReason.INVALID_STOP_LOSS,
                    equity, available, active_positions,
                    daily_drawdown_pct=daily_drawdown_pct,
                    portfolio_open_risk_before=portfolio_open_risk_before,
                    max_open_risk_amount=max_open_risk_amount,
                )
            risk_distance = entry - stop_loss
            take_profit = entry + (risk_distance * self.minimum_rr)
            if take_profit <= entry:
                return self._reject(
                    signal, now, RiskRejectReason.INVALID_TAKE_PROFIT,
                    equity, available, active_positions,
                    daily_drawdown_pct=daily_drawdown_pct,
                    portfolio_open_risk_before=portfolio_open_risk_before,
                    max_open_risk_amount=max_open_risk_amount,
                )
        else:
            structure = max(candle.high for candle in recent)
            stop_loss = structure * (Decimal("1") + buffer_rate)
            if stop_loss <= entry:
                return self._reject(
                    signal, now, RiskRejectReason.INVALID_STOP_LOSS,
                    equity, available, active_positions,
                    daily_drawdown_pct=daily_drawdown_pct,
                    portfolio_open_risk_before=portfolio_open_risk_before,
                    max_open_risk_amount=max_open_risk_amount,
                )
            risk_distance = stop_loss - entry
            take_profit = entry - (risk_distance * self.minimum_rr)
            if take_profit <= 0 or take_profit >= entry:
                return self._reject(
                    signal, now, RiskRejectReason.INVALID_TAKE_PROFIT,
                    equity, available, active_positions,
                    daily_drawdown_pct=daily_drawdown_pct,
                    portfolio_open_risk_before=portfolio_open_risk_before,
                    max_open_risk_amount=max_open_risk_amount,
                )

        rr = abs(take_profit - entry) / risk_distance
        if rr < self.minimum_rr:
            return self._reject(
                signal, now, RiskRejectReason.MINIMUM_RR_NOT_MET,
                equity, available, active_positions,
                daily_drawdown_pct=daily_drawdown_pct,
                portfolio_open_risk_before=portfolio_open_risk_before,
                max_open_risk_amount=max_open_risk_amount,
            )

        risk_amount = equity * (self.risk_per_trade_pct / Decimal("100"))
        quantity = (risk_amount / risk_distance).quantize(
            Decimal("0.00000001"), rounding=ROUND_DOWN
        )
        if quantity <= 0:
            return self._reject(
                signal, now, RiskRejectReason.INVALID_POSITION_SIZE,
                equity, available, active_positions,
                daily_drawdown_pct=daily_drawdown_pct,
                portfolio_open_risk_before=portfolio_open_risk_before,
                max_open_risk_amount=max_open_risk_amount,
            )

        proposed_notional = quantity * entry
        fee_slippage_allowance = self._exposure_allowance(proposed_notional)
        portfolio_open_risk_after = (
            portfolio_open_risk_before + risk_amount + fee_slippage_allowance
        )
        if portfolio_open_risk_after > max_open_risk_amount:
            return self._reject(
                signal, now, RiskRejectReason.MAX_OPEN_RISK_EXCEEDED,
                equity, available, active_positions,
                daily_drawdown_pct=daily_drawdown_pct,
                portfolio_open_risk_before=portfolio_open_risk_before,
                portfolio_open_risk_after=portfolio_open_risk_after,
                max_open_risk_amount=max_open_risk_amount,
                fee_slippage_allowance=fee_slippage_allowance,
            )

        estimated_margin = proposed_notional / self.leverage
        required_capacity = estimated_margin + fee_slippage_allowance
        if required_capacity > available:
            return self._reject(
                signal, now, RiskRejectReason.INSUFFICIENT_AVAILABLE_BALANCE,
                equity, available, active_positions,
                daily_drawdown_pct=daily_drawdown_pct,
                portfolio_open_risk_before=portfolio_open_risk_before,
                portfolio_open_risk_after=portfolio_open_risk_after,
                max_open_risk_amount=max_open_risk_amount,
                fee_slippage_allowance=fee_slippage_allowance,
            )

        return RiskDecision(
            status=RiskDecisionStatus.READY,
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            side=signal.side,
            evaluated_at=now,
            entry=entry,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=rr,
            leverage=self.leverage,
            account_equity=equity,
            available_balance=available,
            risk_amount=risk_amount,
            active_positions=active_positions,
            daily_drawdown_pct=daily_drawdown_pct,
            portfolio_open_risk_before=portfolio_open_risk_before,
            portfolio_open_risk_after=portfolio_open_risk_after,
            max_open_risk_amount=max_open_risk_amount,
            fee_slippage_allowance=fee_slippage_allowance,
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "risk_per_trade_pct": str(self.risk_per_trade_pct),
            "daily_loss_limit_pct": str(self.daily_loss_limit_pct),
            "minimum_rr": str(self.minimum_rr),
            "leverage": str(self.leverage),
            "max_leverage": str(self.max_leverage),
            "max_active_positions": self.max_active_positions,
            "max_open_risk_pct": str(self.max_open_risk_pct),
            "fee_buffer_pct": str(self.fee_buffer_pct),
            "slippage_buffer_pct": str(self.slippage_buffer_pct),
            "structure_lookback": self.structure_lookback,
            "structure_buffer_pct": str(self.structure_buffer_pct),
            "daily_baseline_date": self._baseline_day.isoformat() if self._baseline_day else None,
            "day_start_equity": str(self._day_start_equity) if self._day_start_equity is not None else None,
            "daily_loss_accounting": "persistent_utc_day_equity_baseline" if self._persistence is not None else "session_equity_drawdown",
        }

    def _portfolio_open_risk(
        self,
        positions: list[PositionResponse] | tuple[PositionResponse, ...],
    ) -> Decimal | None:
        total = Decimal("0")
        for position in positions:
            if position.size <= 0:
                continue
            entry = position.entry_price
            stop = position.stop_loss
            if entry is None or stop is None or entry <= 0 or stop <= 0:
                return None
            if position.side == "LONG" and stop >= entry:
                return None
            if position.side == "SHORT" and stop <= entry:
                return None

            stop_risk = abs(entry - stop) * position.size
            notional = (
                abs(position.position_value)
                if position.position_value is not None and position.position_value != 0
                else entry * position.size
            )
            total += stop_risk + self._exposure_allowance(notional)
        return total

    def _exposure_allowance(self, notional: Decimal) -> Decimal:
        combined_pct = self.fee_buffer_pct + self.slippage_buffer_pct
        return abs(notional) * (combined_pct / Decimal("100"))

    def _daily_drawdown(self, today: date, current_equity: Decimal) -> Decimal:
        if self._baseline_day != today or self._day_start_equity is None or self._day_start_equity <= 0:
            persisted = self._persistence.get_daily_baseline(today) if self._persistence is not None else None
            self._baseline_day = today
            self._day_start_equity = persisted if persisted is not None and persisted > 0 else current_equity
            if persisted is None and self._persistence is not None:
                self._persistence.set_daily_baseline(today, current_equity)
        assert self._day_start_equity is not None
        if current_equity >= self._day_start_equity:
            return Decimal("0")
        return ((self._day_start_equity - current_equity) / self._day_start_equity) * Decimal("100")

    @staticmethod
    def _reject(
        signal: StrategySignal,
        now: datetime,
        reason: RiskRejectReason,
        equity: Decimal | None,
        available: Decimal | None,
        active_positions: int,
        *,
        daily_drawdown_pct: Decimal | None = None,
        portfolio_open_risk_before: Decimal | None = None,
        portfolio_open_risk_after: Decimal | None = None,
        max_open_risk_amount: Decimal | None = None,
        fee_slippage_allowance: Decimal | None = None,
    ) -> RiskDecision:
        return RiskDecision(
            status=RiskDecisionStatus.REJECTED,
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            side=signal.side,
            evaluated_at=now,
            reason=reason,
            entry=signal.reference_entry_price,
            account_equity=equity,
            available_balance=available,
            active_positions=active_positions,
            daily_drawdown_pct=daily_drawdown_pct,
            portfolio_open_risk_before=portfolio_open_risk_before,
            portfolio_open_risk_after=portfolio_open_risk_after,
            max_open_risk_amount=max_open_risk_amount,
            fee_slippage_allowance=fee_slippage_allowance,
        )
