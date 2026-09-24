import assert from 'node:assert/strict';
import test from 'node:test';
import { filterTradesByHistoryPeriod } from '../src/features/trades/historyPeriod.ts';

const base = {
  id: 'x', symbol: 'BTCUSDT', side: 'LONG', strategy: 'EMA + RSI', timeframe: '5m',
  entry: 1, exit: 1, sl: 0, tp: 0, pnl: 0, pnlPercentage: 0, rr: '-', duration: 'Closed',
  result: 'Breakeven', closedAt: 'x'
};

const now = new Date('2026-09-22T16:00:00');
const trades = [
  { ...base, id: 'today', closedAtISO: '2026-09-22T10:00:00' },
  { ...base, id: 'week', closedAtISO: '2026-09-18T10:00:00' },
  { ...base, id: 'old', closedAtISO: '2026-09-10T10:00:00' },
];

test('Today keeps only today trades', () => {
  assert.deepEqual(filterTradesByHistoryPeriod(trades, { period: 'Today', now }).map(t => t.id), ['today']);
});

test('7D keeps today plus previous six calendar days', () => {
  assert.deepEqual(filterTradesByHistoryPeriod(trades, { period: '7D', now }).map(t => t.id), ['today', 'week']);
});

test('Custom range uses inclusive dates', () => {
  assert.deepEqual(filterTradesByHistoryPeriod(trades, { period: 'Custom', now, fromDate: '2026-09-18', toDate: '2026-09-18' }).map(t => t.id), ['week']);
});
