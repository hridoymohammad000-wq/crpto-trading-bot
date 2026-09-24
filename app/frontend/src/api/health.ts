import { ApiClientError, apiClient } from './client';
import { HealthCheckResponse, RequestOptions } from './types';

/**
 * Health Check API Module
 * Endpoint: GET /health
 */
export async function getHealth(options?: RequestOptions): Promise<HealthCheckResponse> {
  const response = await apiClient.get<unknown>('/health', options);
  if (!response || typeof response !== 'object' || !('status' in response) || response.status !== 'ok') {
    throw new ApiClientError('Invalid response from GET /health.', undefined, 'INVALID_RESPONSE');
  }
  return { status: 'ok' };
}

export const healthApi = {
  getHealth,
};
