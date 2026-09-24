import { Timeframe, TradingSymbol } from './market';

export type TradeSide = 'BUY' | 'SELL';

export type SignalStrategy = 'EMA + RSI' | 'Bollinger Squeeze' | 'VWAP Pullback';

export type SignalStatus = 'New' | 'Approved' | 'Rejected' | 'Executed';

export interface Signal {
  id: string;
  symbol: TradingSymbol;
  strategy: SignalStrategy;
  side: TradeSide;
  timeframe: Timeframe;
  entry: number;
  sl: number;
  tp: number;
  confidence: number; // e.g. 82 (represents 82%)
  timestamp: string;
  age: string; // e.g. "2m ago"
  status: SignalStatus;
}
