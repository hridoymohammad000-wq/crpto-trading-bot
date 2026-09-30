import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { SymbolTickerInfo, TradingSymbol } from '../types';

interface BackendTicker {
  symbol: string;
  last_price: number | string;
  high_price_24h?: number | string | null;
  low_price_24h?: number | string | null;
  volume_24h?: number | string | null;
  price_change_24h_pct?: number | string | null;
}

export function useTicker(symbol: TradingSymbol) {
  const [ticker, setTicker] = useState<SymbolTickerInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchTicker = useCallback(async () => {
    setIsLoading(true);
    setIsError(false);
    setErrorMessage(null);

    try {
      const data = await apiClient.get<BackendTicker>(
        `/market/ticker?symbol=${encodeURIComponent(symbol)}`
      );

      const rawChange = Number(data.price_change_24h_pct ?? 0);

      setTicker({
        symbol: data.symbol,
        name: `${data.symbol.replace(/USDT$/, '')} / TetherUS`,
        price: Number(data.last_price),
        change24h: rawChange * 100,
        high24h: Number(data.high_price_24h ?? 0),
        low24h: Number(data.low_price_24h ?? 0),
        volume24h: String(data.volume_24h ?? 0),
      });
    } catch (err: unknown) {
      setTicker(null);
      setIsError(true);
      setErrorMessage(
        err instanceof Error ? err.message : 'Failed to load ticker'
      );
    } finally {
      setIsLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    fetchTicker();
  }, [fetchTicker]);

  return {
    ticker,
    isLoading,
    isError,
    errorMessage,
    refetch: fetchTicker,
  };
}
