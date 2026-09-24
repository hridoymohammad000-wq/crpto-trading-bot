import { AlertCircle, Clock3, RefreshCw } from 'lucide-react';
import type { StrategyDiagnostic, StrategyIndicators } from '../../types';
import { useStrategyMonitor } from '../../hooks/useStrategyMonitor';
import { STRATEGY_SYMBOLS, type StrategyMonitorItem } from './monitorState';

const numberFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 });
const volumeFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const dateFormatter = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

export function StrategyMonitor() {
  const { items, isRefreshing, refresh, pollIntervalMs } = useStrategyMonitor();

  return (
    <section aria-labelledby="strategy-monitor-title" className="space-y-4">
      <div className="flex flex-col gap-3 border-b border-slate-800 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="strategy-monitor-title" className="font-mono text-base font-semibold text-slate-100">
              Live Strategy Monitor
            </h2>
            <span className="rounded border border-emerald-800/60 bg-emerald-950/50 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
              Real Backend Data
            </span>
          </div>
          <p className="mt-1 max-w-3xl font-mono text-xs text-slate-400">
            Read-only EMA_RSI_ADX_MOMENTUM diagnostics using closed 5m candles and 15m confirmation.
            Monitoring does not depend on bot state and never submits orders.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={isRefreshing}
          aria-label="Refresh all strategy evaluations"
          className="inline-flex min-h-9 items-center justify-center gap-2 self-start rounded border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-200 transition-colors hover:border-emerald-700 hover:text-emerald-300 disabled:cursor-not-allowed disabled:opacity-50 sm:self-auto"
        >
          <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
          {isRefreshing ? 'Refreshing…' : 'Refresh now'}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded border border-slate-800/80 bg-slate-900/40 px-3 py-2 font-mono text-[11px] text-slate-400">
        <span className="inline-flex items-center gap-1.5">
          <Clock3 size={12} /> Polling every {pollIntervalMs / 1000} seconds
        </span>
        <span>Symbols: BTCUSDT · ETHUSDT · SOLUSDT</span>
        <span>No trading loop</span>
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-3">
        {STRATEGY_SYMBOLS.map((symbol) => (
          <StrategyCard key={symbol} symbol={symbol} item={items[symbol]} />
        ))}
      </div>
    </section>
  );
}

function StrategyCard({ symbol, item }: { symbol: string; item: StrategyMonitorItem }) {
  if (item.isLoading && item.data === null) {
    return <StrategyCardSkeleton symbol={symbol} />;
  }

  return (
    <article className="min-w-0 overflow-hidden rounded-md border border-slate-800 bg-slate-900/80 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 bg-slate-950/80 px-3.5 py-3">
        <div>
          <h3 className="font-mono text-sm font-bold text-slate-100">{symbol}</h3>
          <p className="font-mono text-[10px] text-slate-500">5m entry · 15m trend</p>
        </div>
        {item.data ? <ResultBadges diagnostic={item.data} /> : null}
      </div>

      {item.errorMessage ? (
        <div role="alert" className="flex gap-2 border-b border-rose-800/50 bg-rose-950/30 px-3 py-2 font-mono text-[11px] text-rose-300">
          <AlertCircle size={13} className="mt-0.5 shrink-0" />
          <span>
            {item.errorMessage}
            {item.data ? ' Showing the last successful evaluation.' : ''}
          </span>
        </div>
      ) : null}

      {item.data ? (
        <DiagnosticDetails diagnostic={item.data} lastSuccessfulAt={item.lastSuccessfulAt} />
      ) : (
        <div className="p-5 text-center font-mono text-xs text-slate-400">
          No successful evaluation is available for this symbol.
        </div>
      )}
    </article>
  );
}

function ResultBadges({ diagnostic }: { diagnostic: StrategyDiagnostic }) {
  const isSignal = diagnostic.result === 'SIGNAL';
  return (
    <div className="flex items-center gap-1.5" aria-label={`Result: ${diagnostic.result}`}>
      <span
        className={`rounded border px-2 py-1 font-mono text-[10px] font-bold ${
          isSignal
            ? 'border-emerald-700/60 bg-emerald-950/60 text-emerald-300'
            : 'border-amber-800/50 bg-amber-950/40 text-amber-300'
        }`}
      >
        {isSignal ? 'SIGNAL' : 'NO SIGNAL'}
      </span>
      {diagnostic.side ? (
        <span className="rounded border border-emerald-700/60 bg-emerald-950/60 px-2 py-1 font-mono text-[10px] font-bold text-emerald-300">
          {diagnostic.side}
        </span>
      ) : null}
    </div>
  );
}

