import { useCallback, useEffect, useRef, useState } from 'react';
import { getReconciliation } from '../api';

export interface UseReconciliationReturn {
  data: any | null;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
  refetch: () => Promise<void>;
}

export function useReconciliation(): UseReconciliationReturn {
  const [data, setData] = useState<any | null>(null);
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

  const fetchRecon = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setErrorMessage(null);

    try {
      const result = await getReconciliation();
      if (!isMountedRef.current) return;
      setData(result);
    } catch (err: unknown) {
      if (!isMountedRef.current) return;
      const msg = err instanceof Error ? err.message : 'Unable to load reconciliation.';
      setIsError(true);
      setErrorMessage(msg);
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchRecon();
    const interval = setInterval(fetchRecon, 15000); // 15s refresh
    return () => clearInterval(interval);
  }, [fetchRecon]);

  return {
    data,
    isLoading,
    isError,
    errorMessage,
    refetch: fetchRecon,
  };
}
