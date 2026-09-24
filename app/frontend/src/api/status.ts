import { ApiClientError, apiClient } from './client';
import { BackendStatusResponse, RequestOptions } from './types';

/**
 * Backend Bot Status API Module
 * Endpoint: GET /status
 */
export async function getStatus(options?: RequestOptions): Promise<BackendStatusResponse> {
  return parseBotStatusResponse(await apiClient.get<unknown>('/status', options));
}

export const statusApi = {
  getStatus,
};
export function parseBotStatusResponse(response: unknown): BackendStatusResponse {
  if (!response || typeof response !== 'object' || !('bot_status' in response)) {
    throw new ApiClientError('Invalid bot status response.', undefined, 'INVALID_RESPONSE');
  }
  const botStatus = response.bot_status;
  if (botStatus !== 'running' && botStatus !== 'stopped') {
    throw new ApiClientError('Unsupported bot_status value.', undefined, 'INVALID_RESPONSE');
  }
  return { bot_status: botStatus };
}
