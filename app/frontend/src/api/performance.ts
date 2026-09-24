import { PerformanceData, PerformanceMetrics, EquityPoint, DailyPnlPoint, PerformanceComparison } from '../types';
import { apiClient } from './client';

interface BackendTrade {
  symbol: string;
  side: string;
  quantity: number | string;
  entry_price?: number | string;
  exit_price?: number | string;
  realized_pnl: number | string;
  created_at?: string;
}

interface BackendStats {
  total_trades: number | string;
  winning_trades: number | string;
  losing_trades: number | string;
  breakeven_trades: number | string;
  win_rate_pct: number | string;
  total_realized_pnl: number | string;
  gross_profit: number | string;
  gross_loss: number | string;
  average_pnl: number | string;
  profit_factor?: number | string | null;
}

/**
 * Fetch real performance stats from backend.
 */
export async function getPerformance(): Promise<PerformanceData> {
  const [stats, trades] = await Promise.all([
    apiClient.get<BackendStats>('/trades/stats/persisted'),
    apiClient.get<BackendTrade[]>('/trades/persisted?limit=500')
  ]);

  const winningTrades = Number(stats.winning_trades || 0);
  const losingTrades = Number(stats.losing_trades || 0);
  const grossProfit = Number(stats.gross_profit || 0);
  const grossLoss = Number(stats.gross_loss || 0);

  const metrics: PerformanceMetrics = {
    totalPnl: Number(stats.total_realized_pnl || 0),
    dailyPnl: 0, // Fallback, no easy way without filtering by today
    totalPnlPercentage: 0,
    winRate: Number(stats.win_rate_pct || 0),
    profitFactor: Number(stats.profit_factor ?? 0),
    averageRR: '-',
    maxDrawdown: 0,
    totalTrades: Number(stats.total_trades || 0),
    winningTrades,
    losingTrades,
    averageWinner: winningTrades > 0 ? grossProfit / winningTrades : 0,
    averageLoser: losingTrades > 0 ? grossLoss / losingTrades : 0,
  };

  const equityCurve: EquityPoint[] = [];
  const pnlByDayMap = new Map<string, number>();

  let cumulativeEquity = 10000; // Starting with a base line for equity curve
  
  const sortedTrades = [...trades].sort((a, b) => {
    return new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
  });

  for (const t of sortedTrades) {
    const pnl = Number(t.realized_pnl || 0);
    cumulativeEquity += pnl;
    const dateStr = t.created_at ? new Date(t.created_at).toLocaleDateString('en-US', { month: 'short', day: '2-digit' }) : 'Unknown';
    equityCurve.push({ label: dateStr, equity: cumulativeEquity });

    pnlByDayMap.set(dateStr, (pnlByDayMap.get(dateStr) || 0) + pnl);
  }

  const pnlByDay: DailyPnlPoint[] = Array.from(pnlByDayMap.entries()).map(([label, pnl]) => ({ label, pnl }));

  // For the comparisons, let's just create some based on symbols
  const symbolMap = new Map<string, { pnl: number, wins: number, trades: number }>();
  for (const t of trades) {
    const sym = t.symbol;
    const pnl = Number(t.realized_pnl || 0);
    if (!symbolMap.has(sym)) {
      symbolMap.set(sym, { pnl: 0, wins: 0, trades: 0 });
    }
    const data = symbolMap.get(sym)!;
    data.pnl += pnl;
    data.trades += 1;
    if (pnl > 0) data.wins += 1;
  }
  
  const symbolComparison: PerformanceComparison[] = Array.from(symbolMap.entries()).map(([sym, data]) => ({
    label: sym,
    pnl: data.pnl,
    winRate: data.trades > 0 ? (data.wins / data.trades) * 100 : 0,
    trades: data.trades
  }));

  return {
    metrics,
    equityCurve,
    pnlByDay,
    strategyComparison: [],
    symbolComparison,
    timeframeComparison: []
  };
}

export const performanceApi = {
  getPerformance,
};
