import React from 'react';
import { ChevronRight, Crosshair, Lock } from 'lucide-react';
import { EmptyState } from '../../components/EmptyState';
import { PositionsTableSkeleton } from '../../components/LoadingSkeleton';
import { StatusBadge } from '../../components/StatusBadge';
import { Position } from '../../types';
import { formatCurrency, formatPercentage, getPnlColor } from '../../utils/formatters';

export interface PositionsTableProps {
  positions: Position[];
  onSelectPosition?: (position: Position) => void;
  isLoading?: boolean;
  isLiveUpdates?: boolean;
  className?: string;
}

export const PositionsTable: React.FC<PositionsTableProps> = ({
  positions,
  onSelectPosition,
  isLoading = false,
  isLiveUpdates = false,
  className = '',
}) => {
  if (isLoading) {
    return <PositionsTableSkeleton />;
  }

  return (
    <div
      id="panel-open-positions"
      className={`bg-slate-900/80 border border-slate-800 rounded-md overflow-hidden flex flex-col ${className}`}
    >
      {/* Panel Header */}
      <div className="px-3.5 py-2.5 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Crosshair size={14} className="text-emerald-400" />
          <h2
            id="title-open-positions"
            className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono"
          >
            Open Positions
          </h2>
          {isLiveUpdates ? (
            <span
              className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/50 text-emerald-300 border border-emerald-800/50 flex items-center gap-1"
              title="Real-time WebSocket position updates active"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              WS Live
            </span>
          ) : (
            <span
              className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-blue-950/40 text-blue-400 border border-blue-800/40"
              title="Real Data: Backend positions endpoint active"
            >
              Real Data
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">

          <span className="text-[10px] font-mono text-slate-400 bg-slate-800/60 px-1.5 py-0.5 rounded border border-slate-700/60">
            {positions.length} Active
          </span>
          <span className="hidden sm:inline-flex items-center gap-1 text-[10px] font-mono text-slate-500">
            <Lock size={10} />
            Click row for details
          </span>
        </div>
      </div>

      {/* Content or Empty State */}
      {positions.length === 0 ? (
        <EmptyState
          title="No open positions"
          description="There are currently no active intraday trading positions managed by the bot."
          icon="inbox"
        />
      ) : (
        <div className="max-w-full overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <caption className="sr-only">Open trading positions</caption>
            <thead>
              <tr className="border-b border-slate-800/80 bg-slate-950/40 text-[11px] text-slate-400 uppercase tracking-wider">
                <th className="py-2 px-3 font-medium">Symbol</th>
                <th className="py-2 px-3 font-medium">Side</th>
                <th className="py-2 px-3 font-medium text-right">Entry</th>
                <th className="py-2 px-3 font-medium text-right">Current</th>
                <th className="py-2 px-3 font-medium text-right">Quantity</th>
                <th className="py-2 px-3 font-medium text-right">Pos Value</th>
                <th className="py-2 px-3 font-medium text-right">SL</th>
                <th className="py-2 px-3 font-medium text-right">TP</th>
                <th className="py-2 px-3 font-medium text-right">Unrealized PnL</th>
                <th className="py-2 px-3 font-medium text-right">PnL %</th>
                <th className="py-2 px-3 font-medium text-right">Current R</th>
                <th className="py-2 px-3 font-medium text-right">Duration</th>
                <th className="py-2 px-2 text-center"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 text-slate-300">
              {positions.map((pos) => {
                const isProfit = pos.unrealizedPnl >= 0;
                const pnlClass = getPnlColor(pos.unrealizedPnl);

                return (
                  <tr
                    key={pos.id}
                    id={`row-position-${pos.id}`}
                    onClick={() => onSelectPosition && onSelectPosition(pos)}
                    className="hover:bg-slate-800/50 transition-colors cursor-pointer group"
                    title="Click to view detailed position metrics"
                  >
                    {/* Symbol */}
                    <td className="py-2.5 px-3 font-bold text-slate-100 whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <span>{pos.symbol}</span>
                        <span className="text-[10px] text-slate-500 font-normal">
                          {pos.leverage}x
                        </span>
                      </div>
                    </td>

                    {/* Side Badge */}
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <StatusBadge type="position" value={pos.side} size="xs" />
                    </td>

                    {/* Entry Price */}
                    <td className="py-2.5 px-3 text-right font-medium text-slate-300 whitespace-nowrap">
                      ${pos.entry.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>

                    {/* Current Price */}
                    <td className="py-2.5 px-3 text-right font-medium text-slate-200 whitespace-nowrap">
                      ${pos.current.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>

                    {/* Quantity */}
                    <td className="py-2.5 px-3 text-right text-slate-400 whitespace-nowrap">
                      {pos.quantity}
                    </td>

                    {/* Position Value */}
                    <td className="py-2.5 px-3 text-right text-slate-300 whitespace-nowrap">
                      ${pos.positionValue.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>

                    {/* Stop Loss */}
                    <td className="py-2.5 px-3 text-right text-rose-400 whitespace-nowrap">
                      ${pos.sl.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>

                    {/* Take Profit */}
                    <td className="py-2.5 px-3 text-right text-emerald-400 whitespace-nowrap">
                      ${pos.tp.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>

                    {/* Unrealized PnL */}
                    <td className={`py-2.5 px-3 text-right font-bold whitespace-nowrap ${pnlClass}`}>
                      {formatCurrency(pos.unrealizedPnl, { showSign: true })}
                    </td>

                    {/* PnL % */}
                    <td className={`py-2.5 px-3 text-right font-semibold whitespace-nowrap ${pnlClass}`}>
                      {formatPercentage(pos.pnlPercentage, { showSign: true })}
                    </td>

                    {/* Current R */}
                    <td
                      className={`py-2.5 px-3 text-right font-bold whitespace-nowrap ${
                        isProfit ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {pos.currentR}
                    </td>

                    {/* Duration */}
                    <td className="py-2.5 px-3 text-right text-slate-400 whitespace-nowrap text-[11px]">
                      {pos.duration}
                    </td>

                    {/* Expand Arrow Indicator */}
                    <td className="py-2.5 px-2 text-center text-slate-600 group-hover:text-emerald-400 transition-colors">
                      <ChevronRight size={14} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
