export interface PerformanceMetrics {
  totalPnl: number;
  dailyPnl: number;
  totalPnlPercentage: number;
  winRate: number;
  profitFactor: number;
  averageRR: string;
  maxDrawdown: number;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  averageWinner: number;
  averageLoser: number;
}

export interface EquityPoint {
  label: string;
  equity: number;
}

export interface DailyPnlPoint {
  label: string;
  pnl: number;
}

export interface PerformanceComparison {
  label: string;
  pnl: number;
  winRate: number;
  trades: number;
}

export interface PerformanceData {
  metrics: PerformanceMetrics;
  equityCurve: EquityPoint[];
  pnlByDay: DailyPnlPoint[];
  strategyComparison: PerformanceComparison[];
  symbolComparison: PerformanceComparison[];
  timeframeComparison: PerformanceComparison[];
}
