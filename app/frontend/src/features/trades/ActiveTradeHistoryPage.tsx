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

function money(value: number | string | null | undefined): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '$0.00';
  const sign = numeric > 0 ? '+' : '';
  return `${sign}$${numeric.toFixed(2)}`;
}

export const ActiveTradeHistoryPage: React.FC<Props> = (props) => {
  const [period, setPeriod] = useState<HistoryPeriod>('Today');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');

  const todayTrades = useMemo(
    () => filterTradesByHistoryPeriod(props.trades, { period: 'Today' }),
    [props.trades],
  );

  const todaySummary = useMemo(() => {
    const closedTrades = todayTrades;
    const openTrades = props.positions;

    const wins = closedTrades.filter((trade) => trade.result === 'Win');
    const losses = closedTrades.filter((trade) => trade.result === 'Loss');

    const slHits = closedTrades.filter(
      (trade) => trade.exitReason === 'LIKELY_SL_HIT',
    ).length;

    const tpHits = closedTrades.filter(
      (trade) => trade.exitReason === 'LIKELY_TP_HIT',
    ).length;

    const realizedPnl = closedTrades.reduce(
      (sum, trade) => sum + (Number.isFinite(trade.pnl) ? trade.pnl : 0),
      0,
    );

    const grossProfit = wins.reduce(
      (sum, trade) => sum + trade.pnl,
      0,
    );

    const grossLoss = losses.reduce(
      (sum, trade) => sum + Math.abs(trade.pnl),
      0,
    );

    const winRate =
      closedTrades.length > 0
        ? (wins.length / closedTrades.length) * 100
        : 0;

    const avgWin =
      wins.length > 0
        ? grossProfit / wins.length
        : 0;

    const avgLoss =
      losses.length > 0
        ? grossLoss / losses.length
        : 0;

    const profitFactor =
      grossLoss > 0
        ? grossProfit / grossLoss
        : grossProfit > 0
        ? Infinity
        : 0;

    const bestTrade =
      closedTrades.length > 0
        ? closedTrades.reduce((best, trade) =>
            trade.pnl > best.pnl ? trade : best
          )
        : null;

    const worstTrade =
      closedTrades.length > 0
        ? closedTrades.reduce((worst, trade) =>
            trade.pnl < worst.pnl ? trade : worst
          )
        : null;

    return {
      totalTrades: openTrades.length + closedTrades.length,
      openTrades: openTrades.length,
      closedTrades: closedTrades.length,
      slHits,
      tpHits,
      wins: wins.length,
      losses: losses.length,
      realizedPnl,
      winRate,
      grossProfit,
      grossLoss,
      avgWin,
      avgLoss,
      profitFactor,
      bestTrade,
      worstTrade,
    };
  }, [todayTrades, props.positions]);

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
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold font-mono text-slate-100">
            <CalendarDays size={15} className="text-emerald-400" />
            Today Summary
          </h2>
          <p className="mt-0.5 text-[11px] font-mono text-slate-500">
            Current local-calendar-day trading activity and realized performance.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          {[
            ['Total Trades', todaySummary.totalTrades],
            ['Open', todaySummary.openTrades],
            ['Closed', todaySummary.closedTrades],
            ['SL Hit', todaySummary.slHits],
            ['TP Hit', todaySummary.tpHits],
            ['Wins', todaySummary.wins],
            ['Losses', todaySummary.losses],
            ['Win Rate', `${todaySummary.winRate.toFixed(1)}%`],
          ].map(([label, value]) => (
            <div
              key={String(label)}
              className="rounded-md border border-slate-800 bg-slate-900/80 px-3 py-3"
            >
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
                {label}
              </div>
              <div className="mt-1 text-lg font-bold font-mono text-slate-100">
                {value}
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          {[
            ['Realized PnL', money(todaySummary.realizedPnl)],
            ['Gross Profit', money(todaySummary.grossProfit)],
            ['Gross Loss', `-$${todaySummary.grossLoss.toFixed(2)}`],
            ['Avg Win', money(todaySummary.avgWin)],
            ['Avg Loss', `-$${todaySummary.avgLoss.toFixed(2)}`],
            [
              'Profit Factor',
              Number.isFinite(todaySummary.profitFactor)
                ? todaySummary.profitFactor.toFixed(2)
                : '∞',
            ],
            [
              'Best Trade',
              todaySummary.bestTrade
                ? `${todaySummary.bestTrade.symbol} ${money(todaySummary.bestTrade.pnl)}`
                : '-',
            ],
            [
              'Worst Trade',
              todaySummary.worstTrade
                ? `${todaySummary.worstTrade.symbol} ${money(todaySummary.worstTrade.pnl)}`
                : '-',
            ],
          ].map(([label, value]) => (
            <div
              key={String(label)}
              className="rounded-md border border-slate-800 bg-slate-900/80 px-3 py-3"
            >
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
                {label}
              </div>
              <div className="mt-1 text-sm font-bold font-mono text-slate-100">
                {value}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex flex-col gap-3 border-b border-slate-800 pb-2 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold font-mono text-slate-100">
              <CalendarDays size={15} className="text-cyan-400" /> Trade History
            </h2>
            <p className="mt-0.5 text-[11px] font-mono text-slate-500">
              Default view is today. Switch to the last 7 days or a custom range.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
            {(['Today', '7D', 'Custom'] as HistoryPeriod[]).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setPeriod(item)}
                className={`rounded border px-2.5 py-1.5 ${
                  period === item
                    ? 'border-emerald-700 bg-emerald-950/50 text-emerald-300'
                    : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200'
                }`}
              >
                {item === '7D' ? 'Last 7 Days' : item}
              </button>
            ))}

            {period === 'Custom' && (
              <>
                <input
                  aria-label="History from date"
                  type="date"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                  className="rounded border border-slate-800 bg-slate-900 px-2 py-1.5 text-slate-300"
                />
                <span className="text-slate-600">to</span>
                <input
                  aria-label="History to date"
                  type="date"
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                  className="rounded border border-slate-800 bg-slate-900 px-2 py-1.5 text-slate-300"
                />
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


