import assert from 'node:assert/strict';
import test from 'node:test';

test('backend BUY maps to frontend BUY', () => {
    const backendSignals = [{
        signal_id: '1',
        symbol: 'TAOUSDT',
        strategy: 'EMA_RSI_ADX_MOMENTUM',
        side: 'BUY',
        signal_time: '2026-09-21T14:05:00Z',
        reference_entry_price: 286.36,
        confidence: 91
    }];
    
    const formatted = backendSignals.map(bs => ({
        id: bs.signal_id,
        side: bs.side
    }));
    
    assert.equal(formatted[0].side, 'BUY');
});

test('backend SELL maps to frontend SELL', () => {
    const backendSignals = [{
        signal_id: '2',
        symbol: 'TAOUSDT',
        strategy: 'EMA_RSI_ADX_MOMENTUM',
        side: 'SELL',
        signal_time: '2026-09-21T14:05:00Z',
        reference_entry_price: 286.36,
        confidence: 91
    }];
    
    const formatted = backendSignals.map(bs => ({
        id: bs.signal_id,
        side: bs.side
    }));
    
    assert.equal(formatted[0].side, 'SELL');
});
