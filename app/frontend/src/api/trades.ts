import { apiClient } from './client';
import { RequestOptions } from './types';
import { Trade, TradingSymbol } from '../types';

interface BackendClosedTrade {
  order_id: string;
  symbol: TradingSymbol;
  side: 'LONG' | 'SHORT';
  quantity: number;
  entry_price?: number;
  exit_price?: number;
  realized_pnl: number;
  created_at?: string;
  updated_at?: string;
  strategy?: string | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  exit_reason?: string | null;
  diagnostic_reason?: string | null;
}

export async function getTrades(options?: RequestOptions): Promise<Trade[]> {
  const backendTrades = await apiClient.get<BackendClosedTrade[]>('/trades/persisted', options);
  
  return backendTrades.map(bt => {
    let result: 'Win' | 'Loss' | 'Breakeven' = 'Breakeven';
    if (bt.realized_pnl > 0) result = 'Win';
    else if (bt.realized_pnl < 0) result = 'Loss';

    const pnlPercentage = bt.entry_price 
      ? (bt.realized_pnl / (bt.entry_price * bt.quantity)) * 100 
      : 0;

    return {
      id: bt.order_id || Math.random().toString(),
      symbol: bt.symbol,
      side: bt.side,
      strategy: (bt.strategy || 'EMA + RSI') as any,
      timeframe: '5m', // fallback
      entry: bt.entry_price || 0,
      exit: bt.exit_price || 0,
      sl: bt.stop_loss || 0,
      tp: bt.take_profit || 0,
      pnl: bt.realized_pnl,
      pnlPercentage: pnlPercentage,
      rr: '-',
      duration: 'Closed',
      result,
      closedAt: (bt.updated_at || bt.created_at) ? new Date(bt.updated_at || bt.created_at!).toLocaleString() : 'Unknown',
      closedAtISO: bt.updated_at || bt.created_at,
      exitReason: bt.exit_reason || undefined,
      diagnosticReason: bt.diagnostic_reason || undefined,
    };
  });
}

export const tradesApi = { getTrades };
