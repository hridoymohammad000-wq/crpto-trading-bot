# Final Project Audit — UI Consolidation + Optional AI Analyst

## Scope completed

- Sidebar reduced and reordered to:
  1. Dashboard
  2. Scanner
  3. Signals
  4. Active Trade & History
  5. Performance & Strategy
  6. Settings
- Dashboard duplicate Positions and Trade History sections removed.
- Balance / Equity / Available retained as core account-capacity metrics.
- Connection badges removed from the Dashboard/Header and consolidated in Settings.
- Settings now shows Backend, WebSocket, Bybit Demo, Telegram, and AI Analyst integration status.
- Positions + Trades merged into Active Trade & History:
  - active positions use card view
  - closed trades use table view
  - Today is the default history period
  - Last 7 Days and Custom range are available
  - open positions are always visible regardless of history filter so a live position cannot be hidden by a date filter
- Performance + Strategy Monitor merged into Performance & Strategy.
- Scanner Watching summary now derives from the live watchlist symbol states when available, avoiding the prior summary/table mismatch.
- Login/auth gate removed from active application flow.
- Cookie/auth URL redirect workaround removed.

## AI architecture

An optional read-only AI analyst is included.

Safety boundaries:
- no reference to ExecutionService
- no exchange order placement
- no risk approval
- no readiness bypass
- no SL/TP modification
- no automatic background trading action
- explicit `analysis_only` mode
- disabled by default

Backend endpoints:
- `GET /ai/status`
- `POST /ai/analyze`
- `GET /integrations/status`

Environment variables:
- `AI_ENABLED=false`
- `AI_PROVIDER=groq`
- `GROQ_API_KEY=`
- `AI_MODEL=qwen/qwen3.8-27b`
- `AI_BASE_URL=https://api.groq.com/openai/v1`
- `AI_TIMEOUT_SECONDS=30`
- `AI_MAX_OUTPUT_TOKENS=800`

Telegram status configuration:
- `TELEGRAM_BOT_TOKEN=`
- `TELEGRAM_CHAT_ID=`

No secret value is returned by the integration-status API.

## Verification performed in sandbox

Backend:
- `200 passed`
- includes AI disabled/fail-closed and integration-secret exposure tests

Frontend:
- `10 passed`
- includes Today / Last 7 Days / Custom history-period tests
- TypeScript project check passed with `--skipLibCheck`

Vite production build could not be completed inside the Linux sandbox because the uploaded project contained Windows-native Rollup dependencies and network installation of the Linux optional binary timed out. This is an environment/platform dependency issue, not a TypeScript source error. Run `npm run build` on the target Windows machine before GitHub push.

## Important existing architecture note

The Settings risk/strategy controls are still browser-local UI configuration. They intentionally do not mutate the deterministic backend risk/strategy/execution configuration. This was preserved to avoid silently changing live Demo trading behavior.

Telegram currently reports whether credentials are configured; an outbound notification sender is not enabled by this patch.

## Groq correction
- AI provider is Groq-only in this build.
- Secret variable is `GROQ_API_KEY`; no OpenAI API key is required.
- Default model is `qwen/qwen3.8-27b`.
- Groq REST base URL is `https://api.groq.com/openai/v1`; the `/openai/v1` path is Groq's official OpenAI-compatible API path, not an OpenAI service endpoint.
- AI remains read-only/analysis-only and has no execution authority.
