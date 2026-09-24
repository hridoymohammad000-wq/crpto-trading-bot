import hashlib
import hmac
import time

from app.exchange.bybit.exceptions import BybitAuthenticationError

DEFAULT_RECV_WINDOW_MS = 5000


def _base_auth_headers(
    *,
    api_key: str,
    api_secret: str,
    payload: str,
    recv_window_ms: int,
    timestamp_ms: int | None,
) -> dict[str, str]:
    if not api_key or not api_secret:
        raise BybitAuthenticationError(
            "Bybit Demo API credentials are required for private requests"
        )

    timestamp = str(
        timestamp_ms if timestamp_ms is not None else time.time_ns() // 1_000_000
    )
    recv_window = str(recv_window_ms)
    sign_payload = f"{timestamp}{api_key}{recv_window}{payload}"
    signature = hmac.new(
        api_secret.encode(),
        sign_payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-SIGN": signature,
        "X-BAPI-RECV-WINDOW": recv_window,
    }


def build_get_auth_headers(
    *,
    api_key: str,
    api_secret: str,
    query_string: str,
    recv_window_ms: int = DEFAULT_RECV_WINDOW_MS,
    timestamp_ms: int | None = None,
) -> dict[str, str]:
    return _base_auth_headers(
        api_key=api_key,
        api_secret=api_secret,
        payload=query_string,
        recv_window_ms=recv_window_ms,
        timestamp_ms=timestamp_ms,
    )


def build_post_auth_headers(
    *,
    api_key: str,
    api_secret: str,
    json_body: str,
    recv_window_ms: int = DEFAULT_RECV_WINDOW_MS,
    timestamp_ms: int | None = None,
) -> dict[str, str]:
    headers = _base_auth_headers(
        api_key=api_key,
        api_secret=api_secret,
        payload=json_body,
        recv_window_ms=recv_window_ms,
        timestamp_ms=timestamp_ms,
    )
    headers["Content-Type"] = "application/json"
    return headers
