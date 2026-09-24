# AGENTS.md — Crypto Trading Bot Engineering Contract

## 1. Project scope

Work only inside:

`D:\crypto-trading-bot-FINAL-SINGLE-APP-STEP0-9-MERGED\app`

Backend:
`D:\crypto-trading-bot-FINAL-SINGLE-APP-STEP0-9-MERGED\app\backend`

Frontend:
`D:\crypto-trading-bot-FINAL-SINGLE-APP-STEP0-9-MERGED\app\frontend`

This project is a **Bybit Demo** intraday crypto trading bot.

Do not use Live trading unless the user explicitly authorizes a separate future phase.

---

## 2. Core engineering rule

Build and preserve this model:

**Deterministic Python safety + multi-strategy technical analysis + AI market-context analysis.**

AI may analyze, classify, rank, explain, and provide structured market context.

AI must never directly bypass the deterministic safety path or call exchange execution methods.

Final execution authority remains:

`Signal -> Risk Engine -> TradingReadiness -> Execution Engine -> Bybit Demo`

---

## 3. Source of truth

Bybit Demo is the source of truth for:

- account/wallet state
- positions
- orders
- fills
- leverage
- SL/TP state

SQLite is only for:

- persistence
- recovery
- idempotency
- signal history
- trade history
- pre-trade snapshots
- post-trade reviews
- diagnostics

Never treat SQLite as exchange truth.

---

## 4. Existing architecture

Preserve:

`Bybit Demo`
`-> Exchange Adapter`
`-> Market Data / Account Service`
`-> Scanner`
`-> Strategy`
`-> State Machine`
`-> Risk Engine`
`-> TradingReadiness`
`-> Reconciliation Safety`
`-> Execution Engine`
`-> Bybit Demo`
`-> SQLite + WebSocket + Frontend`

Ownership:

- Scanner discovers candidates.
- Strategy decides.
- State Machine tracks lifecycle.
- Risk Engine constrains exposure.
- Reconciliation explains local/exchange reality.
- TradingReadiness grants permission.
- Execution Engine alone performs trade-capable exchange actions.
- SQLite remembers.
- WebSocket/frontend report.
- BotRuntime orchestrates.

Scanner, strategies, AI, risk, state machine, and frontend must never directly place exchange orders.

---

## 5. Current validated strategy

Do not silently replace the currently validated strategy.

Current validated behavior includes:

- 15m higher-timeframe context
- 5m entry/signal logic
- EMA 9
- EMA 21
- RSI
- ADX
- RVOL
- fresh crossover requirement

Known verified thresholds:

- crossover age `<= 1` candle
- long RSI `52–70`
- ADX `> 22`
- RVOL `> 1.0`

Do not invent a 1m trigger.

Do not loosen thresholds simply to manufacture a signal.

Future strategies must be explicit new modules, independently testable and observable.

---

## 6. Target multi-strategy system

Long-term strategy support should include independently testable modules such as:

1. Momentum continuation
2. Trend-following
3. Pullback continuation
4. Breakout
5. Support/resistance bounce
6. Pattern-confirmed continuation/reversal where validated

Prefer a strategy registry rather than one giant strategy function.

Suggested direction:

```text
backend/app/
├── strategies/
│   ├── registry.py
│   ├── momentum.py
│   ├── trend_following.py
│   ├── pullback.py
│   ├── breakout.py
│   ├── support_resistance.py
│   ├── candlestick.py
│   └── chart_patterns.py
│
├── technical_analysis/
│   ├── indicators.py
│   ├── market_structure.py
│   ├── support_resistance.py
│   ├── trendlines.py
│   ├── candlestick_patterns.py
│   └── chart_patterns.py
│
├── ai/
│   ├── analyst.py
│   ├── confluence.py
│   ├── setup_ranker.py
│   └── explanation.py
```

Do not refactor merely for aesthetics. Add structure only when implementing real capability.

---

## 7. Technical-analysis layer

The system should eventually produce structured, machine-readable context for each symbol:

- EMA values/alignment
- RSI
- ADX
- RVOL
- ATR / volatility
- market structure: HH / HL / LH / LL
- support zones
- resistance zones
- trend direction
- trendlines
- breakout levels
- retest zones
- candlestick patterns
- chart patterns

