import { Timeframe, TradingSymbol } from './market';
import { PositionSide } from './position';
import { SignalStrategy } from './signal';

export type TradeResult = 'Win' | 'Loss' | 'Breakeven';

export interface Trade {
  id: string;
  symbol: TradingSymbol;
  side: PositionSide;
  strategy: SignalStrategy;
  timeframe: Timeframe;
  entry: number;
  exit: number;
  sl: number;
  tp: number;
  pnl: number;
  pnlPercentage: number;
  rr: string;
  duration: string;
  result: TradeResult;
  closedAt: string;
  closedAtISO?: string;
}
