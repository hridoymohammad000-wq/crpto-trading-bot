import React from 'react';
import {
  Activity,
  AlertTriangle,
  Award,
  BarChart3,
  Percent,
  RefreshCw,
  ShieldCheck,
  Target,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { PerformanceMetrics } from '../types';
import { formatCurrency, formatPercentage } from '../utils/formatters';
import { PerformanceCardsSkeleton } from './LoadingSkeleton';
import { MetricCard } from './MetricCard';

export interface PerformanceCardsProps {
  metrics: PerformanceMetrics;
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
  className?: string;
  showSectionHeader?: boolean;
}

export const PerformanceCards: React.FC<PerformanceCardsProps> = ({
  metrics,
  isLoading = false,
  isError = false,
  errorMessage = null,
  onRetry,
  className = '',
  showSectionHeader = true,
}) => {
  if (isLoading) {
    return <PerformanceCardsSkeleton />;
  }

  const isPnlPositive = metrics.totalPnl >= 0;

  return (
    <div id="section-performance-summary" className={`space-y-2 ${className}`}>
      {showSectionHeader && (
        <div className="flex items-center justify-between px-1 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Activity size={14} className="text-emerald-400" />
            <h2
              id="title-performance-summary"
              className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono"
            >
              Performance Metrics
            </h2>
          </div>
          <div className="flex items-center gap-2">
            {onRetry && (
              <button
                type="button"
                id="btn-retry-performance"
                onClick={onRetry}
                disabled={isLoading}
                className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors disabled:opacity-50"
                title="Reload local performance data"
                aria-label="Reload local performance data"
              >
                <RefreshCw size={11} className={isLoading ? 'animate-spin' : ''} />
              </button>
            )}
            <span className="text-[10px] font-mono text-slate-500">
              Rolling Session Statistics
            </span>
          </div>
        </div>
      )}

      {/* Non-fatal error notification strip if fallback is displayed */}
      {isError && errorMessage && (
        <div className="px-3 py-1.5 bg-amber-950/20 border border-amber-800/30 rounded text-[11px] font-mono text-amber-300/90 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 truncate">
            <AlertTriangle size={12} className="shrink-0 text-amber-400" />
            <span className="truncate">{errorMessage}</span>
          </div>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="shrink-0 text-[10px] text-amber-400 hover:text-amber-200 underline"
            >
              Retry
            </button>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-2 font-mono">
        {/* Total PnL */}
        <MetricCard
          id="metric-total-pnl"
          label="Total PnL"
          value={formatCurrency(metrics.totalPnl, { showSign: true })}
          change={formatPercentage(metrics.totalPnlPercentage, { showSign: true })}
          changeType={isPnlPositive ? 'positive' : 'negative'}
          icon={<TrendingUp size={14} />}
        />

        <MetricCard
          id="metric-daily-pnl"
          label="Daily PnL"
          value={formatCurrency(metrics.dailyPnl, { showSign: true })}
          change="Current session"
          changeType={metrics.dailyPnl >= 0 ? 'positive' : 'negative'}
          icon={metrics.dailyPnl >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
        />

        {/* Win Rate */}
        <MetricCard
          id="metric-win-rate"
          label="Win Rate"
          value={`${metrics.winRate}%`}
          change={`${metrics.winningTrades}W / ${metrics.losingTrades}L`}
          changeType="neutral"
          icon={<Percent size={14} />}
        />

        {/* Profit Factor */}
        <MetricCard
          id="metric-profit-factor"
          label="Profit Factor"
          value={metrics.profitFactor.toFixed(2)}
          change="Target: > 1.80"
          changeType="positive"
          icon={<Award size={14} />}
        />

        {/* Average R:R */}
        <MetricCard
          id="metric-avg-rr"
          label="Average R:R"
          value={metrics.averageRR}
          change="Exp: +1.11R"
          changeType="positive"
          icon={<Target size={14} />}
        />

        {/* Max Drawdown */}
        <MetricCard
          id="metric-max-drawdown"
          label="Max Drawdown"
          value={`${metrics.maxDrawdown}%`}
          change="Ceiling: 6.00%"
          changeType="neutral"
          icon={<ShieldCheck size={14} />}
        />

        {/* Total Trades */}
        <MetricCard
          id="metric-total-trades"
          label="Total Trades"
          value={metrics.totalTrades.toString()}
          change={`${metrics.totalTrades} closed`}
          changeType="neutral"
          icon={<BarChart3 size={14} />}
        />

        {/* Winning Trades */}
        <MetricCard
          id="metric-winning-trades"
          label="Winning Trades"
          value={metrics.winningTrades.toString()}
          change={`${metrics.totalTrades > 0 ? ((metrics.winningTrades / metrics.totalTrades) * 100).toFixed(1) : 0}% share`}
          changeType="positive"
          icon={<TrendingUp size={14} />}
        />

        {/* Losing Trades */}
        <MetricCard
          id="metric-losing-trades"
          label="Losing Trades"
          value={metrics.losingTrades.toString()}
          change={`${metrics.totalTrades > 0 ? ((metrics.losingTrades / metrics.totalTrades) * 100).toFixed(1) : 0}% share`}
          changeType="negative"
          icon={<TrendingDown size={14} />}
        />

      </div>
    </div>
  );
};
