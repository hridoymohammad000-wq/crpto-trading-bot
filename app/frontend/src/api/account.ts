import { AccountSummary } from '../types';
import { apiClient } from './client';
import { RequestOptions } from './types';

/**
 * Retrieves the current account summary from the real backend.
 */
export async function getAccount(options?: RequestOptions): Promise<AccountSummary> {
  return apiClient.get<AccountSummary>('/account', options);
}

export async function getReconciliation(options?: RequestOptions): Promise<any> {
  return apiClient.get<any>('/account/reconciliation', options);
}
