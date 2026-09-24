import React, { useMemo, useState } from 'react';
import { CalendarDays } from 'lucide-react';
import { Position, Trade } from '../../types';
import { ActivePositionCards } from './ActivePositionCards';
import { TradeHistoryTable } from './TradeHistoryTable';
import { TradeResultFilter, TradeStrategyFilter, TradeSymbolFilter } from '../../hooks/useTradeFilters';
import { filterTradesByHistoryPeriod, HistoryPeriod } from './historyPeriod';

interface Props {
  positions: Position[];
  trades: Trade[];
  onSelectPosition: (position: Position) => void;
  isLiveUpdates: boolean;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
  onRetry: () => Promise<void>;
  filterResult: TradeResultFilter;
  onFilterResultChange: (value: TradeResultFilter) => void;
  filterSymbol: TradeSymbolFilter;
  onFilterSymbolChange: (value: TradeSymbolFilter) => void;
  filterStrategy: TradeStrategyFilter;
  onFilterStrategyChange: (value: TradeStrategyFilter) => void;
  onResetFilters: () => void;
  hasActiveFilters: boolean;
}

export const ActiveTradeHistoryPage: React.FC<Props> = (props) => {
  const [period, setPeriod] = useState<HistoryPeriod>('Today');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');

  const filteredTrades = useMemo(
    () => filterTradesByHistoryPeriod(props.trades, { period, fromDate, toDate }),
    [props.trades, period, fromDate, toDate],
  );

  return (
    <div className="space-y-6">
      <ActivePositionCards
        positions={props.positions}
        onSelectPosition={props.onSelectPosition}
        isLiveUpdates={props.isLiveUpdates}
      />

      <section className="space-y-3">
        <div className="flex flex-col gap-3 border-b border-slate-800 pb-2 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold font-mono text-slate-100">
              <CalendarDays size={15} className="text-cyan-400" /> Trade History
            </h2>
            <p className="mt-0.5 text-[11px] font-mono text-slate-500">Default view is today. Switch to the last 7 days or a custom range.</p>
          </div>

          <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
            {(['Today', '7D', 'Custom'] as HistoryPeriod[]).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setPeriod(item)}
                className={`rounded border px-2.5 py-1.5 ${period === item ? 'border-emerald-700 bg-emerald-950/50 text-emerald-300' : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200'}`}
              >
                {item === '7D' ? 'Last 7 Days' : item}
              </button>
            ))}
            {period === 'Custom' && (
              <>
                <input aria-label="History from date" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="rounded border border-slate-800 bg-slate-900 px-2 py-1.5 text-slate-300" />
                <span className="text-slate-600">to</span>
                <input aria-label="History to date" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="rounded border border-slate-800 bg-slate-900 px-2 py-1.5 text-slate-300" />
              </>
            )}
          </div>
        </div>

        <TradeHistoryTable
          trades={filteredTrades}
          isLoading={props.isLoading}
          isError={props.isError}
          errorMessage={props.errorMessage}
          onRetry={props.onRetry}
          filterResult={props.filterResult}
          onFilterResultChange={props.onFilterResultChange}
          filterSymbol={props.filterSymbol}
          onFilterSymbolChange={props.onFilterSymbolChange}
          filterStrategy={props.filterStrategy}
          onFilterStrategyChange={props.onFilterStrategyChange}
          onResetFilters={props.onResetFilters}
          hasActiveFilters={props.hasActiveFilters}
          page={1}
          totalPages={1}
          totalCount={filteredTrades.length}
          pageSize={Math.max(10, filteredTrades.length)}
        />
      </section>
    </div>
  );
};
