import assert from 'node:assert/strict';
import test from 'node:test';
import { evaluateSignalExpiry } from '../src/utils/signalLifecycle.ts';

test('Signal expires exactly at 300 seconds', () => {
    const signalTime = new Date('2026-09-21T14:05:00Z').getTime();
    const expiresAt = signalTime + 300 * 1000;
    
    const sig = {
        id: '1',
        status: 'New',
        signalTime: new Date(signalTime).toISOString(),
        expiresAt: new Date(expiresAt).toISOString(),
        age: '0s',
        isExpired: false
    };

    // 299 seconds
    const active = evaluateSignalExpiry(sig, signalTime + 299 * 1000);
    assert.equal(active.isExpired, false);
    assert.equal(active.status, 'New');

    // 300 seconds
    const expired300 = evaluateSignalExpiry(sig, signalTime + 300 * 1000);
    assert.equal(expired300.isExpired, true);
    assert.equal(expired300.status, 'Expired');

    // 301 seconds
    const expired301 = evaluateSignalExpiry(sig, signalTime + 301 * 1000);
    assert.equal(expired301.isExpired, true);
    assert.equal(expired301.status, 'Expired');
});
