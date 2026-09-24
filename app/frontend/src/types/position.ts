import { TradingSymbol } from './market';

export type PositionSide = 'LONG' | 'SHORT';

export interface Position {
  id: string;
  symbol: TradingSymbol;
  side: PositionSide;
  entry: number;
  current: number;
  quantity: number;
  positionValue: number;
  sl: number;
  tp: number;
  unrealizedPnl: number;
  pnlPercentage: number;
  currentR: string; // e.g. "+1.04R"
  duration: string;
  leverage: number;
  riskAmount: number;
  openedTime: string;
}
