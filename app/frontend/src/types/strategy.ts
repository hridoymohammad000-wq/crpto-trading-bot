import type { TradingSymbol } from './market';

export type StrategyResult = 'SIGNAL' | 'NO_SIGNAL';
export type StrategySide = 'BUY' | 'SELL';
export type StrategyName = 'EMA_RSI_ADX_MOMENTUM';

export type StrategyReasonCode =
  | 'NO_CROSSOVER'
  | 'ENTRY_WINDOW_EXPIRED'
  | 'RSI_FILTER_FAILED'
  | 'ADX_FILTER_FAILED'
  | 'VOLUME_FILTER_FAILED'
  | 'CANDLE_CONFIRMATION_FAILED'
  | 'HTF_TREND_FAILED'
  | 'HTF_SLOPE_FAILED'
  | 'INSUFFICIENT_DATA'
  | 'DUPLICATE_SETUP';

export interface StrategyIndicators {
  emaFast: number | null;
  emaSlow: number | null;
  rsi: number | null;
  adx: number | null;
  volume: number | null;
  averageVolume: number | null;
  higherTfEmaFast: number | null;
  higherTfEmaSlow: number | null;
  higherTfEmaFastPrevious: number | null;
}

export interface StrategyDiagnostic {
  symbol: TradingSymbol;
  strategy: StrategyName;
  evaluationTime: string;
  latest5mCandleTime: string | null;
  latest15mCandleTime: string | null;
  result: StrategyResult;
  side: StrategySide | null;
  referenceEntryPrice: number | null;
  confidence: number | null;
  reasonCodes: StrategyReasonCode[];
  indicators: StrategyIndicators;
  crossoverAgeCandles: number | null;
  duplicateSetup: boolean;
}
