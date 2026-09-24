import { useCallback, useEffect, useState } from 'react';
import { getCandles } from '../api/candles';

import {
  ActiveTradeLevels,
  Candle,
  ChartSignalMarker,
  Position,
  Signal,
  Timeframe,
  TradingSymbol,
} from '../types';

export interface UseCandlesOptions {
  symbol: TradingSymbol;
  timeframe: Timeframe;
  positions?: Position[];
  signals?: Signal[];
}

export function useCandles({
  symbol,
  timeframe,
  positions = [],
  signals = [],
}: UseCandlesOptions) {
  const [candles, setCandles] = useState<Candle[]>([]);
  const [markers, setMarkers] = useState<ChartSignalMarker[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isError, setIsError] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchCandles = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setErrorMessage(null);

    try {
      const res = await getCandles(symbol, timeframe);
      setCandles(res.candles);

      // Aggregate signal markers from candle dataset
      const aggregatedMarkers: ChartSignalMarker[] = [...res.markers];

      // Add any live signal markers passed from signals hook for this symbol if matching
      if (signals && signals.length > 0) {
        const symbolSignals = signals.filter((s) => s.symbol === symbol);
        // If we have live signals, ensure they are represented on recent candle timestamps
        if (symbolSignals.length > 0 && res.candles.length > 0) {
          const lastCandle = res.candles[res.candles.length - 1];
          symbolSignals.slice(0, 2).forEach((sig, idx) => {
            // Find or use a candle near the end
            const targetIdx = Math.max(0, res.candles.length - 1 - (idx * 4 + 2));
            const targetCandle = res.candles[targetIdx] || lastCandle;
            
            // Check if already in markers
            const exists = aggregatedMarkers.some((m) => m.id === `sig-live-${sig.id}`);
            if (!exists) {
              aggregatedMarkers.push({
                id: `sig-live-${sig.id}`,
                time: targetCandle.time,
                position: sig.side === 'BUY' ? 'belowBar' : 'aboveBar',
                shape: sig.side === 'BUY' ? 'arrowUp' : 'arrowDown',
                color: sig.side === 'BUY' ? '#10b981' : '#f43f5e',
                text: `${sig.side} (${sig.strategy})`,
                price: sig.entry,
                type: sig.side,
              });
            }
          });
        }
      }

      setMarkers(aggregatedMarkers);
    } catch (err: unknown) {
      setIsError(true);
      setErrorMessage(err instanceof Error ? err.message : 'Failed to load candle data');
    } finally {
      setIsLoading(false);
    }
  }, [symbol, timeframe, signals]);

  useEffect(() => {
    fetchCandles();
  }, [fetchCandles]);

  // Determine active trade levels (SL, TP, Entry) from open positions for this symbol
  // Fallback to the most recent signal for this symbol if no active position exists
  const activePosition = positions.find((p) => p.symbol === symbol);
  const latestSignal = !activePosition ? signals.find((s) => s.symbol === symbol) : null;

  let activeLevels: ActiveTradeLevels | null = null;
  if (activePosition) {
    activeLevels = {
      entryPrice: activePosition.entry ?? undefined,
      stopLoss: activePosition.sl ?? undefined,
      takeProfit: activePosition.tp ?? undefined,
      side: activePosition.side,
    };
  } else if (latestSignal) {
    activeLevels = {
      entryPrice: latestSignal.entry ?? undefined,
      stopLoss: latestSignal.sl ?? undefined,
      takeProfit: latestSignal.tp ?? undefined,
      side: latestSignal.side === 'BUY' ? 'LONG' : 'SHORT',
    };
  }


  return {
    candles,
    markers,
    isLoading,
    isError,
    errorMessage,
    refetch: fetchCandles,
    activeLevels,
    activePosition,
  };
}
