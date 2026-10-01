import { apiClient } from './client';
import { RequestOptions } from './types';
import { Signal, TradingSymbol } from '../types';

interface BackendSignal {
  signal_id: string;
  symbol: TradingSymbol;
  strategy: string;
  side: 'BUY' | 'SELL';
  signal_time: string;
  reference_entry_price: number;
  confidence: number;
  risk_status?: string;
  execution_status?: string;
  stop_loss?: number;
  take_profit?: number;
  expires_at: string;
  is_expired: boolean;
  age_seconds: number;
}

/** Fetch signals from the backend REST endpoint */
export async function getSignals(symbol?: TradingSymbol, options?: RequestOptions): Promise<Signal[]> {
  const backendSignals = await apiClient.get<BackendSignal[]>('/signals', options);
  
  const formattedSignals: Signal[] = backendSignals.map(bs => {
    // Map to frontend Signal type
    let mappedStatus: Signal['status'] = 'New';
    if (bs.execution_status === 'EXECUTED') mappedStatus = 'Executed';
    else if (bs.risk_status === 'APPROVED') mappedStatus = 'Approved';
    else if (bs.risk_status === 'REJECTED') mappedStatus = 'Rejected';
    else if (bs.is_expired) mappedStatus = 'Expired';

    const ageSec = bs.age_seconds;
    let displayAge = `${Math.floor(ageSec)}s`;
    if (ageSec >= 60) {
      displayAge = `${Math.floor(ageSec / 60)}m ${Math.floor(ageSec % 60)}s`;
    }

    return {
      id: bs.signal_id,
      symbol: bs.symbol,
      strategy: bs.strategy as any,
      side: bs.side,
      timeframe: '5m', // fallback timeframe
      entry: bs.reference_entry_price,
      sl: bs.stop_loss || 0,
      tp: bs.take_profit || 0,
      confidence: bs.confidence,
      timestamp: new Date(bs.signal_time).toLocaleTimeString(),
      age: displayAge,
      status: mappedStatus,
      signalTime: bs.signal_time,
      expiresAt: bs.expires_at,
      isExpired: bs.is_expired,
      ageSeconds: bs.age_seconds,
    };
  });

  if (symbol) {
    return formattedSignals.filter(s => s.symbol === symbol);
  }
  return formattedSignals;
}

export const signalsApi = { getSignals };
