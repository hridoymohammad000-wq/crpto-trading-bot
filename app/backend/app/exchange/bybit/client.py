from dataclasses import dataclass
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException, ROUND_DOWN, ROUND_UP
from urllib.parse import urlencode

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.exchange.base import ExchangeClient
from app.exchange.bybit.auth import (
    DEFAULT_RECV_WINDOW_MS,
    build_get_auth_headers,
    build_post_auth_headers,
)
from app.exchange.bybit.exceptions import BybitAPIError, BybitConnectionError
from app.models.candle import Candle

BYBIT_DEMO_REST_URL = "https://api-demo.bybit.com"
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
MIN_KLINE_LIMIT = 1
MAX_KLINE_LIMIT = 1000
CORE_SYMBOLS = frozenset({"BTCUSDT", "ETHUSDT", "SOLUSDT"})
TIMEFRAME_INTERVALS = {"1m": "1", "5m": "5", "15m": "15"}
TIMEFRAME_DURATIONS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
}


@dataclass(frozen=True)
class MarketTicker:
    symbol: str
    last_price: Decimal
    high_price_24h: Decimal | None
    low_price_24h: Decimal | None
    volume_24h: Decimal | None
    turnover_24h: Decimal | None
    prev_price_24h: Decimal | None
    price_change_24h_pct: Decimal | None
    bid_price: Decimal | None
    ask_price: Decimal | None


@dataclass(frozen=True)
class CoinBalance:
    coin: str
    equity: Decimal | None
    wallet_balance: Decimal | None
    total_order_im: Decimal | None
    total_position_im: Decimal | None

@dataclass(frozen=True)
class AccountBalance:
    total_equity: Decimal | None
    total_wallet_balance: Decimal | None
    total_margin_balance: Decimal | None
    total_available_balance: Decimal | None
    total_initial_margin: Decimal | None
    total_maintenance_margin: Decimal | None
    total_perp_upl: Decimal | None
    coins: tuple[CoinBalance, ...]


@dataclass(frozen=True)
class AccountInfo:
    unified_margin_status: int | None
    margin_mode: str | None


@dataclass(frozen=True)
class InstrumentInfo:
    symbol: str
    qty_step: Decimal
    min_order_qty: Decimal
    max_order_qty: Decimal | None
    tick_size: Decimal
    min_notional_value: Decimal | None
    max_leverage: Decimal | None


@dataclass(frozen=True)
class NormalizedOrderValues:
    quantity: Decimal
    stop_loss: Decimal
    take_profit: Decimal


@dataclass(frozen=True)
class OrderAcknowledgement:
    order_id: str
    order_link_id: str | None



@dataclass(frozen=True)
class ClosedTrade:
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal | None
    exit_price: Decimal | None
    realized_pnl: Decimal
    open_fee: Decimal | None
    close_fee: Decimal | None
    order_id: str | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class Position:
    symbol: str
    side: str
    size: Decimal
    entry_price: Decimal | None
    mark_price: Decimal | None
    position_value: Decimal | None
    leverage: Decimal | None
    unrealized_pnl: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    liquidation_price: Decimal | None


