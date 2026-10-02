import { ApiClientError, apiClient } from './client';
import { HealthCheckResponse, RequestOptions } from './types';

/**
 * Health Check API Module
 * Endpoint: GET /health
 */
export async function getHealth(options?: RequestOptions): Promise<HealthCheckResponse> {
  const response = await apiClient.get<HealthCheckResponse>('/health', options);
  if (!response || typeof response !== 'object' || !('status' in response)) {
    throw new ApiClientError('Invalid response from GET /health.', undefined, 'INVALID_RESPONSE');
  }
  return response;
}

export const healthApi = {
  getHealth,
};
