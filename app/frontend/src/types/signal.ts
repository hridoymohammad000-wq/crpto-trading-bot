import { Timeframe, TradingSymbol } from './market';

export type TradeSide = 'BUY' | 'SELL';

export type SignalStrategy = 'EMA + RSI' | 'Bollinger Squeeze' | 'VWAP Pullback';

export type SignalStatus = 'New' | 'Approved' | 'Rejected' | 'Executed' | 'Expired';

export interface Signal {
  id: string;
  symbol: TradingSymbol;
  strategy: SignalStrategy;
  side: TradeSide;
  timeframe: Timeframe;
  entry: number;
  sl: number;
  tp: number;
  confidence: number;
  timestamp: string;
  age: string;
  status: SignalStatus;
  
  // New TTL properties
  signalTime: string;
  expiresAt: string;
  isExpired: boolean;
  ageSeconds: number;
}
