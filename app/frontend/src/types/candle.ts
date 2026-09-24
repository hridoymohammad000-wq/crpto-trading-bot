export interface Candle {
  time: number; // Unix timestamp in seconds (UTCTimestamp)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type MarkerPosition = 'aboveBar' | 'belowBar' | 'inBar';
export type MarkerShape = 'circle' | 'square' | 'arrowUp' | 'arrowDown';

export interface ChartSignalMarker {
  id: string;
  time: number;
  position: MarkerPosition;
  shape: MarkerShape;
  color: string;
  text: string;
  price?: number;
  type: 'BUY' | 'SELL' | 'ENTRY' | 'EXIT';
}

export interface ChartPriceLineConfig {
  id: string;
  price: number;
  title: string;
  color: string;
  lineStyle?: 'solid' | 'dotted' | 'dashed';
  lineWidth?: number;
}

export interface ActiveTradeLevels {
  entryPrice?: number;
  stopLoss?: number;
  takeProfit?: number;
  side?: 'LONG' | 'SHORT';
}
