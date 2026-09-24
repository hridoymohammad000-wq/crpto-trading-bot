import { Timeframe, TradingSymbol } from './market';

export type StrategyKey = 'emaRsi' | 'bollingerSqueeze';

export interface BotSettings {
  strategies: Record<StrategyKey, boolean>;
  riskPerTrade: number;
  symbols: TradingSymbol[];
  timeframes: Timeframe[];
  spreadFilterThreshold: number;
  volatilityFilterEnabled: boolean;
  maxOpenPositions: number;
  mode: 'DEMO';
}

export type BotSettingsErrors = Partial<
  Record<'strategies' | 'riskPerTrade' | 'symbols' | 'timeframes' | 'spreadFilterThreshold' | 'maxOpenPositions', string>
>;
