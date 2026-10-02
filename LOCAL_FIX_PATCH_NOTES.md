# Local Fix Patch — 2026-09-28

This package is intended for local replacement/testing only. No GitHub push is performed by this package.

## Included fixes

1. Daily PnL now comes from today's closed-trade realized PnL ledger instead of unrealized equity/wallet delta.
2. Trade History includes exit-reason and diagnostic columns. SL/TP labels are only inferred when the persisted configured level and exit price correlate; otherwise the UI says the cause is not proven. The inferred attribution is persisted in the local closed-trade ledger.
3. Scanner UI shows only candidates with Market Score >= 60 and Setup Score >= 60, ranked and capped at Top 10.
4. Dashboard chart symbol selector is driven by Scanner Top 10 instead of fixed BTC/ETH/SOL. Active-position and currently selected symbols remain visible.
5. Signals page uses card view and hides Rejected signals from the actionable feed.
6. Strategy Lab has a real paper-trade lifecycle: Total/Open/Closed/Wins/Losses/SL Hit/TP Hit/Win Rate/Net PnL/Avg R, plus exit reason and heuristic SL diagnosis.

## Strategy Lab paper-risk policy

Strategy Lab remains paper-only and never submits exchange orders. To make lifecycle metrics deterministic, new and existing paper signals use a research benchmark of 1% paper stop and 2% paper target (2R). SL diagnosis is explicitly marked heuristic.

## Verification in packaging environment

- Backend: 201 pytest tests passed.
- Frontend: 19 Node tests passed.
- Changed TypeScript/TSX files passed TypeScript syntax transpilation.
- A full Vite production build was not run because package installation was unavailable in the packaging environment; run `npm ci` then `npm run build` locally after replacement.

## Safety

Runtime databases, lock files, caches, node_modules, local `.env`, and old deployment-token helper scripts are excluded from this ZIP. Keep your existing local `.env` separately.
