import React, { useMemo } from 'react';
import { LineChart, TrendingDown, TrendingUp } from 'lucide-react';
import { EquityPoint, PerformanceMetrics } from '../../types';
import { formatCurrency, formatPercentage } from '../../utils/formatters';

export interface EquityCurveCardProps {
  points?: EquityPoint[];
  metrics?: PerformanceMetrics;
  isLoading?: boolean;
  className?: string;
}

function buildLine(points: EquityPoint[]): string {
  if (points.length === 0) return '';
  const equities = points.map((point) => point.equity);
  const minimum = Math.min(...equities);
  const maximum = Math.max(...equities);
  const range = Math.max(maximum - minimum, 1);
  return points
    .map((point, index) => {
      const x = points.length === 1 ? 320 : (index / (points.length - 1)) * 620 + 10;
      const y = 180 - ((point.equity - minimum) / range) * 155;
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
}

export const EquityCurveCard: React.FC<EquityCurveCardProps> = ({
  points,
  metrics,
  isLoading = false,
  className = '',
}) => {
  const resolvedPoints = points ?? [];
  const linePath = useMemo(() => buildLine(resolvedPoints), [resolvedPoints]);
  const isPositive = (metrics?.totalPnl ?? 0) >= 0;
  const finalPoint = resolvedPoints.at(-1);

  if (isLoading) {
    return (
      <div className={`animate-pulse overflow-hidden rounded-md border border-slate-800 bg-slate-900/80 ${className}`}>
        <div className="h-10 border-b border-slate-800 bg-slate-950/80" />
        <div className="space-y-3 p-4"><div className="h-7 w-36 rounded bg-slate-800" /><div className="h-48 rounded bg-slate-950/60" /></div>
      </div>
    );
  }

  return (
    <section id="panel-equity-curve" className={`flex flex-col overflow-hidden rounded-md border border-slate-800 bg-slate-900/80 ${className}`}>
      <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950/80 px-3.5 py-2.5">
        <div className="flex items-center gap-2">
          <LineChart size={14} className="text-emerald-400" />
          <h2 className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-200">Equity Curve</h2>
        </div>
        <span className="font-mono text-[10px] text-slate-500">7-day session window</span>
      </div>

      <div className="flex flex-1 flex-col p-3 sm:p-4">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2 font-mono">
          <div>
            <div className="text-xl font-bold tracking-tight text-slate-100 sm:text-2xl">
              {finalPoint ? formatCurrency(finalPoint.equity) : <span className="text-slate-500 text-sm">No data</span>}
            </div>
            <div className={`mt-0.5 flex items-center gap-1.5 text-xs font-medium ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isPositive ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
              <span>{metrics ? `${formatCurrency(metrics.totalPnl, { showSign: true })} (${formatPercentage(metrics.totalPnlPercentage, { showSign: true })})` : '—'}</span>
            </div>
          </div>
          <div className="text-right text-[11px] text-slate-400">
            <div>Trades: <span className="text-slate-200">{metrics?.totalTrades ?? '—'}</span></div>
            <div>Max DD: <span className="text-rose-400">{metrics != null ? `-${metrics.maxDrawdown}%` : '—'}</span></div>
          </div>
        </div>

        {resolvedPoints.length === 0 ? (
          <div className="flex min-h-48 items-center justify-center rounded border border-dashed border-slate-700 bg-slate-950/50 font-mono text-xs text-slate-500">
            No equity data available.
          </div>
        ) : (
          <div className="relative min-h-48 flex-1 overflow-hidden rounded border border-slate-800/80 bg-slate-950/60">
            <div className="pointer-events-none absolute inset-0 opacity-15" style={{ backgroundImage: 'linear-gradient(to right, #334155 1px, transparent 1px), linear-gradient(to bottom, #334155 1px, transparent 1px)', backgroundSize: '80px 40px' }} />
            <svg className="h-48 w-full" viewBox="0 0 640 200" preserveAspectRatio="none" role="img" aria-label={`Equity from ${resolvedPoints[0]?.equity ?? 0} to ${finalPoint?.equity ?? 0}`}>
              <defs>
                <linearGradient id="equity-area-gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d={`${linePath} L 630 190 L 10 190 Z`} fill="url(#equity-area-gradient)" />
              <path d={linePath} fill="none" stroke="#34d399" strokeWidth="3" vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        )}

        <div className="mt-2 flex justify-between gap-2 overflow-hidden px-1 font-mono text-[10px] text-slate-500">
          {resolvedPoints.map((point, index) => (
            <span key={`${point.label}-${index}`} className={index > 0 && index < resolvedPoints.length - 1 ? 'hidden sm:inline' : ''}>{point.label}</span>
          ))}
        </div>
      </div>
    </section>
  );
};
