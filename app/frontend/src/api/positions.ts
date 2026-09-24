import { Position } from '../types';
import { apiClient } from './client';
import { RequestOptions } from './types';

interface BackendPosition {
  symbol: string;
  side: 'LONG' | 'SHORT';
  size: string | number;
  entry_price: string | number;
  mark_price: string | number;
  position_value: string | number | null;
  leverage: string | number | null;
  unrealized_pnl: string | number | null;
  stop_loss: string | number | null;
  take_profit: string | number | null;
  liquidation_price?: string | number | null;
}

function num(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizePosition(p: BackendPosition): Position {
  const entry = num(p.entry_price);
  const current = num(p.mark_price, entry);
  const quantity = num(p.size);
  const positionValue = num(p.position_value, current * quantity);
  const unrealizedPnl = num(p.unrealized_pnl);
  const sl = num(p.stop_loss);
  const tp = num(p.take_profit);
  const leverage = num(p.leverage, 1);

  const pnlPercentage =
    positionValue !== 0
      ? (unrealizedPnl / positionValue) * 100
      : 0;

  const riskAmount =
    sl > 0
      ? Math.abs(entry - sl) * quantity
      : 0;

  const currentR =
    riskAmount > 0
      ? `${(unrealizedPnl / riskAmount).toFixed(2)}R`
      : '0.00R';

  return {
    id: `${p.symbol}:${p.side}`,
    symbol: p.symbol as Position['symbol'],
    side: p.side,
    entry,
    current,
    quantity,
    positionValue,
    sl,
    tp,
    unrealizedPnl,
    pnlPercentage,
    currentR,
    duration: '—',
    leverage,
    riskAmount,
    openedTime: '—',
  };
}

export async function getPositions(
  options?: RequestOptions
): Promise<Position[]> {
  const rows = await apiClient.get<BackendPosition[]>('/positions', options);
  return rows.map(normalizePosition);
}
