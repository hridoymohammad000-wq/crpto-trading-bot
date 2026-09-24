import { apiClient } from './client';
import { parseBotStatusResponse } from './status';
import {
  BotStartResponse,
  BotStopResponse,
  RequestOptions,
} from './types';

/**
 * Bot Lifecycle Control API Module
 * Endpoints:
 * - POST /bot/start
 * - POST /bot/stop
 */

/**
 * Sends a request to start the trading bot on the backend.
 * Endpoint: POST /bot/start
 */
export async function startBot(options?: RequestOptions): Promise<BotStartResponse> {
  return parseBotStatusResponse(await apiClient.post<unknown>('/bot/start', undefined, options));
}

/**
 * Sends a request to stop the trading bot on the backend.
 * Endpoint: POST /bot/stop
 */
export async function stopBot(options?: RequestOptions): Promise<BotStopResponse> {
  return parseBotStatusResponse(await apiClient.post<unknown>('/bot/stop', undefined, options));
}

export const botApi = {
  startBot,
  stopBot,
};