Every detected object should include evidence where applicable:

- symbol
- timeframe
- source candle timestamps
- relevant price coordinates or zone
- detection method
- confidence
- invalidation condition

Do not draw decorative/fake chart annotations.

---

## 8. AI role

AI is a **market-analysis and confluence layer**, not an exchange executor.

Allowed AI responsibilities:

- market-regime classification
- market-structure interpretation
- support/resistance context
- candlestick/chart-pattern interpretation
- multi-strategy comparison
- setup-quality analysis
- WAIT / WATCH / CONFIRM reasoning
- rejection explanation
- post-trade review
- recurring Demo failure-pattern analysis
- strategy research assistance

Prefer structured AI output.

Example shape:

```json
{
  "trend": "UPTREND",
  "regime": "TRENDING",
  "support_zones": [{"low": 82600, "high": 82750}],
  "resistance_zones": [{"low": 84100, "high": 84250}],
  "patterns": [{"type": "ASCENDING_TRIANGLE", "confidence": 0.78}],
  "recommended_state": "WAITING_FOR_CONFIRMATION",
  "execution_authority": false
}
```

`execution_authority` must remain false for the AI layer.

---

## 9. AI security boundary

Never inject `ExecutionService` or direct exchange trade methods into the AI service.

AI may read:

- market data
- scanner state
- strategy state
- indicators
- risk result
- account summary
- trade history
- reconciliation state

AI must not directly call:

- `place_order`
- `cancel_order`
- `set_leverage`
- trading-stop / position-changing methods
- position-size override
- Risk override
- TradingReadiness override

AI/API keys must stay backend-only.

Never print, log, commit, or expose secrets.

---

## 10. Chart requirements

The frontend chart should eventually visualize what the bot is actually seeing:

- candlesticks
- EMA 9
- EMA 21
- support zones
- resistance zones
- detected trendlines
- HH / HL / LH / LL
- breakout/retest zones
- genuine signal markers
- entry
- stop loss
- take profit
- active position marker
- candlestick-pattern markers
- chart-pattern markers

Side/bottom context should expose:

- RSI
- ADX
- RVOL
- ATR
- 15m trend/context
- current strategy
- setup state
- rejection/wait reason
- confluence evidence

Frontend annotations must come from backend-derived analysis/state, not independent guesses.

---

## 11. State-machine direction

Preserve existing working lifecycle semantics.

Future extensions may evolve toward:

```text
DISCOVERED
-> ANALYZING
-> WATCHING
-> ARMED
-> WAITING_CONFIRMATION
-> TRIGGERED
-> RISK_APPROVED
-> READY
-> IN_POSITION
```

Do not add states without defining:

- legal transitions
- transition owner
- persistence behavior
- restart behavior
- invalidation behavior
- tests

---

## 12. Demo learning philosophy

Demo losses are allowed.

Do not optimize the system by simply preventing every possible loss.

The purpose of Demo is to learn:

- what the system believed before entry
- why a trade was taken
- which strategy triggered
- what indicators/context supported it
- what AI said before entry
- what Risk approved
- what happened afterward
- why the setup succeeded or failed

A market prediction being wrong is acceptable Demo learning data.

Software-safety failures are not acceptable learning events.

Unacceptable software failures include:

- duplicate orders
- missing required SL
- uncontrolled sizing
- wrong leverage
- ignored reconciliation mismatch
- stale signal execution
- ignored DB failure
- AI bypass of safety gates
- blind resubmit after ambiguous exchange response

Principle:

**Strategy may be wrong. Infrastructure safety must remain deterministic and fail-closed.**

---

## 13. Mandatory pre-trade snapshot

Before any Demo entry is submitted, persist a durable pre-trade snapshot containing enough evidence to reproduce the decision.

At minimum:

- signal_id
- symbol
- side
- strategy name/version
- 15m context
- 5m signal candle identity
- source candle timestamps
- indicator values
- support/resistance context
- market structure
- detected patterns
- AI analysis used at the time
- AI model/config/version if applicable
- risk decision
- proposed entry
- proposed SL
- proposed TP
- proposed size
- leverage
- account/trading-capacity snapshot
- reconciliation status/timestamp
- TradingReadiness result
- created_at / expiry
- deterministic orderLinkId / intent identifier

