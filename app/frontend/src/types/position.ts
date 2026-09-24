import { TradingSymbol } from './market';

export type PositionSide = 'LONG' | 'SHORT';

export interface Position {
  id: string;
  symbol: TradingSymbol;
  side: PositionSide;
  entry: number | null | undefined;
  current: number | null | undefined;
  quantity: number | null | undefined;
  positionValue: number | null | undefined;
  sl: number | null | undefined;
  tp: number | null | undefined;
  unrealizedPnl: number | null | undefined;
  pnlPercentage: number | null | undefined;
  currentR: string | null | undefined;
  duration: string | null | undefined;
  leverage: number | null | undefined;
  riskAmount: number | null | undefined;
  openedTime: string | null | undefined;
}
