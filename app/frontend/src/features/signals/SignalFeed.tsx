import React from 'react';
import { AlertCircle, Radio, RefreshCw } from 'lucide-react';
import { EmptyState } from '../../components/EmptyState';
import { SignalFeedSkeleton } from '../../components/LoadingSkeleton';
import { StatusBadge } from '../../components/StatusBadge';
import { Signal } from '../../types';
import { formatPrice } from '../../utils/formatters';

export interface SignalFeedProps {
  signals: Signal[];
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string | null;
  isLiveStream?: boolean;
  onRetry?: () => void;
  className?: string;
}

export const SignalFeed: React.FC<SignalFeedProps> = ({
  signals,
  isLoading = false,
  isError = false,
  errorMessage = null,
  isLiveStream = false,
  onRetry,
  className = '',
}) => {
  if (isLoading) return <SignalFeedSkeleton />;

  const recentSignals = signals.slice(0, 50);

  const actionableSignals = recentSignals.filter(
    (signal) => !signal.isExpired && signal.status !== 'Expired' && signal.status !== 'Rejected' && signal.status !== 'Executed'
  );

  const renderCard = (sig: Signal) => (
    <article key={sig.id} id={`card-signal-${sig.id}`} className="rounded-lg border border-slate-800 p-3 font-mono shadow-sm bg-slate-950/60">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-100">{sig.symbol}</span>
            <StatusBadge type="side" value={sig.side} size="xs" />
          </div>
          <div className="mt-1 text-[10px] text-slate-500">{sig.age} &bull; {sig.timestamp}</div>
        </div>
        <StatusBadge type="signal-status" value={sig.status} size="xs" />
      </div>

      <div className="mt-3 flex items-center justify-between text-[11px]">
        <span className="rounded border border-slate-700/60 bg-slate-800/70 px-1.5 py-0.5 text-slate-300">{sig.strategy}</span>
        <span className="text-slate-400">TF {sig.timeframe}</span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
        <div className="rounded bg-slate-900 p-2"><div className="text-slate-500">Entry</div><div className="mt-0.5 font-semibold text-slate-100">{formatPrice(sig.entry)}</div></div>
        <div className="rounded bg-slate-900 p-2"><div className="text-slate-500">SL</div><div className="mt-0.5 font-semibold text-rose-400">{sig.sl ? formatPrice(sig.sl) : '-'}</div></div>
        <div className="rounded bg-slate-900 p-2"><div className="text-slate-500">TP</div><div className="mt-0.5 font-semibold text-emerald-400">{sig.tp ? formatPrice(sig.tp) : '-'}</div></div>
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-slate-800 pt-2 text-[11px] text-slate-400">
        <span>Confidence</span><strong className="text-sky-400">{sig.confidence}%</strong>
      </div>
    </article>
  );

  return (
    <div id="panel-signals" className={`bg-slate-900/80 border border-slate-800 rounded-md overflow-hidden flex flex-col ${className}`}>
      <div className="px-3.5 py-2.5 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Radio size={14} className="text-emerald-400" />
          <h2 id="title-recent-signals" className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono">Actionable Signals</h2>
          {isLiveStream && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/50 text-emerald-300 border border-emerald-800/50 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> WS Live
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {onRetry && (
            <button type="button" onClick={onRetry} disabled={isLoading} className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors disabled:opacity-50" title="Reload signal data">
              <RefreshCw size={11} className={isLoading ? 'animate-spin' : ''} />
            </button>
          )}
          <span className="text-[10px] font-mono text-slate-400 bg-slate-800/60 px-1.5 py-0.5 rounded border border-slate-700/60">{actionableSignals.length} Actionable / {recentSignals.length} Total</span>
        </div>
      </div>

      {isError && errorMessage && (
        <div className="px-3 py-1.5 bg-amber-950/20 border-b border-amber-800/30 flex items-center gap-1.5 text-[11px] font-mono text-amber-300/90">
          <AlertCircle size={12} className="shrink-0 text-amber-400" /><span>{errorMessage}</span>
        </div>
      )}

      {actionableSignals.length === 0 ? (
        <EmptyState
          title={isError ? 'Unable to load signals' : 'No actionable signals right now.'}
          description={isError ? (errorMessage || 'Unable to load signal data.') : 'All previous signals have expired and are hidden from this page. Waiting for new trading opportunities...'}
          icon={isError ? 'alert' : 'inbox'}
          actionLabel={onRetry ? 'Retry Fetch' : undefined}
          onAction={onRetry}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 p-3">
          {actionableSignals.map(s => renderCard(s))}
        </div>
      )}
    </div>
  );
};