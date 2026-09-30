import { apiClient } from './client';
import { RequestOptions } from './types';
import { Trade, TradingSymbol } from '../types';

interface BackendClosedTrade {
  order_id?: string | null;
  symbol: TradingSymbol;
  side: 'LONG' | 'SHORT';
  quantity: number | string;
  entry_price?: number | string | null;
  exit_price?: number | string | null;
  realized_pnl: number | string;
  created_at?: string | null;
  updated_at?: string | null;
  strategy?: string | null;
  stop_loss?: number | string | null;
  take_profit?: number | string | null;
  exit_reason?: string | null;
  diagnostic_reason?: string | null;
}

function num(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export async function getTrades(options?: RequestOptions): Promise<Trade[]> {
  const backendTrades = await apiClient.get<BackendClosedTrade[]>(
    '/trades/persisted',
    options
  );

  return backendTrades.map((bt, index) => {
    const quantity = num(bt.quantity);
    const entry = num(bt.entry_price);
    const exit = num(bt.exit_price);
    const pnl = num(bt.realized_pnl);
    const sl = num(bt.stop_loss);
    const tp = num(bt.take_profit);

    let result: 'Win' | 'Loss' | 'Breakeven' = 'Breakeven';

    if (pnl > 0) result = 'Win';
    else if (pnl < 0) result = 'Loss';

    const positionCost = entry * quantity;

    const pnlPercentage =
      positionCost !== 0
        ? (pnl / positionCost) * 100
        : 0;

    const closedAtISO =
      bt.updated_at ||
      bt.created_at ||
      undefined;

    return {
      id:
        bt.order_id ||
        `${bt.symbol}-${closedAtISO || 'unknown'}-${index}`,

      symbol: bt.symbol,
      side: bt.side,

      strategy: (bt.strategy || 'EMA + RSI') as Trade['strategy'],
      timeframe: '5m',

      entry,
      exit,
      sl,
      tp,

      pnl,
      pnlPercentage,

      rr: '-',
      duration: 'Closed',
      result,

      closedAt: closedAtISO
        ? new Date(closedAtISO).toLocaleString()
        : 'Unknown',

      closedAtISO,

      exitReason: bt.exit_reason || undefined,
      diagnosticReason: bt.diagnostic_reason || undefined,
    };
  });
}

export const tradesApi = { getTrades };