class BybitDemoClient(ExchangeClient):
    def __init__(
        self,
        settings: Settings,
        *,
        timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
        recv_window_ms: int = DEFAULT_RECV_WINDOW_MS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not settings.BYBIT_DEMO:
            raise ValueError("BybitDemoClient requires BYBIT_DEMO=true")

        self.api_key = settings.BYBIT_API_KEY
        self.api_secret = settings.BYBIT_API_SECRET
        self.base_url = BYBIT_DEMO_REST_URL
        self.timeout = timeout
        self.recv_window_ms = recv_window_ms
        self._transport = transport
        self._http_client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self._transport,
            )

    async def disconnect(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def get_server_time(self) -> int:
        payload = await self._get("/v5/market/time")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise BybitAPIError("Bybit server-time response is malformed")

        time_second = result.get("timeSecond")
        try:
            return int(time_second)
        except (TypeError, ValueError) as exc:
            raise BybitAPIError("Bybit server-time response is malformed") from exc

    async def get_account_balance(self) -> AccountBalance:
        payload = await self._get(
            "/v5/account/wallet-balance",
            params={"accountType": "UNIFIED"},
            authenticated=True,
        )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise BybitAPIError("Bybit wallet-balance response is malformed")

        accounts = result.get("list")
        if not isinstance(accounts, list) or not accounts:
            raise BybitAPIError("Bybit wallet-balance response is malformed")

        account = accounts[0]
        if not isinstance(account, dict):
            raise BybitAPIError("Bybit wallet-balance response is malformed")

        raw_coins = account.get("coin", [])
        if not isinstance(raw_coins, list):
            raise BybitAPIError("Bybit wallet-balance response is malformed")

        coins = tuple(self._parse_coin_balance(coin) for coin in raw_coins)

        return AccountBalance(
            total_equity=self._parse_decimal(account.get("totalEquity")),
            total_wallet_balance=self._parse_decimal(account.get("totalWalletBalance")),
            total_margin_balance=self._parse_decimal(account.get("totalMarginBalance")),
            total_available_balance=self._parse_decimal(account.get("totalAvailableBalance")),
            total_initial_margin=self._parse_decimal(account.get("totalInitialMargin")),
            total_maintenance_margin=self._parse_decimal(account.get("totalMaintenanceMargin")),
            total_perp_upl=self._parse_decimal(account.get("totalPerpUPL")),
            coins=coins,
        )

    async def get_account_info(self) -> AccountInfo:
        payload = await self._get(
            "/v5/account/info",
            authenticated=True,
        )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise BybitAPIError("Bybit account-info response is malformed")

        raw_status = result.get("unifiedMarginStatus")
        try:
            unified_margin_status = int(raw_status) if raw_status is not None else None
        except (TypeError, ValueError):
            unified_margin_status = None

        raw_margin_mode = result.get("marginMode")
        margin_mode = str(raw_margin_mode) if raw_margin_mode is not None else None

        return AccountInfo(
            unified_margin_status=unified_margin_status,
            margin_mode=margin_mode,
        )

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> tuple[Candle, ...]:
        if not symbol.endswith("USDT"):
            raise ValueError(f"Unsupported symbol: {symbol}")
        if timeframe not in TIMEFRAME_INTERVALS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not MIN_KLINE_LIMIT <= limit <= MAX_KLINE_LIMIT
        ):
            raise ValueError(
                f"limit must be between {MIN_KLINE_LIMIT} and {MAX_KLINE_LIMIT}"
            )

        payload = await self._get(
            "/v5/market/kline",
            params={
                "category": "linear",
                "symbol": symbol,
                "interval": TIMEFRAME_INTERVALS[timeframe],
                "limit": str(limit),
            },
        )
        reference_time = self._parse_response_time(payload.get("time"))
        result = payload.get("result")
        if not isinstance(result, dict):
            raise BybitAPIError("Bybit Kline response is malformed")
        if result.get("category") != "linear" or result.get("symbol") != symbol:
            raise BybitAPIError("Bybit Kline response is malformed")

        raw_candles = result.get("list")
        if not isinstance(raw_candles, list):
            raise BybitAPIError("Bybit Kline response is malformed")

        candles = [
            self._parse_candle(
                value,
                symbol=symbol,
                timeframe=timeframe,
                reference_time=reference_time,
            )
            for value in raw_candles
        ]
        return tuple(sorted(candles, key=lambda candle: candle.start_time))

    async def get_ticker(self, symbol: str) -> MarketTicker:
        if not symbol.endswith("USDT"):
            raise ValueError(f"Unsupported symbol: {symbol}")

        payload = await self._get(
            "/v5/market/tickers",
            params={"category": "linear", "symbol": symbol},
        )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise BybitAPIError("Bybit ticker response is malformed")

        raw_tickers = result.get("list")
        if not isinstance(raw_tickers, list) or len(raw_tickers) != 1:
            raise BybitAPIError("Bybit ticker response is malformed")
        value = raw_tickers[0]
        if not isinstance(value, dict) or value.get("symbol") != symbol:
            raise BybitAPIError("Bybit ticker response is malformed")

        last_price = self._parse_required_decimal(value.get("lastPrice"), "ticker last price")
        return MarketTicker(
            symbol=symbol,
            last_price=last_price,
            high_price_24h=self._parse_decimal(value.get("highPrice24h")),
            low_price_24h=self._parse_decimal(value.get("lowPrice24h")),
            volume_24h=self._parse_decimal(value.get("volume24h")),
            turnover_24h=self._parse_decimal(value.get("turnover24h")),
            prev_price_24h=self._parse_decimal(value.get("prevPrice24h")),
            price_change_24h_pct=self._parse_decimal(value.get("price24hPcnt")),
            bid_price=self._parse_decimal(value.get("bid1Price")),
            ask_price=self._parse_decimal(value.get("ask1Price")),
        )

    async def get_all_tickers(self) -> tuple[MarketTicker, ...]:
        payload = await self._get("/v5/market/tickers", params={"category": "linear"})
        result = payload.get("result")
        rows = result.get("list") if isinstance(result, dict) else None
        if not isinstance(rows, list):
            raise BybitAPIError("Bybit tickers response is malformed")
        parsed: list[MarketTicker] = []
        for value in rows:
            if not isinstance(value, dict):
                continue
            symbol = str(value.get("symbol") or "")
            if not symbol.endswith("USDT"):
                continue
            last = self._parse_decimal(value.get("lastPrice"))
            if last is None or last <= 0:
                continue
            parsed.append(MarketTicker(
                symbol=symbol, last_price=last,
                high_price_24h=self._parse_decimal(value.get("highPrice24h")),
                low_price_24h=self._parse_decimal(value.get("lowPrice24h")),
                volume_24h=self._parse_decimal(value.get("volume24h")),
                turnover_24h=self._parse_decimal(value.get("turnover24h")),
                prev_price_24h=self._parse_decimal(value.get("prevPrice24h")),
                price_change_24h_pct=self._parse_decimal(value.get("price24hPcnt")),
                bid_price=self._parse_decimal(value.get("bid1Price")),
                ask_price=self._parse_decimal(value.get("ask1Price")),
            ))
        return tuple(parsed)

    async def get_all_instruments(self) -> tuple[InstrumentInfo, ...]:
        cursor: str | None = None
        items: list[InstrumentInfo] = []
        while True:
            params = {"category": "linear", "limit": "1000"}
            if cursor:
                params["cursor"] = cursor
            payload = await self._get("/v5/market/instruments-info", params=params)
            result = payload.get("result")
            rows = result.get("list") if isinstance(result, dict) else None
            if not isinstance(rows, list):
                raise BybitAPIError("Bybit instruments-info response is malformed")
            for row in rows:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("symbol") or "")
                if not symbol.endswith("USDT") or row.get("status") not in (None, "Trading"):
                    continue
                lot = row.get("lotSizeFilter")
                price = row.get("priceFilter")
                leverage = row.get("leverageFilter")
                if not isinstance(lot, dict) or not isinstance(price, dict):
                    continue
                try:
                    items.append(InstrumentInfo(
                        symbol=symbol,
                        qty_step=self._parse_required_decimal(lot.get("qtyStep"), "quantity step"),
                        min_order_qty=self._parse_required_decimal(lot.get("minOrderQty"), "minimum order quantity"),
                        max_order_qty=self._parse_decimal(lot.get("maxMktOrderQty") or lot.get("maxOrderQty")),
                        tick_size=self._parse_required_decimal(price.get("tickSize"), "tick size"),
                        min_notional_value=self._parse_decimal(lot.get("minNotionalValue")),
                        max_leverage=(self._parse_decimal(leverage.get("maxLeverage")) if isinstance(leverage, dict) else None),
                    ))
                except (BybitAPIError, ValueError):
                    continue
            cursor = str(result.get("nextPageCursor") or "") if isinstance(result, dict) else ""
            if not cursor:
                break
        return tuple(items)

    async def get_closed_trades(self, limit: int = 100) -> tuple[ClosedTrade, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        payload = await self._get(
            "/v5/position/closed-pnl",
            params={
                "category": "linear",
                "settleCoin": "USDT",
                "limit": str(limit),
            },
            authenticated=True,
        )
        result = payload.get("result")
        rows = result.get("list") if isinstance(result, dict) else None
        if not isinstance(rows, list):
            raise BybitAPIError("Bybit closed-PnL response is malformed")
        return tuple(self._parse_closed_trade(row) for row in rows)

    async def get_positions(self) -> tuple[Position, ...]:
        payload = await self._get(
            "/v5/position/list",
            params={"category": "linear", "settleCoin": "USDT"},
            authenticated=True,
        )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise BybitAPIError("Bybit positions response is malformed")

        raw_positions = result.get("list")
        if not isinstance(raw_positions, list):
            raise BybitAPIError("Bybit positions response is malformed")

        positions: list[Position] = []
        for raw_position in raw_positions:
            position = self._parse_position(raw_position)
            if position.size > 0:
                positions.append(position)

        return tuple(positions)

    async def get_instrument_info(self, symbol: str) -> InstrumentInfo:
        if not symbol.endswith("USDT"):
            raise ValueError(f"Unsupported symbol: {symbol}")
        payload = await self._get(
            "/v5/market/instruments-info",
            params={"category": "linear", "symbol": symbol},
        )
        result = payload.get("result")
        rows = result.get("list") if isinstance(result, dict) else None
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise BybitAPIError("Bybit instruments-info response is malformed")
        row = rows[0]
        if row.get("symbol") != symbol:
            raise BybitAPIError("Bybit instruments-info response is malformed")
        lot = row.get("lotSizeFilter")
        price = row.get("priceFilter")
        leverage = row.get("leverageFilter")
        if not isinstance(lot, dict) or not isinstance(price, dict):
            raise BybitAPIError("Bybit instruments-info response is malformed")
        return InstrumentInfo(
            symbol=symbol,
            qty_step=self._parse_required_decimal(lot.get("qtyStep"), "quantity step"),
            min_order_qty=self._parse_required_decimal(lot.get("minOrderQty"), "minimum order quantity"),
            max_order_qty=self._parse_decimal(lot.get("maxMktOrderQty") or lot.get("maxOrderQty")),
            tick_size=self._parse_required_decimal(price.get("tickSize"), "tick size"),
            min_notional_value=self._parse_decimal(lot.get("minNotionalValue")),
            max_leverage=(self._parse_decimal(leverage.get("maxLeverage")) if isinstance(leverage, dict) else None),
        )

    async def normalize_order_values(
        self,
        *,
        symbol: str,
        side: str,
        quantity: Decimal,
        reference_entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
    ) -> NormalizedOrderValues:
        if side not in {"Buy", "Sell"}:
            raise ValueError("side must be Buy or Sell")
        info = await self.get_instrument_info(symbol)
        normalized_qty = self._floor_to_step(quantity, info.qty_step)
        if normalized_qty < info.min_order_qty:
            raise ValueError("Calculated quantity is below Bybit minimum order quantity")
        if info.max_order_qty is not None and normalized_qty > info.max_order_qty:
            raise ValueError("Calculated quantity exceeds Bybit maximum market order quantity")
        if (
            info.min_notional_value is not None
            and normalized_qty * reference_entry_price < info.min_notional_value
        ):
            raise ValueError("Calculated order value is below Bybit minimum notional")
        if side == "Buy":
            normalized_sl = self._floor_to_step(stop_loss, info.tick_size)
            normalized_tp = self._ceil_to_step(take_profit, info.tick_size)
        else:
            normalized_sl = self._ceil_to_step(stop_loss, info.tick_size)
            normalized_tp = self._floor_to_step(take_profit, info.tick_size)
        if normalized_sl <= 0 or normalized_tp <= 0:
            raise ValueError("Normalized SL/TP must be positive")
        return NormalizedOrderValues(
            quantity=normalized_qty,
            stop_loss=normalized_sl,
            take_profit=normalized_tp,
        )

    async def set_leverage(self, symbol: str, leverage: Decimal) -> None:
        if not symbol.endswith("USDT"):
            raise ValueError(f"Unsupported symbol: {symbol}")
        if leverage <= 0 or leverage > Decimal("10"):
            raise ValueError("leverage must be > 0 and <= 10")
        info = await self.get_instrument_info(symbol)
        if info.max_leverage is not None and leverage > info.max_leverage:
            raise ValueError("Requested leverage exceeds instrument maximum")
        value = self._format_decimal(leverage)
        try:
            await self._post(
                "/v5/position/set-leverage",
                body={
                    "category": "linear",
                    "symbol": symbol,
                    "buyLeverage": value,
                    "sellLeverage": value,
                },
            )
        except BybitAPIError as exc:
            # Bybit may report that leverage is already set; the client keeps
            # all other API failures fail-closed.
            if "110043" not in str(exc):
                raise

    async def place_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: Decimal,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
        order_link_id: str | None = None,
        reduce_only: bool = False,
    ) -> OrderAcknowledgement:
        if not symbol.endswith("USDT"):
            raise ValueError(f"Unsupported symbol: {symbol}")
        if side not in {"Buy", "Sell"}:
            raise ValueError("side must be Buy or Sell")
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        body: dict[str, object] = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": self._format_decimal(quantity),
            "positionIdx": 0,
            "reduceOnly": reduce_only,
        }
        if order_link_id:
            body["orderLinkId"] = order_link_id
        if not reduce_only:
            if stop_loss is None or take_profit is None:
                raise ValueError("opening orders require stop_loss and take_profit")
            body.update(
                {
                    "stopLoss": self._format_decimal(stop_loss),
                    "takeProfit": self._format_decimal(take_profit),
                    "tpslMode": "Full",
                    "tpOrderType": "Market",
                    "slOrderType": "Market",
                }
            )

        payload = await self._post("/v5/order/create", body=body)
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("orderId"), str):
            raise BybitAPIError("Bybit order-create response is malformed")
        return OrderAcknowledgement(
            order_id=result["orderId"],
            order_link_id=(result.get("orderLinkId") if isinstance(result.get("orderLinkId"), str) else order_link_id),
        )

    async def get_order(self, *, symbol: str, order_id: str) -> dict[str, object]:
        payload = await self._get(
            "/v5/order/realtime",
            params={"category": "linear", "symbol": symbol, "orderId": order_id},
            authenticated=True,
        )
        result = payload.get("result")
        rows = result.get("list") if isinstance(result, dict) else None
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise BybitAPIError("Bybit order-status response is malformed")
        return rows[0]

    async def get_order_by_link_id(
        self,
        *,
        symbol: str,
        order_link_id: str,
    ) -> dict[str, object] | None:
        """Find an order by deterministic orderLinkId without submitting.

        Realtime state is checked first; order history is then checked so an
        already-filled/cancelled order can still resolve an ambiguous submit.
        """
        for path in ("/v5/order/realtime", "/v5/order/history"):
            payload = await self._get(
                path,
                params={
                    "category": "linear",
                    "symbol": symbol,
                    "orderLinkId": order_link_id,
                },
                authenticated=True,
            )
            result = payload.get("result")
            rows = result.get("list") if isinstance(result, dict) else None
            if not isinstance(rows, list):
                raise BybitAPIError("Bybit order lookup response is malformed")
            for row in rows:
                if isinstance(row, dict) and row.get("orderLinkId") == order_link_id:
                    return row
        return None

    async def get_open_orders(self) -> tuple[dict[str, object], ...]:
        payload = await self._get(
            "/v5/order/realtime",
            params={"category": "linear", "settleCoin": "USDT"},
            authenticated=True,
        )
        result = payload.get("result")
        rows = result.get("list") if isinstance(result, dict) else None
        if not isinstance(rows, list):
            raise BybitAPIError("Bybit open-orders response is malformed")
        return tuple(row for row in rows if isinstance(row, dict))

    async def cancel_order(self, *, symbol: str, order_id: str) -> OrderAcknowledgement:
        payload = await self._post(
            "/v5/order/cancel",
            body={"category": "linear", "symbol": symbol, "orderId": order_id},
        )
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("orderId"), str):
            raise BybitAPIError("Bybit order-cancel response is malformed")
        return OrderAcknowledgement(
            order_id=result["orderId"],
            order_link_id=result.get("orderLinkId") if isinstance(result.get("orderLinkId"), str) else None,
        )

    async def close_position(self, symbol: str) -> OrderAcknowledgement:
        positions = await self.get_positions()
        position = next((item for item in positions if item.symbol == symbol), None)
        if position is None:
            raise ValueError(f"No open position for {symbol}")
        return await self.place_order(
            symbol=symbol,
            side="Sell" if position.side == "LONG" else "Buy",
            quantity=position.size,
            reduce_only=True,
            order_link_id=f"close-{symbol.lower()}",
        )

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        authenticated: bool = False,
    ) -> dict[str, object]:
        query_string = urlencode(params or {})
        headers: dict[str, str] = {}
        if authenticated:
            headers = build_get_auth_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                query_string=query_string,
                recv_window_ms=self.recv_window_ms,
            )

        await self.connect()
        if self._http_client is None:
            raise BybitConnectionError("Bybit Demo HTTP client is unavailable")

        try:
            response = await self._http_client.get(
                path,
                params=params,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise BybitConnectionError("Bybit Demo request timed out") from exc
        except httpx.RequestError as exc:
            raise BybitConnectionError("Bybit Demo request failed") from exc

        if not response.is_success:
            raise BybitAPIError(
                f"Bybit Demo returned HTTP status {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise BybitAPIError("Bybit response is not valid JSON") from exc

        if not isinstance(payload, dict) or "retCode" not in payload:
            raise BybitAPIError("Bybit response is malformed")
        if payload["retCode"] != 0:
            raise BybitAPIError(
                f"Bybit API returned error code {payload['retCode']}"
            )

        return payload


    async def _post(
        self,
        path: str,
        *,
        body: dict[str, object],
    ) -> dict[str, object]:
        json_body = json.dumps(body, separators=(",", ":"), sort_keys=True)
        headers = build_post_auth_headers(
            api_key=self.api_key,
            api_secret=self.api_secret,
            json_body=json_body,
            recv_window_ms=self.recv_window_ms,
        )
        await self.connect()
        if self._http_client is None:
            raise BybitConnectionError("Bybit Demo HTTP client is unavailable")
        try:
            response = await self._http_client.post(
                path,
                content=json_body,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise BybitConnectionError("Bybit Demo request timed out") from exc
        except httpx.RequestError as exc:
            raise BybitConnectionError("Bybit Demo request failed") from exc
        if not response.is_success:
            raise BybitAPIError(
                f"Bybit Demo returned HTTP status {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise BybitAPIError("Bybit response is not valid JSON") from exc
        if not isinstance(payload, dict) or "retCode" not in payload:
            raise BybitAPIError("Bybit response is malformed")
        if payload["retCode"] != 0:
            raise BybitAPIError(
                f"Bybit API returned error code {payload['retCode']}"
            )
        return payload

    @staticmethod
    def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
        if value <= 0 or step <= 0:
            raise ValueError("value and step must be positive")
        units = (value / step).to_integral_value(rounding=ROUND_DOWN)
        return units * step

    @staticmethod
    def _ceil_to_step(value: Decimal, step: Decimal) -> Decimal:
        if value <= 0 or step <= 0:
            raise ValueError("value and step must be positive")
        units = (value / step).to_integral_value(rounding=ROUND_UP)
        return units * step

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        return format(value, "f").rstrip("0").rstrip(".") if "." in format(value, "f") else format(value, "f")


    @classmethod
    def _parse_closed_trade(cls, value: object) -> ClosedTrade:
        if not isinstance(value, dict):
            raise BybitAPIError("Bybit closed-PnL response is malformed")
        symbol = value.get("symbol")
        side = value.get("side")
        if not isinstance(symbol, str) or side not in {"Buy", "Sell"}:
            raise BybitAPIError("Bybit closed-PnL response is malformed")
        qty = cls._parse_required_decimal(value.get("qty"), "closed trade quantity")
        pnl = cls._parse_required_decimal(value.get("closedPnl"), "closed trade PnL")
        return ClosedTrade(
            symbol=symbol,
            side="SHORT" if side == "Buy" else "LONG",
            quantity=qty,
            entry_price=cls._parse_decimal(value.get("avgEntryPrice")),
            exit_price=cls._parse_decimal(value.get("avgExitPrice")),
            realized_pnl=pnl,
            open_fee=cls._parse_decimal(value.get("openFee")),
            close_fee=cls._parse_decimal(value.get("closeFee")),
            order_id=value.get("orderId") if isinstance(value.get("orderId"), str) else None,
            created_at=cls._parse_timestamp_ms(value.get("createdTime")),
            updated_at=cls._parse_timestamp_ms(value.get("updatedTime")),
        )

    @staticmethod
    def _parse_timestamp_ms(value: object) -> datetime | None:
        if value in (None, ""):
            return None
        try:
            return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    @classmethod
    def _parse_position(cls, value: object) -> Position:
        if not isinstance(value, dict):
            raise BybitAPIError("Bybit positions response is malformed")

        symbol = value.get("symbol")
        raw_side = value.get("side")
        if not isinstance(symbol, str) or raw_side not in {"Buy", "Sell"}:
            raise BybitAPIError("Bybit positions response is malformed")

        size = cls._parse_required_decimal(value.get("size"), "position size")
        return Position(
            symbol=symbol,
            side="LONG" if raw_side == "Buy" else "SHORT",
            size=size,
            entry_price=cls._parse_decimal(value.get("avgPrice")),
            mark_price=cls._parse_decimal(value.get("markPrice")),
            position_value=cls._parse_decimal(value.get("positionValue")),
            leverage=cls._parse_decimal(value.get("leverage")),
            unrealized_pnl=cls._parse_decimal(value.get("unrealisedPnl")),
            stop_loss=cls._parse_decimal(value.get("stopLoss")),
            take_profit=cls._parse_decimal(value.get("takeProfit")),
            liquidation_price=cls._parse_decimal(value.get("liqPrice")),
        )

    @classmethod
    def _parse_required_decimal(cls, value: object, field_name: str) -> Decimal:
        parsed = cls._parse_decimal(value)
        if parsed is None:
            raise BybitAPIError(f"Bybit {field_name} is missing")
        return parsed

    @classmethod
    def _parse_coin_balance(cls, value: object) -> CoinBalance:
        if not isinstance(value, dict) or not isinstance(value.get("coin"), str):
            raise BybitAPIError("Bybit coin-balance response is malformed")

        return CoinBalance(
            coin=value["coin"],
            equity=cls._parse_decimal(value.get("equity")),
            wallet_balance=cls._parse_decimal(value.get("walletBalance")),
            total_order_im=cls._parse_decimal(value.get("totalOrderIM")),
            total_position_im=cls._parse_decimal(value.get("totalPositionIM")),
        )

    @staticmethod
    def _parse_decimal(value: object) -> Decimal | None:
        if value is None or value == "":
            return None

        try:
            return Decimal(str(value))
        except (DecimalException, ValueError) as exc:
            raise BybitAPIError("Bybit balance contains an invalid number") from exc

    @staticmethod
    def _parse_response_time(value: object) -> datetime:
        try:
            milliseconds = int(value)
            return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
                milliseconds=milliseconds
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise BybitAPIError("Bybit Kline response is malformed") from exc

    @classmethod
    def _parse_candle(
        cls,
        value: object,
        *,
        symbol: str,
        timeframe: str,
        reference_time: datetime,
    ) -> Candle:
        if not isinstance(value, list) or len(value) < 7:
            raise BybitAPIError("Bybit Kline response is malformed")

        try:
            start_time = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
                milliseconds=int(value[0])
            )
            duration = TIMEFRAME_DURATIONS[timeframe]
            return Candle(
                symbol=symbol,
                timeframe=timeframe,
                start_time=start_time,
                open=Decimal(str(value[1])),
                high=Decimal(str(value[2])),
                low=Decimal(str(value[3])),
                close=Decimal(str(value[4])),
                volume=Decimal(str(value[5])),
                turnover=Decimal(str(value[6])),
                is_closed=start_time + duration <= reference_time,
            )
        except (
            DecimalException,
            TypeError,
            ValueError,
            OverflowError,
            ValidationError,
        ) as exc:
            raise BybitAPIError("Bybit Kline response is malformed") from exc