The snapshot must exist before execution so post-trade analysis cannot rewrite history.

---

## 14. Post-trade review

After a trade closes, compare:

**What the system believed before entry**
vs
**What actually happened**

Do not let AI invent pre-trade reasons after the result is known.

Store post-trade analysis separately from the immutable pre-trade snapshot.

Review may include:

- strategy correctness
- regime classification
- support/resistance behavior
- volume confirmation
- pattern validity
- entry timing
- stop placement
- target placement
- slippage
- risk/reward
- recurring failure/success patterns

---

## 15. Safety invariants

Do not weaken:

- Demo-only execution
- max active positions
- portfolio open-risk cap
- daily loss limits
- leverage constraints
- available trading capacity checks
- signal freshness
- duplicate protection
- reconciliation freshness
- DB fail-closed behavior
- singleton runtime leadership
- startup reconciliation barrier
- deterministic idempotency
- SL/TP verification
- reduce-only safety paths

Unknown trading capacity must block new/increasing exposure.

Never use wallet balance or equity as a hidden fallback for unknown capacity.

Reduce-only safety exits must remain available when appropriate.

---

## 16. Bybit account rules

Current verified account:

- Bybit Demo
- UNIFIED
- ISOLATED_MARGIN

Do not automatically change account margin mode.

Do not switch to Cross/Portfolio without explicit user authorization.

Do not fabricate unavailable account-wide margin fields.

Any future Bybit account-semantics change must be verified against current official Bybit V5 documentation before implementation.

---

## 17. Execution ownership

Only the Execution Engine may perform trade-capable exchange actions.

Audit before/after changes to ensure scanner, strategy, risk, state machine, AI, and frontend cannot perform exchange execution.

Trade-capable actions include:

- order creation
- execution-related order cancellation
- leverage setting
- position-changing calls
- protective-order placement/update

---

## 18. Idempotency and ambiguous submits

Before an order POST:

- create durable execution intent
- assign deterministic `orderLinkId`
- persist intent before exchange submission

If exchange response is ambiguous:

- do not blindly retry
- enter an UNKNOWN/RECONCILING state
- query exchange truth
- resolve using durable identifiers
- only then continue

Restart/retry must never create a duplicate order for the same intent.

---

## 19. Current Step 9 status

Treat runtime evidence as authoritative.

```text
Q1  [x] Demo API authentication
Q2  [x] Available trading capacity known
Q3  [x] Reconciliation clean
Q4  [x] Infrastructure ready
Q5  [ ] Genuine market-generated signal — WAITING
Q6  [ ] RiskDecision = APPROVED
Q7  [ ] Real Bybit Demo order acknowledged
Q8  [ ] Position appears on Bybit
Q9  [ ] Actual exchange SL/TP verified
Q10 [ ] Local DB matches exchange state
Q11 [ ] Post-trade reconciliation clean
Q12 [ ] Restart/retry produces no duplicate
```

Q4 infrastructure is healthy, but per-signal readiness may remain `NO_READINESS_DECISION_YET` until a genuine fresh signal exists.

Q5 must not be forced.

---

## 20. Q5 rules

A genuine signal must originate from:

- current Bybit Demo market data
- a closed strategy candle
- the real scanner
- the real strategy
- the real state machine

Do not:

- inject fake signals
- create synthetic live candles
- replay historical candles into live runtime
- lower thresholds merely to trigger
- manually set TRIGGERED
- force Risk APPROVED
- manually invoke execution

If there is no signal:

`Q5 = WAITING FOR GENUINE SIGNAL`

That is a valid result.

---

## 21. Testing rules

For every meaningful backend change:

1. run targeted tests
2. run full backend regression suite

Use:

```cmd
.\.venv\Scripts\python.exe -m pytest tests\ -q --basetemp=tmp_agent
```

For frontend changes:

```cmd
npm test
npm run build
```

Do not report PASS without command evidence.

If a failure is environmental/tooling rather than application logic, report that distinction precisely.

