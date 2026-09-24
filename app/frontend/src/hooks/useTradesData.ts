import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getTrades, PaginationMeta } from '../api';
import { Trade } from '../types';
import {
  TradeResultFilter,
  TradeStrategyFilter,
  TradeSymbolFilter,
} from './useTradeFilters';

export interface UseTradesDataReturn {
  // Current visible trades (either paginated or filtered)
  trades: Trade[];
  // Total count of trades matching filters
  totalMatchingCount: number;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
  isServerPaginated: boolean;
  // Pagination
  page: number;
  setPage: (page: number) => void;
  pageSize: number;
  setPageSize: (size: number) => void;
  totalPages: number;
  pagination: PaginationMeta;
  // Filters
  filterResult: TradeResultFilter;
  setFilterResult: (filter: TradeResultFilter) => void;
  filterSymbol: TradeSymbolFilter;
  setFilterSymbol: (filter: TradeSymbolFilter) => void;
  filterStrategy: TradeStrategyFilter;
  setFilterStrategy: (filter: TradeStrategyFilter) => void;
  hasActiveFilters: boolean;
  resetFilters: () => void;
  // Actions
  refetch: () => Promise<void>;
}

export function useTradesData(): UseTradesDataReturn {
  const [rawTrades, setRawTrades] = useState<Trade[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isError, setIsError] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Pagination state
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);

  // Filter state
  const [filterResult, setFilterResult] = useState<TradeResultFilter>('All');
  const [filterSymbol, setFilterSymbol] = useState<TradeSymbolFilter>('All');
  const [filterStrategy, setFilterStrategy] = useState<TradeStrategyFilter>('All');

  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const fetchTrades = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setErrorMessage(null);

    try {
      const localTrades = await getTrades();

      if (!isMountedRef.current) return;

      setRawTrades(localTrades);
      setIsError(false);
      setErrorMessage(null);
    } catch (err: unknown) {
      if (!isMountedRef.current) return;

      const msg = err instanceof Error ? err.message : 'Unable to load local trade data.';
      setIsError(true);
      setErrorMessage(msg);
      setRawTrades([]);
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchTrades();
  }, [fetchTrades]);

  // Client-side filtering when backend returns a flat array or when fallback mock data is in use
  const filteredTrades = useMemo(() => {
    return rawTrades.filter((trade) => {
      // Result filter
      if (filterResult === 'Winners' && trade.result !== 'Win') return false;
      if (filterResult === 'Losers' && trade.result !== 'Loss') return false;

      // Symbol filter
      if (filterSymbol !== 'All' && trade.symbol !== filterSymbol) return false;

      // Strategy filter
      if (filterStrategy !== 'All' && trade.strategy !== filterStrategy) return false;

      return true;
    });
  }, [rawTrades, filterResult, filterSymbol, filterStrategy]);

  // Client-side pagination if not server-paginated
  const paginatedTrades = useMemo(() => {
    const startIndex = (page - 1) * pageSize;
    return filteredTrades.slice(startIndex, startIndex + pageSize);
  }, [filteredTrades, page, pageSize]);

  const totalMatchingCount = filteredTrades.length;
  const totalPages = Math.max(1, Math.ceil(totalMatchingCount / pageSize));

  // Auto-clamp page if filter reduced total pages
  useEffect(() => {
    if (page > totalPages && totalPages > 0) {
      setPage(1);
    }
  }, [page, totalPages]);

  const paginationMeta: PaginationMeta = useMemo(() => {
    return {
      page,
      limit: pageSize,
      total: totalMatchingCount,
      totalPages,
      hasNextPage: page < totalPages,
      hasPrevPage: page > 1,
    };
  }, [page, pageSize, totalMatchingCount, totalPages]);

  const hasActiveFilters =
    filterResult !== 'All' || filterSymbol !== 'All' || filterStrategy !== 'All';

  const resetFilters = useCallback(() => {
    setFilterResult('All');
    setFilterSymbol('All');
    setFilterStrategy('All');
    setPage(1);
  }, []);

  return {
    trades: paginatedTrades,
    totalMatchingCount,
    isLoading,
    isError,
    errorMessage,
    isServerPaginated: false,
    page,
    setPage,
    pageSize,
    setPageSize,
    totalPages,
    pagination: paginationMeta,
    filterResult,
    setFilterResult,
    filterSymbol,
    setFilterSymbol,
    filterStrategy,
    setFilterStrategy,
    hasActiveFilters,
    resetFilters,
    refetch: fetchTrades,
  };
}
