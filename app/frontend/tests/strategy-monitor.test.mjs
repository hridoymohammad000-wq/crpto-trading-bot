import assert from 'node:assert/strict';
import test from 'node:test';

import {
  StrategyContractError,
  parseStrategyDiagnostic,
} from '../src/api/strategyContract.ts';
import {
  STRATEGY_SYMBOLS,
  createInitialMonitorState,
  fetchStrategyOutcomes,
  mergeStrategyOutcomes,
} from '../src/features/strategy/monitorState.ts';

function backendResponse(overrides = {}) {
  return {
    symbol: 'BTCUSDT',
    strategy: 'EMA_RSI_ADX_MOMENTUM',
    evaluation_time: '2026-09-14T15:10:00Z',
    latest_5m_candle_time: '2026-09-14T15:05:00Z',
    latest_15m_candle_time: '2026-09-14T14:45:00Z',
    result: 'NO_SIGNAL',
    side: null,
    reference_entry_price: null,
    confidence: null,
    reason_codes: ['ENTRY_WINDOW_EXPIRED'],
    indicators: {
      ema_fast: '78420.24',
      ema_slow: '78306.31',
      rsi: '55.97',
      adx: '29.68',
      volume: '476.947',
      average_volume: '550.45735',
      higher_tf_ema_fast: '78219.29',
      higher_tf_ema_slow: '78028.08',
      higher_tf_ema_fast_previous: '78153.46',
    },
    crossover_age_candles: 4,
    duplicate_setup: false,
    ...overrides,
  };
}

test('maps a backend no-signal response and decimal strings', () => {
  const result = parseStrategyDiagnostic(backendResponse());
  assert.equal(result.result, 'NO_SIGNAL');
  assert.deepEqual(result.reasonCodes, ['ENTRY_WINDOW_EXPIRED']);
  assert.equal(result.indicators.emaFast, 78420.24);
  assert.equal(result.side, null);
});

test('maps a backend signal response', () => {
  const result = parseStrategyDiagnostic(
    backendResponse({
      result: 'SIGNAL',
      side: 'BUY',
      reference_entry_price: '78450.50',
      confidence: 92,
      reason_codes: [],
      crossover_age_candles: 0,
    }),
  );
  assert.equal(result.result, 'SIGNAL');
  assert.equal(result.side, 'BUY');
  assert.equal(result.referenceEntryPrice, 78450.5);
  assert.equal(result.confidence, 92);
});

test('rejects malformed strategy responses', () => {
  assert.throws(
    () => parseStrategyDiagnostic(backendResponse({ indicators: null })),
    StrategyContractError,
  );
  assert.throws(
    () => parseStrategyDiagnostic(backendResponse({ result: 'SIGNAL' })),
    StrategyContractError,
  );
});

test('initial monitor state exposes a loading card for every symbol', () => {
  const state = createInitialMonitorState();
  for (const symbol of STRATEGY_SYMBOLS) {
    assert.equal(state[symbol].isLoading, true);
    assert.equal(state[symbol].data, null);
    assert.equal(state[symbol].errorMessage, null);
  }
});

test('one-symbol failure does not break successful symbol results', async () => {
  const outcomes = await fetchStrategyOutcomes(async (symbol) => {
    if (symbol === 'ETHUSDT') throw new Error('ETH evaluation timed out');
    return parseStrategyDiagnostic(backendResponse({ symbol }));
  });
  const state = mergeStrategyOutcomes(
    createInitialMonitorState(),
    outcomes,
    '2026-09-14T15:11:00Z',
  );

  assert.equal(state.BTCUSDT.data?.result, 'NO_SIGNAL');
  assert.equal(state.SOLUSDT.data?.result, 'NO_SIGNAL');
  assert.equal(state.ETHUSDT.data, null);
  assert.equal(state.ETHUSDT.isLoading, false);
  assert.equal(state.ETHUSDT.errorMessage, 'ETH evaluation timed out');
  assert.equal(state.BTCUSDT.lastSuccessfulAt, '2026-09-14T15:11:00Z');
});
