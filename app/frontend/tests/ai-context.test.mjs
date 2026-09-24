import assert from 'node:assert/strict';
import test from 'node:test';

import { buildEnrichedAIContext } from '../src/features/ai/contextBuilder.ts';

test('buildEnrichedAIContext merges base context with factual data payload', () => {
  const baseContext = { activeTab: 'Dashboard', botStatus: 'RUNNING' };
  
  const scannerStatus = { universe_count: 100, eligible_count: 50 };
  const scannerCandidates = [{ symbol: 'BTCUSDT', state: 'WATCHING', market_quality_score: 9 }];
  const scannerWatchlist = { core_symbols: ['BTCUSDT'] };
  const botRuntime = { bot_status: 'RUNNING', worker_running: true, cycle_in_progress: true };

  const enriched = buildEnrichedAIContext(
    baseContext,
    scannerStatus,
    scannerCandidates,
    scannerWatchlist,
    botRuntime
  );

  assert.equal(enriched.activeTab, 'Dashboard');
  assert.equal(enriched.botStatus, 'RUNNING');
  assert.deepEqual(enriched.scannerStatus, scannerStatus);
  assert.deepEqual(enriched.scannerCandidates, scannerCandidates);
  assert.deepEqual(enriched.scannerWatchlist, scannerWatchlist);
  assert.deepEqual(enriched.botRuntime, botRuntime);
});

test('buildEnrichedAIContext safely merges null fetched states', () => {
  const baseContext = { activeTab: 'Settings' };
  
  const enriched = buildEnrichedAIContext(
    baseContext,
    null,
    [],
    null,
    null
  );

  assert.equal(enriched.activeTab, 'Settings');
  assert.equal(enriched.scannerStatus, null);
  assert.deepEqual(enriched.scannerCandidates, []);
  assert.equal(enriched.scannerWatchlist, null);
  assert.equal(enriched.botRuntime, null);
});
