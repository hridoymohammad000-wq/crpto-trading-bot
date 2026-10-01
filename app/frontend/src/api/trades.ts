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
  mae_price?: number | string | null;
  mfe_price?: number | string | null;
  mae_pct?: number | string | null;
  mfe_pct?: number | string | null;
  mae_r?: number | string | null;
  mfe_r?: number | string | null;
  sl_distance?: number | string | null;
  sl_distance_atr?: number | string | null;
  mae_at?: string | null;
  mfe_at?: string | null;
  root_cause?: string | null;
  root_cause_evidence?: string | null;
  excursion_status?: string | null;
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

      maePrice: num(bt.mae_price, NaN),
      mfePrice: num(bt.mfe_price, NaN),
      maePct: num(bt.mae_pct, NaN),
      mfePct: num(bt.mfe_pct, NaN),
      maeR: num(bt.mae_r, NaN),
      mfeR: num(bt.mfe_r, NaN),
      slDistance: num(bt.sl_distance, NaN),
      slDistanceAtr: num(bt.sl_distance_atr, NaN),
      maeAt: bt.mae_at || undefined,
      mfeAt: bt.mfe_at || undefined,
      rootCause: bt.root_cause || undefined,
      rootCauseEvidence: bt.root_cause_evidence || undefined,
      excursionStatus: bt.excursion_status || undefined,
    };
  });
}

export const tradesApi = { getTrades };
