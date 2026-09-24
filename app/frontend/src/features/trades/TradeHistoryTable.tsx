import React from 'react';
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Filter,
  History,
  RefreshCw,
  RotateCcw,
} from 'lucide-react';
import { EmptyState } from '../../components/EmptyState';
import { TradeHistorySkeleton } from '../../components/LoadingSkeleton';
import { StatusBadge } from '../../components/StatusBadge';
import {
  TradeResultFilter,
  TradeStrategyFilter,
  TradeSymbolFilter,
  useTradeFilters,
} from '../../hooks/useTradeFilters';
import { Trade } from '../../types';
import { formatCurrency, formatPercentage } from '../../utils/formatters';

export interface TradeHistoryTableProps {
  trades: Trade[];
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string | null;
  onRetry?: () => void;
  className?: string;
  // Controlled filters (optional)
  filterResult?: TradeResultFilter;
  onFilterResultChange?: (filter: TradeResultFilter) => void;
  filterSymbol?: TradeSymbolFilter;
  onFilterSymbolChange?: (filter: TradeSymbolFilter) => void;
  filterStrategy?: TradeStrategyFilter;
  onFilterStrategyChange?: (filter: TradeStrategyFilter) => void;
  onResetFilters?: () => void;
  hasActiveFilters?: boolean;
  // Controlled pagination (optional)
  page?: number;
  totalPages?: number;
  totalCount?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
}

