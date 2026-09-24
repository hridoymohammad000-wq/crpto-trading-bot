import type { RequestOptions } from './types';
import type { StrategyDiagnostic } from '../types/strategy';
import type { TradingSymbol } from '../types/market';
import { apiClient } from './client';
import { parseStrategyDiagnostic } from './strategyContract';

export async function getStrategyEvaluation(
  symbol: TradingSymbol,
  options?: RequestOptions,
): Promise<StrategyDiagnostic> {
  const response = await apiClient.get<unknown>('/strategy/evaluate', {
    ...options,
    params: { ...options?.params, symbol },
  });
  return parseStrategyDiagnostic(response);
}

export const strategyApi = { getStrategyEvaluation };
