import { useCallback, useEffect, useRef, useState } from 'react';
import { getSignals } from '../api';
import { Signal, TradingSymbol } from '../types';

export interface UseSignalsDataReturn {
  signals: Signal[];
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
  refetch: () => Promise<void>;
}

export function useSignalsData(symbol?: TradingSymbol): UseSignalsDataReturn {
  const [signals, setSignals] = useState<Signal[]>([]);
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

  const fetchSignals = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setErrorMessage(null);

    try {
      const localSignals = await getSignals(symbol);

      if (!isMountedRef.current) return;

      setSignals(localSignals);
      setIsError(false);
      setErrorMessage(null);
    } catch (err: unknown) {
      if (!isMountedRef.current) return;

      const msg = err instanceof Error ? err.message : 'Unable to load local signal data.';
      setIsError(true);
      setErrorMessage(msg);
      setSignals([]);
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [symbol]);

  useEffect(() => {
    fetchSignals();
  }, [fetchSignals]);

  return {
    signals,
    isLoading,
    isError,
    errorMessage,
    refetch: fetchSignals,
  };
}
