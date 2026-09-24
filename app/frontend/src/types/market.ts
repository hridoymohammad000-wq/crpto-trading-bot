export type TradingSymbol = string;

export type Timeframe = '1m' | '5m' | '15m';

export interface SymbolTickerInfo {
  symbol: TradingSymbol;
  name: string;
  price: number;
  change24h: number;
  high24h: number;
  low24h: number;
  volume24h: string;
}
