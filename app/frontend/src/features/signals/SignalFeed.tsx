import React from 'react';
import { AlertTriangle, Radio, RefreshCw } from 'lucide-react';
import { EmptyState } from '../../components/EmptyState';
import { SignalFeedSkeleton } from '../../components/LoadingSkeleton';
import { StatusBadge } from '../../components/StatusBadge';
import { Signal } from '../../types';

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
  if (isLoading) {
    return <SignalFeedSkeleton />;
  }

  return (
    <div
      id="panel-signals"
      className={`bg-slate-900/80 border border-slate-800 rounded-md overflow-hidden flex flex-col ${className}`}
    >
      {/* Panel Header */}
      <div className="px-3.5 py-2.5 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Radio size={14} className="text-emerald-400" />
          <h2
            id="title-recent-signals"
            className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono"
          >
            Recent Signals
          </h2>
          {isLiveStream && (
            <span
              className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/50 text-emerald-300 border border-emerald-800/50 flex items-center gap-1"
              title="Real-time WebSocket signal streaming active"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              WS Live
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {onRetry && (
            <button
              type="button"
              id="btn-retry-signals"
              onClick={onRetry}
              disabled={isLoading}
              className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors disabled:opacity-50"
              title="Reload local signal data"
              aria-label="Reload local signal data"
            >
              <RefreshCw size={11} className={isLoading ? 'animate-spin' : ''} />
            </button>
          )}
          <span className="text-[10px] font-mono text-slate-400 bg-slate-800/60 px-1.5 py-0.5 rounded border border-slate-700/60">
            {signals.length} Signals
          </span>
        </div>
      </div>

      {/* Non-fatal error notification strip if fallback is displayed */}
      {isError && errorMessage && (
        <div className="px-3 py-1.5 bg-amber-950/20 border-b border-amber-800/30 flex items-center justify-between text-[11px] font-mono text-amber-300/90 gap-2">
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

      {/* Signals Content or Empty State */}
      {signals.length === 0 ? (
        <EmptyState
          title={isError ? 'Unable to load signals' : 'No recent signals'}
          description={
            isError
              ? (errorMessage || 'Unable to load local signal data.')
              : 'The algorithmic scanners have not triggered any valid trade entries for the selected parameters.'
          }
          icon={isError ? 'alert' : 'inbox'}
          actionLabel={onRetry ? 'Retry Fetch' : undefined}
          onAction={onRetry}
        />
      ) : (
        <div className="max-w-full overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <caption className="sr-only">Recent trading signals</caption>
            <thead>
              <tr className="border-b border-slate-800/80 bg-slate-950/40 text-[11px] text-slate-400 uppercase tracking-wider">
                <th className="py-2 px-3 font-medium">Age / Time</th>
                <th className="py-2 px-3 font-medium">Symbol</th>
                <th className="py-2 px-3 font-medium">Side</th>
                <th className="py-2 px-3 font-medium">Strategy</th>
                <th className="py-2 px-3 font-medium">TF</th>
                <th className="py-2 px-3 font-medium text-right">Entry</th>
                <th className="py-2 px-3 font-medium text-right">SL</th>
                <th className="py-2 px-3 font-medium text-right">TP</th>
                <th className="py-2 px-3 font-medium text-right">Conf</th>
                <th className="py-2 px-3 font-medium text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 text-slate-300">
              {signals.map((sig) => (
                <tr
                  key={sig.id}
                  id={`row-signal-${sig.id}`}
                  className="hover:bg-slate-800/40 transition-colors"
                >
                  <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                    <div className="text-slate-300 font-medium">{sig.age}</div>
                    <div className="text-[10px] text-slate-500">{sig.timestamp}</div>
                  </td>
                  <td className="py-2.5 px-3 font-bold text-slate-100 whitespace-nowrap">
                    {sig.symbol}
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <StatusBadge type="side" value={sig.side} size="xs" />
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <span className="px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/50 text-[11px]">
                      {sig.strategy}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                    {sig.timeframe}
                  </td>
                  <td className="py-2.5 px-3 text-right font-medium text-slate-200 whitespace-nowrap">
                    ${sig.entry.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-right text-rose-400 whitespace-nowrap">
                    ${sig.sl.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-right text-emerald-400 whitespace-nowrap">
                    ${sig.tp.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-right font-semibold text-sky-400 whitespace-nowrap">
                    {sig.confidence}%
                  </td>
                  <td className="py-2.5 px-3 text-center whitespace-nowrap">
                    <StatusBadge type="signal-status" value={sig.status} size="xs" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
