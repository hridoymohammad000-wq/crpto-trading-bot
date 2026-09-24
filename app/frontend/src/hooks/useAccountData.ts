import { useCallback, useEffect, useRef, useState } from 'react';
import { getAccount } from '../api';
import { AccountSummary } from '../types';

export interface UseAccountDataReturn {
  data: AccountSummary | null;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
  refetch: () => Promise<void>;
}

export function useAccountData(): UseAccountDataReturn {
  const [data, setData] = useState<AccountSummary | null>(null);
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

  const fetchAccount = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setErrorMessage(null);

    try {
      const localData = await getAccount();

      if (!isMountedRef.current) return;

      setData(localData);
      setIsError(false);
      setErrorMessage(null);
    } catch (err: unknown) {
      if (!isMountedRef.current) return;

      const msg = err instanceof Error ? err.message : 'Unable to load local account data.';
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
    fetchAccount();
  }, [fetchAccount]);

  return {
    data,
    isLoading,
    isError,
    errorMessage,
    refetch: fetchAccount,
  };
}
