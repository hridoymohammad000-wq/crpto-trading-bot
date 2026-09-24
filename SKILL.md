# SKILL.md

## Purpose

This file defines the mandatory working rules for the AI coding agent operating on this project.

The agent must treat the current local workspace as the source of truth, inspect before modifying, preserve existing architecture and safeguards, and obtain explicit user approval before starting any new task.

---

## 1. Mandatory Approval Gate

**The agent must NEVER start a new task without explicit user approval.**

For every new task, phase, fix, refactor, audit, feature, cleanup, migration, configuration change, test addition, deployment change, or documentation update:

1. Inspect the relevant existing files first.
2. Explain the issue or requested change.
3. State the exact scope of the proposed work.
4. List the files expected to be modified.
5. State any risks, assumptions, or decisions required.
6. Present a concise implementation plan.
7. Ask the user for explicit approval.
8. Wait for approval before making any change.

Accepted approval examples:
- `Approved`
- `Yes, proceed`
- `Start`
- `Go ahead`
- `Koro`
- another clear affirmative instruction from the user

Until approval is received, the agent may inspect and report, but must not modify source files, create implementation files, run destructive commands, change configuration, install packages, migrate databases, deploy, or package a final ZIP.

---

## 2. New Task Means New Approval

Approval applies only to the exact task and scope that was approved.

If, during implementation, the agent discovers a new issue that requires work outside the approved scope:

- stop that new work;
- report the finding;
- classify it;
- explain the proposed fix;
- ask for fresh approval.

Do not silently expand scope.

Examples requiring new approval:
- fixing an unrelated bug discovered during another fix;
- redesigning UI while fixing backend logic;
- changing strategy rules during scanner debugging;
- changing database schema during a frontend task;
- introducing a new dependency;
- enabling execution/trading;
- changing risk limits;
- changing deployment architecture.

---

## 3. Inspection Before Modification

Before editing:

- identify the active source-of-truth folders;
- inspect the existing implementation;
- trace the relevant code path;
- confirm the problem from code, logs, tests, or runtime evidence;
- distinguish confirmed bugs from assumptions.

Do not modify code based only on a guess.

Classify findings as:

- `CONFIRMED BUG`
- `DESIGN ISSUE`
- `SAFETY ISSUE`
- `DATA/UI CONSISTENCY ISSUE`
- `CLEANUP`
- `NEEDS USER DECISION`

Only confirmed safe fixes inside the approved scope may be implemented without another approval.

---

## 4. Preserve User-Controlled Trading Rules

The agent must not invent, relax, or silently change trading logic.

Do not change without explicit approval:

- strategy thresholds;
- EMA/RSI/ADX rules;
- market filters;
- scoring;
- signal grades;
- entry windows;
- 15m/5m/1m confirmation rules;
- RR requirements;
- stop-loss rules;
- take-profit rules;
- leverage;
- position sizing;
- maximum open trades;
- cooldown;
- daily loss limits;
- duplicate-signal rules;
- execution allowlists;
- readiness gates.

If a rule is missing or unclear, mark it `NEEDS USER DECISION`.

---

## 5. Execution Safety

Execution state must never be changed implicitly.

Before changing any of the following, obtain explicit approval:

- `EXECUTION_ENABLED`
- Demo/Testnet/Live mode
- Bybit endpoint
- API credentials usage
- order submission behavior
- risk engine execution gates
- automatic bot start
- restart recovery that can resume execution
- position close behavior

Never switch from Demo to Live automatically.

Never use live credentials unless the user explicitly directs it.

---

## 6. Read-Only AI Analyst

The AI Analyst must remain read-only unless the user explicitly approves a different architecture.

The AI Analyst may:

- summarize scanner status;
- explain `WATCHING`, `ARMED`, `TRIGGERED`, `INVALIDATED`, `COOLDOWN`;
- explain reason codes;
- summarize runtime health;
- summarize positions and trade history;
- explain risk/readiness blocks;
- interpret existing performance metrics;
- compare current candidates using factual system data.

The AI Analyst must not:

