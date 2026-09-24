import { apiClient } from './client';

export interface AIStatus {
  enabled: boolean;
  configured: boolean;
  provider: string;
  model: string;
  mode: 'analysis_only';
}

export interface AIAnalysisResponse {
  analysis: string;
  provider: string;
  model: string;
  mode: 'analysis_only';
}

export async function getAIStatus(): Promise<AIStatus> {
  return apiClient.get<AIStatus>('/ai/status');
}

export async function requestAIAnalysis(context: Record<string, unknown>, question?: string): Promise<AIAnalysisResponse> {
  return apiClient.post<AIAnalysisResponse>('/ai/analyze', { context, question });
}
