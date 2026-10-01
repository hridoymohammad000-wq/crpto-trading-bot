import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const scannerPageUrl = new URL('../src/features/scanner/ScannerPage.tsx', import.meta.url);
const scannerApiUrl = new URL('../src/api/scanner.ts', import.meta.url);

test('scanner UI and contract expose the 1H, 15m, 5m pipeline', async () => {
  const [page, api] = await Promise.all([
    readFile(scannerPageUrl, 'utf8'),
    readFile(scannerApiUrl, 'utf8'),
  ]);

  for (const label of ['1H Trend', '15m Setup', '5m Entry']) {
    assert.match(page, new RegExp(label));
  }
  const oldLabels = ['15m ' + 'Ctx', '5m ' + 'Setup', '1m ' + 'Trigger'];
  for (const oldLabel of oldLabels) {
    assert.doesNotMatch(page, new RegExp(`>${oldLabel}<`));
  }
  for (const field of ['trend_1h', 'setup_15m', 'entry_5m']) {
    assert.match(api, new RegExp(field));
    assert.match(page, new RegExp(field));
  }
});
