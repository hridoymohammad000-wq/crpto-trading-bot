import { apiClient } from './client';
import { RequestOptions } from './types';
import { Candle, ChartSignalMarker, Timeframe, TradingSymbol } from '../types';

export interface CandleResponse {
  symbol: TradingSymbol;
  timeframe: Timeframe;
  candles: Candle[];
  markers: ChartSignalMarker[];
  isMock: boolean;
}

interface BackendCandle {
  symbol: TradingSymbol;
  timeframe: Timeframe;
  start_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  turnover: number;
  is_closed: boolean;
}

export async function getCandles(
  symbol: TradingSymbol,
  timeframe: Timeframe,
  barCount: number = 96,
  options?: RequestOptions
): Promise<CandleResponse> {
  const data = await apiClient.get<BackendCandle[]>(`/market/candles?symbol=${symbol}&timeframe=${timeframe}&limit=${barCount}`, options);
  
  const frontendCandles: Candle[] = data.map(c => ({
    time: Math.floor(new Date(c.start_time).getTime() / 1000), // convert to seconds
    open: Number(c.open),
    high: Number(c.high),
    low: Number(c.low),
    close: Number(c.close),
    volume: Number(c.volume)
  }));

  // Sort them just in case
  frontendCandles.sort((a, b) => (a.time as number) - (b.time as number));

  return {
    symbol,
    timeframe,
    candles: frontendCandles,
    markers: [],
    isMock: false,
  };
}
