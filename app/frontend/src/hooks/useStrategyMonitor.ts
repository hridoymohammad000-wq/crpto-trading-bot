import { useCallback, useEffect, useRef, useState } from 'react';
import { getStrategyEvaluation } from '../api/strategy';
import {
  createInitialMonitorState,
  fetchStrategyOutcomes,
  mergeStrategyOutcomes,
} from '../features/strategy/monitorState';

const POLL_INTERVAL_MS = 30_000;

export function useStrategyMonitor() {
  const [items, setItems] = useState(createInitialMonitorState);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const requestInFlight = useRef(false);
  const mounted = useRef(false);

  const refresh = useCallback(async () => {
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    setIsRefreshing(true);
    try {
      const outcomes = await fetchStrategyOutcomes(getStrategyEvaluation);
      if (mounted.current) {
        setItems((previous) =>
          mergeStrategyOutcomes(previous, outcomes, new Date().toISOString()),
        );
      }
    } finally {
      requestInFlight.current = false;
      if (mounted.current) setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const intervalId = window.setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => {
      mounted.current = false;
      window.clearInterval(intervalId);
    };
  }, [refresh]);

  return { items, isRefreshing, refresh, pollIntervalMs: POLL_INTERVAL_MS };
}
