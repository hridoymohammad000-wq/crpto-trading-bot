import { apiClient } from './client';

export interface IntegrationStatusResponse {
  backend: { status: 'connected' };
  bybit: { configured: boolean; demo: boolean };
  telegram: { configured: boolean };
  ai: { enabled: boolean; configured: boolean; provider: string; model: string };
}

export async function getIntegrationStatus(): Promise<IntegrationStatusResponse> {
  return apiClient.get<IntegrationStatusResponse>('/integrations/status');
}
