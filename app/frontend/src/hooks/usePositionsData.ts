import { useCallback, useEffect, useRef, useState } from 'react';
import { getPositions } from '../api';
import { Position } from '../types';

export interface UsePositionsDataReturn {
  positions: Position[];
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
  refetch: () => Promise<void>;
}

export function usePositionsData(): UsePositionsDataReturn {
  const [positions, setPositions] = useState<Position[]>([]);
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

  const fetchPositions = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setErrorMessage(null);

    try {
      const localData = await getPositions();

      if (!isMountedRef.current) return;

      setPositions(localData);
      setIsError(false);
      setErrorMessage(null);
    } catch (err: unknown) {
      if (!isMountedRef.current) return;

      const msg = err instanceof Error ? err.message : 'Unable to load local positions data.';
      setIsError(true);
      setErrorMessage(msg);
      setPositions([]);
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);

  return {
    positions,
    isLoading,
    isError,
    errorMessage,
    refetch: fetchPositions,
  };
}
