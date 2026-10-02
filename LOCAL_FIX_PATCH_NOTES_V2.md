# Local Fix Patch V2

This package builds on the previous local-fixes ZIP and keeps GitHub untouched.

Additional fixes in V2:

- Dashboard chart scanner-symbol hook retries after 5 seconds when the initial scanner request fails, then returns to the normal 60-second refresh cadence after success.
- The last known qualified chart symbols are retained across temporary scanner/API failures.
- Bybit V5 non-zero `retCode` responses retain the numeric code and safe `retMsg` text for diagnosis.
- Common Bybit authentication retCodes are translated to `BybitAuthenticationError`.
- `/account` preserves the existing friendly missing-credentials message, but exposes safe Bybit error details for invalid credentials/API responses instead of the generic `invalid response` message.

No `.env`, API keys, local databases, caches, or `node_modules` are included.