function DiagnosticDetails({
  diagnostic,
  lastSuccessfulAt,
}: {
  diagnostic: StrategyDiagnostic;
  lastSuccessfulAt: string | null;
}) {
  const trend = trendAlignment(diagnostic.indicators);
  const slope = slopeState(diagnostic.indicators);
  return (
    <div className="space-y-3 p-3.5">
      {diagnostic.result === 'SIGNAL' ? (
        <div className="grid grid-cols-2 gap-2 rounded border border-emerald-800/40 bg-emerald-950/20 p-2.5 font-mono text-xs">
          <Metric label="Confidence" value={`${diagnostic.confidence ?? '—'}%`} accent="text-emerald-300" />
          <Metric label="Reference price" value={formatNumber(diagnostic.referenceEntryPrice)} accent="text-emerald-300" />
        </div>
      ) : (
        <div>
          <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wide text-slate-500">Filter state</p>
          <div className="flex flex-wrap gap-1.5">
            {diagnostic.reasonCodes.length > 0 ? diagnostic.reasonCodes.map((reason) => (
              <span key={reason} className="rounded border border-amber-800/40 bg-amber-950/30 px-2 py-1 font-mono text-[10px] text-amber-300">
                {reason.replaceAll('_', ' ')}
              </span>
            )) : (
              <span className="font-mono text-[11px] text-slate-500">No reason codes returned</span>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-x-4 gap-y-2 border-y border-slate-800/80 py-3 sm:grid-cols-3 xl:grid-cols-2 2xl:grid-cols-3">
        <Metric label="EMA9" value={formatNumber(diagnostic.indicators.emaFast)} />
        <Metric label="EMA21" value={formatNumber(diagnostic.indicators.emaSlow)} />
        <Metric label="RSI14" value={formatNumber(diagnostic.indicators.rsi)} />
        <Metric label="ADX14" value={formatNumber(diagnostic.indicators.adx)} />
        <Metric label="Volume" value={formatVolume(diagnostic.indicators.volume)} />
        <Metric label="Avg volume (20)" value={formatVolume(diagnostic.indicators.averageVolume)} />
      </div>

      <div className="space-y-2 font-mono text-[11px]">
        <StateRow label="15m trend alignment" value={trend.label} tone={trend.tone} />
        <StateRow label="15m EMA9 slope" value={slope.label} tone={slope.tone} />
        <StateRow
          label="Crossover age"
          value={diagnostic.crossoverAgeCandles === null ? 'None' : `${diagnostic.crossoverAgeCandles} candle${diagnostic.crossoverAgeCandles === 1 ? '' : 's'}`}
          tone="neutral"
        />
        <StateRow
          label="Duplicate setup"
          value={diagnostic.duplicateSetup ? 'Yes' : 'No'}
          tone={diagnostic.duplicateSetup ? 'amber' : 'neutral'}
        />
      </div>

      <dl className="space-y-1 border-t border-slate-800/80 pt-3 font-mono text-[10px] text-slate-500">
        <TimeRow label="Latest closed 5m" value={diagnostic.latest5mCandleTime} />
        <TimeRow label="Latest closed 15m" value={diagnostic.latest15mCandleTime} />
        <TimeRow label="Engine evaluation" value={diagnostic.evaluationTime} />
        <TimeRow label="Last successful fetch" value={lastSuccessfulAt} />
      </dl>
    </div>
  );
}

function Metric({ label, value, accent = 'text-slate-200' }: { label: string; value: string; accent?: string }) {
  return (
    <div className="min-w-0">
      <dt className="truncate font-mono text-[10px] uppercase text-slate-500">{label}</dt>
      <dd className={`truncate font-mono text-xs font-semibold ${accent}`} title={value}>{value}</dd>
    </div>
  );
}

function StateRow({ label, value, tone }: { label: string; value: string; tone: 'green' | 'amber' | 'neutral' }) {
  const color = tone === 'green' ? 'text-emerald-300' : tone === 'amber' ? 'text-amber-300' : 'text-slate-300';
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className={`text-right ${color}`}>{value}</span>
    </div>
  );
}

function TimeRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex flex-col justify-between gap-0.5 sm:flex-row sm:gap-3 xl:flex-col 2xl:flex-row">
      <dt>{label}</dt>
      <dd className="text-slate-300" title={value ?? undefined}>{formatTime(value)}</dd>
    </div>
  );
}

function StrategyCardSkeleton({ symbol }: { symbol: string }) {
  return (
    <article aria-label={`Loading ${symbol} strategy evaluation`} className="animate-pulse overflow-hidden rounded-md border border-slate-800 bg-slate-900/80">
      <div className="border-b border-slate-800 bg-slate-950/80 px-3.5 py-3">
        <div className="font-mono text-sm font-bold text-slate-300">{symbol}</div>
      </div>
      <div className="space-y-3 p-3.5">
        <div className="h-8 rounded bg-slate-800/80" />
        <div className="grid grid-cols-2 gap-2">
          {Array.from({ length: 6 }).map((_, index) => <div key={index} className="h-9 rounded bg-slate-800/60" />)}
        </div>
        <div className="h-20 rounded bg-slate-800/50" />
      </div>
    </article>
  );
}

function trendAlignment(indicators: StrategyIndicators): { label: string; tone: 'green' | 'amber' | 'neutral' } {
  if (indicators.higherTfEmaFast === null || indicators.higherTfEmaSlow === null) return { label: 'Unavailable', tone: 'neutral' };
  if (indicators.higherTfEmaFast > indicators.higherTfEmaSlow) return { label: 'Bullish · EMA9 > EMA21', tone: 'green' };
  if (indicators.higherTfEmaFast < indicators.higherTfEmaSlow) return { label: 'Bearish · EMA9 < EMA21', tone: 'amber' };
  return { label: 'Flat', tone: 'neutral' };
}

function slopeState(indicators: StrategyIndicators): { label: string; tone: 'green' | 'amber' | 'neutral' } {
  const current = indicators.higherTfEmaFast;
  const previous = indicators.higherTfEmaFastPrevious;
  if (current === null || previous === null) return { label: 'Unavailable', tone: 'neutral' };
  if (current > previous) return { label: 'Rising', tone: 'green' };
  if (current < previous) return { label: 'Falling', tone: 'amber' };
  return { label: 'Flat', tone: 'neutral' };
}

function formatNumber(value: number | null): string {
  return value === null ? '—' : numberFormatter.format(value);
}

function formatVolume(value: number | null): string {
  return value === null ? '—' : volumeFormatter.format(value);
}

function formatTime(value: string | null): string {
  return value === null ? 'Unavailable' : dateFormatter.format(new Date(value));
}
