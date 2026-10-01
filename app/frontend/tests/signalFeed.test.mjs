import assert from 'node:assert/strict';
import test from 'node:test';
import { evaluateSignalExpiry } from '../src/utils/signalLifecycle.ts';

test('SignalFeed actionable filtering logic', () => {
    const signalTime = new Date('2026-09-21T14:05:00Z').getTime();
    
    const baseSig = {
        id: '1',
        status: 'New',
        signalTime: new Date(signalTime).toISOString(),
        expiresAt: new Date(signalTime + 300000).toISOString(),
        age: '0s',
        isExpired: false
    };

    const getActionable = (signals) => signals.slice(0, 50).filter(s => !s.isExpired && s.status !== 'Expired' && s.status !== 'Rejected' && s.status !== 'Executed');

    // 1. Fresh signal appears in Actionable
    const fresh = evaluateSignalExpiry(baseSig, signalTime + 299000);
    assert.equal(getActionable([fresh]).length, 1, 'Fresh signal should be actionable');

    // 2. Expired signal does NOT appear in Actionable
    const expired = evaluateSignalExpiry(baseSig, signalTime + 301000);
    assert.equal(getActionable([expired]).length, 0, 'Expired signal should not be actionable');

    // 3. At exactly 300 sec, signal moves out of Actionable
    const transition = evaluateSignalExpiry(baseSig, signalTime + 300000);
    assert.equal(getActionable([transition]).length, 0, 'Transition signal should not be actionable');

    // 4. Rejected signal stays out of Actionable
    const rejectedSig = { ...baseSig, id: '2', status: 'Rejected' };
    assert.equal(getActionable([rejectedSig]).length, 0, 'Rejected signal should not be actionable');
});
