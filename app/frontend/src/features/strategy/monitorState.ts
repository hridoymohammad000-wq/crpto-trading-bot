import type { StrategyDiagnostic, TradingSymbol } from '../../types';

export const STRATEGY_SYMBOLS: readonly TradingSymbol[] = [
  'BTCUSDT',
  'ETHUSDT',
  'SOLUSDT',
];

export interface StrategyMonitorItem {
  data: StrategyDiagnostic | null;
  isLoading: boolean;
  errorMessage: string | null;
  lastSuccessfulAt: string | null;
}

export type StrategyMonitorState = Record<TradingSymbol, StrategyMonitorItem>;

export interface StrategyFetchOutcome {
  symbol: TradingSymbol;
  data: StrategyDiagnostic | null;
  errorMessage: string | null;
}

export type StrategyFetcher = (symbol: TradingSymbol) => Promise<StrategyDiagnostic>;

export function createInitialMonitorState(): StrategyMonitorState {
  return Object.fromEntries(
    STRATEGY_SYMBOLS.map((symbol) => [
      symbol,
      {
        data: null,
        isLoading: true,
        errorMessage: null,
        lastSuccessfulAt: null,
      },
    ]),
  ) as StrategyMonitorState;
}

export async function fetchStrategyOutcomes(
  fetcher: StrategyFetcher,
): Promise<StrategyFetchOutcome[]> {
  return Promise.all(
    STRATEGY_SYMBOLS.map(async (symbol) => {
      try {
        return { symbol, data: await fetcher(symbol), errorMessage: null };
      } catch (error: unknown) {
        return {
          symbol,
          data: null,
          errorMessage:
            error instanceof Error ? error.message : 'Unable to evaluate this symbol.',
        };
      }
    }),
  );
}

export function mergeStrategyOutcomes(
  previous: StrategyMonitorState,
  outcomes: StrategyFetchOutcome[],
  completedAt: string,
): StrategyMonitorState {
  const next = { ...previous };
  for (const outcome of outcomes) {
    const current = previous[outcome.symbol];
    next[outcome.symbol] = outcome.data
      ? {
          data: outcome.data,
          isLoading: false,
          errorMessage: null,
          lastSuccessfulAt: completedAt,
        }
      : {
          ...current,
          isLoading: false,
          errorMessage: outcome.errorMessage ?? 'Unable to evaluate this symbol.',
        };
  }
  return next;
}