- place orders;
- start or stop the bot;
- change strategy settings;
- change risk settings;
- modify SL/TP;
- approve rejected trades;
- bypass readiness;
- change execution mode;
- alter the database;
- write configuration.

---

## 7. Source of Truth

Use the active local source tree confirmed by the user/workspace.

Do not assume ZIP archives, old deploy folders, backups, generated builds, or stale copies are authoritative.

Before substantial work, verify:

- active backend path;
- active frontend path;
- active `.env`;
- active database;
- current running process/port if runtime behavior matters.

Do not edit packaged `dist`, build output, backup copies, or generated artifacts as if they were source.

---

## 8. Minimal Safe Changes

Prefer the smallest change that fixes the confirmed problem.

Avoid:

- unnecessary refactors;
- architecture rewrites;
- mass formatting;
- unrelated cleanup;
- dependency upgrades unrelated to the task;
- renaming public APIs without need;
- replacing working modules only for style.

Preserve backward compatibility where practical.

---

## 9. Tests Are Mandatory

For approved code changes:

1. run the relevant focused tests;
2. add regression tests for confirmed bugs when appropriate;
3. run the full affected test suite;
4. run frontend build/typecheck when frontend changes;
5. report exact PASS / FAIL / NOT RUN results.

Never claim a fix is complete only because code compiles.

For runtime bugs, also perform code-path or live runtime verification when possible.

---

## 10. Runtime Observability

Do not hide failures.

External/network awaits should have bounded behavior where appropriate.

Avoid silent patterns such as:

```python
except Exception:
    pass
```

for important runtime paths.

Prefer useful structured diagnostics for:

- scanner refresh;
- market-data fetch;
- exchange calls;
- reconciliation;
- state transitions;
- readiness blocks;
- duplicate suppression;
- execution attempts;
- background task crashes;
- timeout stages.

Avoid excessive log spam.

---

## 11. Database and Persistence

Before schema or persistence changes:

- inspect the current schema and repository logic;
- explain migration impact;
- obtain explicit approval.

Do not delete, recreate, reset, or migrate user data without approval.

Runtime-generated database files must not be treated as source code.

---

## 12. Frontend Data Integrity

UI labels and metrics must reflect their real data source.

Do not present:

- historical data as current-session data;
- local time as UTC;
- seeded/demo metrics as live account metrics;
- fixed symbol monitoring as dynamic scanner coverage;
- stale snapshots as live runtime state.

If multiple sources exist, label them clearly.

---

## 13. File Creation and Cleanup

Before creating new implementation files, explain why they are needed in the approval plan.

Temporary debugging files should be removed after use unless they are intentionally retained.

Final packages should exclude unnecessary runtime/generated files such as:

- `.venv`
- `node_modules`
- caches
- `.pyc`
- temporary test folders
- runtime locks
- real `.env`
- secrets
- generated local databases unless explicitly requested

---

## 14. Final Report After Approved Work

After completing an approved task, report:

- what was changed;
- exact files modified;
- bugs fixed;
- issues not changed;
- tests run;
- test results;
- remaining risks;
- any new findings requiring approval.

Do not automatically begin the next task.

---

## 15. Mandatory End-of-Task Stop

After an approved task is complete:

**STOP.**

Do not continue into another task, phase, cleanup, optimization, or feature.

Instead provide:

> Task completed. I found the following possible next task(s): [summary].  
> No further changes will be made until you approve the next task.

Then wait for the user's approval.

---

## 16. Approval Template

Before every new task, use this structure:

### Proposed Task
[short task name]

### Why
[confirmed problem / requested goal]

### Scope
[exact work to be done]

### Files Expected to Change
- file 1
- file 2

### Will Not Change
- strategy rules
- risk rules
- execution mode
- unrelated modules
- other protected areas relevant to the task

### Validation
- focused tests
- full affected test suite
- runtime/build verification if applicable

### Approval Required
**Approve this task before I make any changes.**

---

## Golden Rule

**Inspect → Explain → Plan → Ask Approval → Wait → Implement → Test → Report → Stop.**

No new task starts without explicit user approval.
