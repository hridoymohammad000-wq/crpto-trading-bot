import React from 'react';
import { AlertTriangle, BarChart3, RefreshCw } from 'lucide-react';
import { DailyPnlPoint, PerformanceComparison, PerformanceData } from '../../types';
import { formatCurrency } from '../../utils/formatters';
import { EquityCurveCard } from './EquityCurveCard';

interface PerformanceAnalyticsProps {
  data: PerformanceData | null;
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
}

interface PanelProps {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  className?: string;
}

const Panel: React.FC<PanelProps> = ({ title, subtitle, children, className = '' }) => (
  <section className={`overflow-hidden rounded-md border border-slate-800 bg-slate-900/80 ${className}`}>
    <div className="border-b border-slate-800 bg-slate-950/80 px-3.5 py-2.5">
      <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-200">{title}</h3>
      <p className="mt-0.5 font-mono text-[10px] text-slate-500">{subtitle}</p>
    </div>
    <div className="p-4">{children}</div>
  </section>
);

const DailyPnlChart: React.FC<{ points: DailyPnlPoint[] }> = ({ points }) => {
  if (points.length === 0) return <EmptyChart label="No daily PnL data available." />;
  const maximum = Math.max(...points.map((point) => Math.abs(point.pnl)), 1);
  return (
    <div className="overflow-x-auto pb-1">
      <div className="flex h-52 min-w-130 items-stretch gap-2" role="img" aria-label="Profit and loss by day">
        {points.map((point) => {
          const height = Math.max((Math.abs(point.pnl) / maximum) * 82, point.pnl === 0 ? 2 : 8);
          return (
            <div key={point.label} className="flex min-w-14 flex-1 flex-col items-center">
              <span className={`mb-1 h-5 font-mono text-[10px] ${point.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {formatCurrency(point.pnl, { showSign: true })}
              </span>
              <div className="relative flex w-full flex-1 flex-col">
                <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-slate-700" />
                <div className="flex h-1/2 items-end justify-center">
                  {point.pnl >= 0 && <div className="w-7 rounded-t bg-emerald-500/80" style={{ height: `${height}%` }} />}
                </div>
                <div className="flex h-1/2 items-start justify-center">
                  {point.pnl < 0 && <div className="w-7 rounded-b bg-rose-500/80" style={{ height: `${height}%` }} />}
                </div>
              </div>
              <span className="mt-1 font-mono text-[10px] text-slate-500">{point.label.replace('Sep ', '')}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const EmptyChart: React.FC<{ label: string }> = ({ label }) => (
  <div className="flex min-h-36 items-center justify-center rounded border border-dashed border-slate-700 bg-slate-950/40 font-mono text-xs text-slate-500">
    {label}
  </div>
);

const ComparisonPanel: React.FC<{ title: string; items: PerformanceComparison[] }> = ({ title, items }) => {
  const maximum = Math.max(...items.map((item) => Math.abs(item.pnl)), 1);
  return (
    <Panel title={title} subtitle="PnL, win rate, and closed trades">
      {items.length === 0 ? (
        <EmptyChart label={`No ${title.toLowerCase()} data available.`} />
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <div key={item.label} className="font-mono">
              <div className="mb-1.5 flex items-center justify-between gap-3 text-xs">
                <span className="truncate font-semibold text-slate-200">{item.label}</span>
                <span className={item.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}>{formatCurrency(item.pnl, { showSign: true })}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                <div className={`h-full rounded-full ${item.pnl >= 0 ? 'bg-emerald-500' : 'bg-rose-500'}`} style={{ width: `${Math.max((Math.abs(item.pnl) / maximum) * 100, 3)}%` }} />
              </div>
              <div className="mt-1.5 flex justify-between text-[10px] text-slate-500">
                <span>{item.winRate.toFixed(1)}% win rate</span>
                <span>{item.trades} trades</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
};

const WinLossChart: React.FC<{ wins: number; losses: number }> = ({ wins, losses }) => {
  const total = wins + losses;
  if (total === 0) return <EmptyChart label="No closed trades available." />;
  const winShare = (wins / total) * 100;
  return (
    <div className="flex min-h-44 flex-col items-center justify-center gap-5 sm:flex-row">
      <div
        className="relative h-32 w-32 shrink-0 rounded-full"
        style={{ background: `conic-gradient(#10b981 0 ${winShare}%, #f43f5e ${winShare}% 100%)` }}
        role="img"
        aria-label={`${wins} winning trades and ${losses} losing trades`}
      >
        <div className="absolute inset-5 flex flex-col items-center justify-center rounded-full bg-slate-950 font-mono">
          <span className="text-xl font-bold text-slate-100">{total}</span>
          <span className="text-[9px] uppercase text-slate-500">Trades</span>
        </div>
      </div>
      <div className="w-full max-w-44 space-y-3 font-mono text-xs">
        <div className="flex items-center justify-between gap-4"><span className="flex items-center gap-2 text-slate-400"><span className="h-2 w-2 rounded-full bg-emerald-500" />Wins</span><strong className="text-emerald-400">{wins}</strong></div>
        <div className="flex items-center justify-between gap-4"><span className="flex items-center gap-2 text-slate-400"><span className="h-2 w-2 rounded-full bg-rose-500" />Losses</span><strong className="text-rose-400">{losses}</strong></div>
      </div>
    </div>
  );
};

export const PerformanceAnalytics: React.FC<PerformanceAnalyticsProps> = ({
  data,
  isLoading = false,
  isError = false,
  errorMessage = null,
  onRetry,
}) => {
  if (isLoading) {
    return (
      <div className="grid animate-pulse grid-cols-1 gap-4 lg:grid-cols-2">
        {[0, 1, 2, 3].map((item) => <div key={item} className="h-64 rounded-md border border-slate-800 bg-slate-900/80" />)}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex min-h-56 flex-col items-center justify-center gap-3 rounded-md border border-amber-800/40 bg-amber-950/20 p-6 text-center font-mono">
        <AlertTriangle size={22} className="text-amber-400" />
        <p className="text-sm text-amber-200">{errorMessage ?? 'No performance dataset is available.'}</p>
        {onRetry && <button type="button" onClick={onRetry} className="inline-flex items-center gap-2 rounded border border-amber-700 px-3 py-2 text-xs text-amber-300 hover:bg-amber-950/50"><RefreshCw size={13} />Reload local data</button>}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <EquityCurveCard points={data.equityCurve} metrics={data.metrics} className="xl:col-span-3" />
        <Panel title="PnL by Day" subtitle="Daily realized result • local dataset" className="xl:col-span-2">
          <DailyPnlChart points={data.pnlByDay} />
        </Panel>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Panel title="Win / Loss Distribution" subtitle="Closed trades by outcome">
          <WinLossChart wins={data.metrics.winningTrades} losses={data.metrics.losingTrades} />
        </Panel>
        <ComparisonPanel title="Strategy Comparison" items={data.strategyComparison} />
        <ComparisonPanel title="Symbol Comparison" items={data.symbolComparison} />
        <ComparisonPanel title="Timeframe Comparison" items={data.timeframeComparison} />
      </div>
      <div className="flex items-center gap-2 rounded border border-slate-800 bg-slate-900/50 px-3 py-2 font-mono text-[10px] text-slate-500">
        <BarChart3 size={12} className="text-emerald-400" />
        Structured frontend analytics. No live strategy calculations or exchange access.
      </div>
    </div>
  );
};