---

## 22. Runtime validation

For real Demo validation confirm:

- backend running
- Demo environment
- runtime leadership owned
- startup reconciliation complete
- reconciliation SYNCED
- DB healthy
- trading capacity known
- no unexpected positions/orders
- genuine signal freshness
- Risk decision
- TradingReadiness
- exchange acknowledgement
- actual position state
- actual exchange SL/TP
- local DB match
- post-trade reconciliation
- restart/retry duplicate protection

Never infer runtime PASS from unit tests alone.

---

## 23. No overclaiming

Never state:

- complete
- fully verified
- production ready
- Demo ready
- PASS

unless required evidence was actually observed.

Keep separate:

- code-level validation
- test-level validation
- runtime validation
- real exchange Demo validation

If evidence is missing, state exactly what remains unknown.

---

## 24. Change discipline

Before editing:

1. inspect relevant implementation
2. trace callers/callees
3. understand ownership
4. identify tests
5. make the smallest safe change

After editing:

1. run targeted tests
2. run regression tests
3. inspect runtime behavior if relevant
4. report changed files
5. report exact evidence
6. state remaining blocker

Do not make unrelated refactors while validating a single checklist item.

---

## 25. Secrets

Never display or print:

- Bybit API key
- Bybit API secret
- OpenAI/AI API key
- private credentials

Do not dump `.env` contents into logs.

Never commit `.env`.

Use `.env.example` placeholders for documentation.

---

## 26. Completion order

Finish current real Demo validation before allowing major AI/multi-strategy changes to alter live signal behavior.

Order:

```text
Finish Q5
-> Q6
-> Q7
-> Q8
-> Q9
-> Q10
-> Q11
-> Q12
-> freeze a known-good Step 9 baseline
-> technical-analysis foundation
-> multi-strategy registry
-> AI analysis/confluence
-> chart overlays
-> collect Demo trade dataset
-> evidence-driven strategy tuning
```

Do not mix an unvalidated Step 9 execution path with a major strategy rewrite.

---

## 27. AI / multi-strategy rollout

### Phase A — Technical-analysis foundation

Add deterministic/testable:

- support/resistance
- market structure
- trendlines
- candlestick patterns
- chart patterns
- ATR/volatility context

No execution behavior change.

### Phase B — Multi-strategy registry

Add strategies one by one.

Each strategy requires:

- documented entry logic
- documented invalidation
- independent tests
- state-machine compatibility
- observable rejection reasons
- no direct execution authority

### Phase C — AI analyst

Add read-only AI analysis.

Requirements:

- structured schema
- timeouts
- failure handling
- model-output validation
- no secret exposure
- no direct execution dependency

If AI is unavailable, behavior must follow an explicitly defined safe policy.

### Phase D — Confluence

Combine:

- deterministic technical evidence
- strategy outputs
- optional AI context

AI must never override hard Risk/Readiness safety.

### Phase E — Chart overlays

Render backend-derived evidence in frontend.

### Phase F — Demo learning loop

Collect Demo trades before tuning.

Compare:

- immutable pre-trade snapshot
- actual outcome
- post-trade review
- recurring failure/success patterns

Any tuning should be evidence-driven.

---

## 28. Required final report from the agent

At the end of every task report:

1. Task attempted
2. Status: PASS / WAITING / BLOCKED / FAIL
3. What was inspected
4. What was changed
5. Why it was changed
6. Files changed
7. Tests run
8. Exact test results
9. Runtime checks
10. Exact runtime evidence
11. Orders submitted, if any
12. Position/exchange state, if relevant
13. Safety invariants confirmed
14. Remaining blocker
15. Recommended next single step

Do not claim anything beyond observed evidence.

---

## 29. Standing instruction

Follow this file as the engineering contract for this project.

When a task conflicts with these rules:

- preserve safety
- preserve deterministic execution authority
- preserve Demo-only operation
- preserve evidence/observability
- preserve fail-closed behavior
- obtain explicit user authorization before changing major safety invariants

The objective is not to make every checklist green quickly.

The objective is to build a system whose decisions, mistakes, and exchange actions can be explained, reproduced, tested, and safely improved.
