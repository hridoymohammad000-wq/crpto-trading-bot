import { useMemo, useState } from 'react';
import { Trade, TradingSymbol } from '../types';

export type TradeResultFilter = 'All' | 'Winners' | 'Losers';
export type TradeSymbolFilter = 'All' | TradingSymbol;
export type TradeStrategyFilter = 'All' | 'EMA + RSI' | 'Bollinger Squeeze';

export interface UseTradeFiltersReturn {
  filterResult: TradeResultFilter;
  setFilterResult: (filter: TradeResultFilter) => void;
  filterSymbol: TradeSymbolFilter;
  setFilterSymbol: (filter: TradeSymbolFilter) => void;
  filterStrategy: TradeStrategyFilter;
  setFilterStrategy: (filter: TradeStrategyFilter) => void;
  filteredTrades: Trade[];
  hasActiveFilters: boolean;
  resetFilters: () => void;
}

export function useTradeFilters(trades: Trade[]): UseTradeFiltersReturn {
  const [filterResult, setFilterResult] = useState<TradeResultFilter>('All');
  const [filterSymbol, setFilterSymbol] = useState<TradeSymbolFilter>('All');
  const [filterStrategy, setFilterStrategy] = useState<TradeStrategyFilter>('All');

  const filteredTrades = useMemo(() => {
    return trades.filter((trade) => {
      // Result filter
      if (filterResult === 'Winners' && trade.result !== 'Win') return false;
      if (filterResult === 'Losers' && trade.result !== 'Loss') return false;

      // Symbol filter
      if (filterSymbol !== 'All' && trade.symbol !== filterSymbol) return false;

      // Strategy filter
      if (filterStrategy !== 'All' && trade.strategy !== filterStrategy) return false;

      return true;
    });
  }, [trades, filterResult, filterSymbol, filterStrategy]);

  const hasActiveFilters =
    filterResult !== 'All' || filterSymbol !== 'All' || filterStrategy !== 'All';

  const resetFilters = () => {
    setFilterResult('All');
    setFilterSymbol('All');
    setFilterStrategy('All');
  };

  return {
    filterResult,
    setFilterResult,
    filterSymbol,
    setFilterSymbol,
    filterStrategy,
    setFilterStrategy,
    filteredTrades,
    hasActiveFilters,
    resetFilters,
  };
}
