import { Position } from '../types';
import { apiClient } from './client';
import { RequestOptions } from './types';

/**
 * Retrieves the current open positions from the real backend.
 */
export async function getPositions(options?: RequestOptions): Promise<Position[]> {
  return apiClient.get<Position[]>('/positions', options);
}