export const TradeHistoryTable: React.FC<TradeHistoryTableProps> = ({
  trades,
  isLoading = false,
  isError = false,
  errorMessage = null,
  onRetry,
  className = '',
  filterResult: controlledResult,
  onFilterResultChange,
  filterSymbol: controlledSymbol,
  onFilterSymbolChange,
  filterStrategy: controlledStrategy,
  onFilterStrategyChange,
  onResetFilters: controlledResetFilters,
  hasActiveFilters: controlledHasActiveFilters,
  page = 1,
  totalPages = 1,
  totalCount,
  pageSize = 10,
  onPageChange,
  onPageSizeChange,
}) => {
  // Local fallback filters if not controlled externally
  const localFilters = useTradeFilters(trades);

  const isControlled = onFilterResultChange !== undefined;

  const activeResult = isControlled ? controlledResult! : localFilters.filterResult;
  const activeSymbol = isControlled ? controlledSymbol! : localFilters.filterSymbol;
  const activeStrategy = isControlled ? controlledStrategy! : localFilters.filterStrategy;
  const hasActive = isControlled ? !!controlledHasActiveFilters : localFilters.hasActiveFilters;

  const handleResultChange = (val: TradeResultFilter) => {
    if (onFilterResultChange) onFilterResultChange(val);
    else localFilters.setFilterResult(val);
  };

  const handleSymbolChange = (val: TradeSymbolFilter) => {
    if (onFilterSymbolChange) onFilterSymbolChange(val);
    else localFilters.setFilterSymbol(val);
  };

  const handleStrategyChange = (val: TradeStrategyFilter) => {
    if (onFilterStrategyChange) onFilterStrategyChange(val);
    else localFilters.setFilterStrategy(val);
  };

  const handleReset = () => {
    if (controlledResetFilters) controlledResetFilters();
    else localFilters.resetFilters();
  };

  // If controlled externally, `trades` are already filtered/paginated
  const displayTrades = isControlled ? trades : localFilters.filteredTrades;
  const displayTotal = totalCount !== undefined ? totalCount : displayTrades.length;

  if (isLoading) {
    return <TradeHistorySkeleton />;
  }

  return (
    <div
      id="panel-trade-history"
      className={`bg-slate-900/80 border border-slate-800 rounded-md overflow-hidden flex flex-col ${className}`}
    >
      {/* Panel Header */}
      <div className="px-3.5 py-2.5 bg-slate-950/90 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex items-center gap-2">
          <History size={14} className="text-emerald-400" />
          <h2
            id="title-trade-history"
            className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono"
          >
            Trade History
          </h2>
          <span className="text-[10px] font-mono text-slate-400 bg-slate-800/60 px-1.5 py-0.5 rounded border border-slate-700/60">
            {displayTotal} {displayTotal === 1 ? 'Trade' : 'Trades'}
          </span>
        </div>

        {/* Local Filter Strip & Actions */}
        <div className="flex items-center gap-2 flex-wrap text-xs font-mono">
          <div className="flex items-center gap-1 text-slate-500 text-[11px]">
            <Filter size={11} />
            <span className="hidden sm:inline">Filters:</span>
          </div>

          {/* Result Filter */}
          <select
            id="select-filter-result"
            aria-label="Filter trades by result"
            value={activeResult}
            onChange={(e) => handleResultChange(e.target.value as TradeResultFilter)}
            className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-[11px] text-slate-300 focus:outline-none focus:border-slate-700"
          >
            <option value="All">All Results</option>
            <option value="Winners">Winners</option>
            <option value="Losers">Losers</option>
          </select>

          {/* Symbol Filter */}
          <select
            id="select-filter-symbol"
            aria-label="Filter trades by symbol"
            value={activeSymbol}
            onChange={(e) => handleSymbolChange(e.target.value as TradeSymbolFilter)}
            className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-[11px] text-slate-300 focus:outline-none focus:border-slate-700"
          >
            <option value="All">All Symbols</option>
            <option value="BTCUSDT">BTCUSDT</option>
            <option value="ETHUSDT">ETHUSDT</option>
            <option value="SOLUSDT">SOLUSDT</option>
          </select>

          {/* Strategy Filter */}
          <select
            id="select-filter-strategy"
            aria-label="Filter trades by strategy"
            value={activeStrategy}
            onChange={(e) => handleStrategyChange(e.target.value as TradeStrategyFilter)}
            className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-[11px] text-slate-300 focus:outline-none focus:border-slate-700"
          >
            <option value="All">All Strategies</option>
            <option value="EMA + RSI">EMA + RSI</option>
            <option value="Bollinger Squeeze">Bollinger Squeeze</option>
          </select>

          {/* Reset Filters Action */}
          {hasActive && (
            <button
              id="btn-reset-trade-filters"
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-1 px-1.5 py-1 rounded text-[11px] text-amber-400 hover:text-amber-300 hover:bg-slate-800 transition-colors"
              title="Reset all filters"
            >
              <RotateCcw size={10} />
              <span>Reset</span>
            </button>
          )}

          {/* Retry / Refresh Action */}
          {onRetry && (
            <button
              type="button"
              id="btn-retry-trades"
              onClick={onRetry}
              disabled={isLoading}
              className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors disabled:opacity-50"
              title="Reload local trade data"
              aria-label="Reload local trade data"
            >
              <RefreshCw size={11} className={isLoading ? 'animate-spin' : ''} />
            </button>
          )}
        </div>
      </div>

      {/* Non-fatal error notification strip */}
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

      {/* Trades Table or Empty State */}
      {displayTrades.length === 0 ? (
        <EmptyState
          title={isError ? 'Unable to load trades' : hasActive ? 'No trades match filter criteria' : 'No closed trades recorded'}
          description={
            isError
              ? (errorMessage || 'Unable to load local trade data.')
              : hasActive
              ? 'Try changing or clearing your active filters to see historical trade logs.'
              : 'No closed trade executions recorded for this session.'
          }
          icon={isError ? 'alert' : hasActive ? 'filter' : 'inbox'}
          actionLabel={isError && onRetry ? 'Retry Fetch' : hasActive ? 'Clear Filters' : undefined}
          onAction={isError && onRetry ? onRetry : hasActive ? handleReset : undefined}
        />
      ) : (
        <div className="max-w-full overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <caption className="sr-only">Closed trade history</caption>
            <thead>
              <tr className="border-b border-slate-800/80 bg-slate-950/40 text-[11px] text-slate-400 uppercase tracking-wider">
                <th className="py-2 px-3 font-medium">Closed Time</th>
                <th className="py-2 px-3 font-medium">Symbol</th>
                <th className="py-2 px-3 font-medium">Side</th>
                <th className="py-2 px-3 font-medium">Strategy</th>
                <th className="py-2 px-3 font-medium">TF</th>
                <th className="py-2 px-3 font-medium text-right">Entry</th>
                <th className="py-2 px-3 font-medium text-right">Exit</th>
                <th className="py-2 px-3 font-medium text-right">PnL ($)</th>
                <th className="py-2 px-3 font-medium text-right">PnL (%)</th>
                <th className="py-2 px-3 font-medium text-right">R:R</th>
                <th className="py-2 px-3 font-medium text-right">Duration</th>
                <th className="py-2 px-3 font-medium text-center">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 text-slate-300">
              {displayTrades.map((trade) => {
                const isWin = trade.result === 'Win';
                const isLoss = trade.result === 'Loss';
                const pnlClass = isWin
                  ? 'text-emerald-400'
                  : isLoss
                  ? 'text-rose-400'
                  : 'text-slate-400';

                return (
                  <tr
                    key={trade.id}
                    id={`row-trade-${trade.id}`}
                    className="hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap text-[11px]">
                      {trade.closedAt}
                    </td>

                    <td className="py-2.5 px-3 font-bold text-slate-100 whitespace-nowrap">
                      {trade.symbol}
                    </td>

                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <StatusBadge type="position" value={trade.side} size="xs" />
                    </td>

                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span className="px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/50 text-[11px]">
                        {trade.strategy}
                      </span>
                    </td>

                    <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                      {trade.timeframe}
                    </td>

                    <td className="py-2.5 px-3 text-right font-medium text-slate-300 whitespace-nowrap">
                      ${trade.entry.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>

                    <td className="py-2.5 px-3 text-right font-medium text-slate-200 whitespace-nowrap">
                      ${trade.exit.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>

                    <td className={`py-2.5 px-3 text-right font-bold whitespace-nowrap ${pnlClass}`}>
                      {formatCurrency(trade.pnl, { showSign: true })}
                    </td>

                    <td className={`py-2.5 px-3 text-right font-semibold whitespace-nowrap ${pnlClass}`}>
                      {formatPercentage(trade.pnlPercentage, { showSign: true })}
                    </td>

                    <td className="py-2.5 px-3 text-right text-slate-300 whitespace-nowrap">
                      {trade.rr}
                    </td>

                    <td className="py-2.5 px-3 text-right text-slate-400 whitespace-nowrap text-[11px]">
                      {trade.duration}
                    </td>

                    <td className="py-2.5 px-3 text-center whitespace-nowrap">
                      <StatusBadge type="trade-result" value={trade.result} size="xs" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Footer */}
      {onPageChange && totalPages > 1 && (
        <div className="px-3.5 py-2 bg-slate-950/70 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400 flex-wrap gap-2">
          <div className="flex items-center gap-2 text-[11px]">
            <span>
              Page <strong className="text-slate-200">{page}</strong> of{' '}
              <strong className="text-slate-200">{totalPages}</strong>
            </span>
            {onPageSizeChange && (
              <div className="flex items-center gap-1 ml-2 text-slate-500">
                <span>Per page:</span>
                <select
                  aria-label="Trades per page"
                  value={pageSize}
                  onChange={(e) => onPageSizeChange(Number(e.target.value))}
                  className="bg-slate-900 border border-slate-800 rounded px-1.5 py-0.5 text-[10px] text-slate-300 focus:outline-none"
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                </select>
              </div>
            )}
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              id="btn-prev-trades-page"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-slate-900 border border-slate-800 text-[11px] text-slate-300 hover:bg-slate-800 disabled:opacity-40 disabled:pointer-events-none transition-colors"
            >
              <ChevronLeft size={12} />
              <span>Prev</span>
            </button>
            <span className="px-2 py-1 text-[11px] text-slate-400 font-mono">
              {page} / {totalPages}
            </span>
            <button
              type="button"
              id="btn-next-trades-page"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-slate-900 border border-slate-800 text-[11px] text-slate-300 hover:bg-slate-800 disabled:opacity-40 disabled:pointer-events-none transition-colors"
            >
              <span>Next</span>
              <ChevronRight size={12} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
