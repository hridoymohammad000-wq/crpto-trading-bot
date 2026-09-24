import type { Trade } from '../../types/trade.ts';

export type HistoryPeriod = 'Today' | '7D' | 'Custom';

export interface HistoryRangeOptions {
  period: HistoryPeriod;
  now?: Date;
  fromDate?: string;
  toDate?: string;
}

export function filterTradesByHistoryPeriod(trades: Trade[], options: HistoryRangeOptions): Trade[] {
  const now = options.now ?? new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const endToday = new Date(today);
  endToday.setDate(endToday.getDate() + 1);

  let from: Date | null = null;
  let to: Date | null = null;

  if (options.period === 'Today') {
    from = today;
    to = endToday;
  } else if (options.period === '7D') {
    from = new Date(today);
    from.setDate(from.getDate() - 6);
    to = endToday;
  } else if (options.fromDate && options.toDate) {
    from = new Date(`${options.fromDate}T00:00:00`);
    to = new Date(`${options.toDate}T23:59:59.999`);
  }

  if (!from || !to) return trades;

  return trades.filter((trade) => {
    if (!trade.closedAtISO) return false;
    const closed = new Date(trade.closedAtISO);
    return !Number.isNaN(closed.getTime()) && closed >= from! && closed <= to!;
  });
}
