import { useCallback, useEffect, useRef, useState } from 'react';
import { getPerformance } from '../api';
import { PerformanceData, PerformanceMetrics } from '../types';

export interface UsePerformanceDataReturn {
  data: PerformanceData | null;
  metrics: PerformanceMetrics;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
  refetch: () => Promise<void>;
}

export function usePerformanceData(): UsePerformanceDataReturn {
  const [data, setData] = useState<PerformanceData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isError, setIsError] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const loadPerformance = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setErrorMessage(null);

    try {
      const localData = await getPerformance();

      if (!isMountedRef.current) return;

      setData(localData);
      setIsError(false);
      setErrorMessage(null);
    } catch (err: unknown) {
      if (!isMountedRef.current) return;

      const msg = err instanceof Error ? err.message : 'Unable to load local performance data.';
      setIsError(true);
      setErrorMessage(msg);
      setData(null);
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadPerformance();
  }, [loadPerformance]);

  return {
    data,
    metrics: data?.metrics ?? {
      totalPnl: 0, dailyPnl: 0, totalPnlPercentage: 0, winRate: 0, profitFactor: 0,
      averageRR: '-', maxDrawdown: 0, totalTrades: 0, winningTrades: 0, losingTrades: 0,
      averageWinner: 0, averageLoser: 0
    },
    isLoading,
    isError,
    errorMessage,
    refetch: loadPerformance,
  };
}
