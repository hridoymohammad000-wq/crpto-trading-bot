from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/scanner", tags=["scanner"])

class WatchlistResponse(BaseModel):
    core_symbols: list[str]
    dynamic_symbols: list[str]
    open_position_symbols: list[str]
    cooldown_symbols: dict[str, str]

@router.get("/status")
def get_status(request: Request):
    engine = request.app.state.scanner_engine
    
    eligible_count = sum(1 for o in engine.universe if o.reason_codes == () or not o.reason_codes)
    watching_count = sum(1 for o in engine.universe if o.state.value == "WATCHING")
    armed_count = sum(1 for o in engine.universe if o.state.value == "ARMED")
    
    return {
        "last_refresh": engine._last_universe_refresh.isoformat() if engine._last_universe_refresh else None,
        "universe_count": len(engine.universe),
        "eligible_count": eligible_count,
        "watching_count": watching_count,
        "armed_count": armed_count,
        "open_positions": len(engine.watchlist.open_position_symbols)
    }

@router.get("/universe")
def get_universe(request: Request):
    engine = request.app.state.scanner_engine
    return [
        {
            "symbol": o.symbol,
            "price": float(o.price),
            "spread_pct": float(o.spread_pct),
            "turnover_24h": float(o.turnover_24h),
            "volume_24h": float(o.volume_24h),
            "atr_pct": float(o.atr_pct) if o.atr_pct is not None else None,
            "rvol": float(o.rvol) if o.rvol is not None else None,
            "adx": float(o.adx) if o.adx is not None else None,
            "regime": o.regime.value,
            "bias": o.bias,
            "market_quality_score": o.market_quality_score,
            "setup_quality_score": o.setup_quality_score,
            "state": o.state.value,
            "reason_codes": list(o.reason_codes)
        }
        for o in engine.universe
    ]

@router.get("/watchlist")
def get_watchlist(request: Request):
    engine = request.app.state.scanner_engine
    return {
        "core_symbols": list(engine.watchlist.core_symbols),
        "dynamic_symbols": list(engine.watchlist.dynamic_symbols),
        "open_position_symbols": list(engine.watchlist.open_position_symbols),
        "cooldown_symbols": {k: v.isoformat() for k, v in engine.watchlist.cooldown_symbols.items()},
        "symbol_states": {
            k: {
                "symbol": v.symbol,
                "state": v.state.value,
                "execution_allowed": v.execution_allowed,
                "context_15m": v.context_15m,
                "setup_5m": v.setup_5m,
                "trigger_1m": {
                    "trigger_status": v.trigger_1m.get("trigger_status"),
                    "latest_closed_candle": v.trigger_1m.get("latest_closed_candle"),
                    "trigger_reason": v.trigger_1m.get("trigger_reason")
                } if v.trigger_1m else {},
                "reason_codes": v.reason_codes
            } for k, v in engine.watchlist.symbol_states.items()
        }
    }

@router.get("/candidates")
def get_candidates(request: Request):
    engine = request.app.state.scanner_engine
    watchlist = engine.watchlist
    
    candidates = []
    
    # Filter for eligible or monitored
    for o in engine.universe:
        sState = watchlist.symbol_states.get(o.symbol)
        current_state = sState.state.value if sState else o.state.value
        
        # Reason check: exclude items with rejections unless they are in active state or open position
        has_rejection = bool(sState.reason_codes if sState else o.reason_codes)
        
        is_monitored = (
            o.symbol in watchlist.core_symbols or 
            o.symbol in watchlist.dynamic_symbols or
            o.symbol in watchlist.open_position_symbols
        )
        
        active_states = {"WATCHING", "ARMED", "TRIGGERED", "EXECUTED", "COOLDOWN"}
        is_active = current_state in active_states
        
        if not is_monitored and not is_active:
            continue
            
        if has_rejection and not is_active and o.symbol not in watchlist.open_position_symbols:
            continue
            
        candidates.append({
            "symbol": o.symbol,
            "price": float(o.price),
            "spread_pct": float(o.spread_pct),
            "turnover_24h": float(o.turnover_24h),
            "volume_24h": float(o.volume_24h),
            "atr_pct": float(o.atr_pct) if o.atr_pct is not None else None,
            "rvol": float(o.rvol) if o.rvol is not None else None,
            "adx": float(o.adx) if o.adx is not None else None,
            "regime": o.regime.value,
            "bias": o.bias,
            "market_quality_score": o.market_quality_score,
            "setup_quality_score": o.setup_quality_score,
            "state": current_state,
            "reason_codes": list(sState.reason_codes if sState else o.reason_codes)
        })

    # Sort logic
    state_order = {
        "TRIGGERED": 1,
        "ARMED": 2,
        "WATCHING": 3,
        "EXECUTED": 4,
        "COOLDOWN": 5
    }
    
    candidates.sort(key=lambda x: (
        state_order.get(x["state"], 99),
        -(x["setup_quality_score"] or 0),
        -(x["market_quality_score"] or 0)
    ))
    
    return candidates

@router.get("/symbol/{symbol}")
def get_symbol_state(request: Request, symbol: str):
    engine = request.app.state.scanner_engine
    
    opportunity = next((o for o in engine.universe if o.symbol == symbol), None)
    state = engine.watchlist.symbol_states.get(symbol)
    
    if not state and not opportunity:
        return {"error": "Symbol not found"}
        
    return {
        "symbol": symbol,
        "state": state.state.value if state else opportunity.state.value if opportunity else "DISCOVERED",
        "regime": opportunity.regime.value if opportunity else "UNKNOWN",
        "bias": opportunity.bias if opportunity else None,
        "15m": state.context_15m if state else {},
        "5m": state.setup_5m if state else {},
        "1m": {
            "trigger_status": state.trigger_1m.get("trigger_status"),
            "latest_closed_candle": state.trigger_1m.get("latest_closed_candle"),
            "trigger_reason": state.trigger_1m.get("trigger_reason")
        } if state and state.trigger_1m else {},
        "scores": {
            "market_quality_score": opportunity.market_quality_score if opportunity else 0,
            "setup_quality_score": opportunity.setup_quality_score if opportunity else 0,
        },
        "execution": {
            "allowed": state.execution_allowed if state else False,
            "risk_status": None,
            "execution_status": state.execution_diagnostics.get("execution_status") if state else None
        },
        "reason_codes": state.reason_codes if state else list(opportunity.reason_codes) if opportunity else []
    }

