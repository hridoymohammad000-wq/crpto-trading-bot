from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.candle import SupportedSymbol


class MarketTickerResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: SupportedSymbol
    last_price: Decimal
    high_price_24h: Decimal | None
    low_price_24h: Decimal | None
    volume_24h: Decimal | None
    turnover_24h: Decimal | None
    prev_price_24h: Decimal | None
    price_change_24h_pct: Decimal | None
    bid_price: Decimal | None
    ask_price: Decimal | None
