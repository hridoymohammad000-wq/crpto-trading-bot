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

test('SignalFeed actionable filtering prevents Expired signals from rendering', () => {
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

    // 1. New signal renders (299 sec)
    const freshSignal = evaluateSignalExpiry(sig, signalTime + 299 * 1000);
    const visibleFresh = [freshSignal].filter(s => s.status !== 'Rejected');
    const actionableFresh = visibleFresh.filter(s => !s.isExpired && s.status !== 'Expired');
    assert.equal(actionableFresh.length, 1, 'New signal should render in actionable grid');
    
    // 2. 300-second transition removes the card
    const expiredSignal = evaluateSignalExpiry(sig, signalTime + 300 * 1000);
    const visibleExpired = [expiredSignal].filter(s => s.status !== 'Rejected');
    const actionableExpired = visibleExpired.filter(s => !s.isExpired && s.status !== 'Expired');
    assert.equal(actionableExpired.length, 0, '300-second transition must remove the card');
    
    // 3. Expired signal does not render (301 sec)
    const fullyExpiredSignal = evaluateSignalExpiry(sig, signalTime + 301 * 1000);
    const visibleFullyExpired = [fullyExpiredSignal].filter(s => s.status !== 'Rejected');
    const actionableFullyExpired = visibleFullyExpired.filter(s => !s.isExpired && s.status !== 'Expired');
    assert.equal(actionableFullyExpired.length, 0, 'Expired signal must not render');
});
