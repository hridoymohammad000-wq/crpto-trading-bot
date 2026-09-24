/**
 * Core API Types and Contract Definitions
 * Typed request/response models for the FastAPI trading bot backend.
 */

// ==========================================
// 1. Common API & Request State Models
// ==========================================

export interface ApiError {
  message: string;
  status?: number;
  code?: string;
  details?: unknown;
}

export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  params?: Record<string, string | number | boolean | undefined>;
}

// ==========================================
// 2. Health Endpoint Models (GET /health)
// ==========================================

export interface HealthCheckResponse {
  status: 'ok';
}

// ==========================================
// 3. Status Endpoint Models (GET /status)
// ==========================================

export type BackendBotState = 'running' | 'stopped';

export interface BackendStatusResponse {
  bot_status: BackendBotState;
}

// ==========================================
// 4. Bot Lifecycle Models (POST /bot/start, POST /bot/stop)
// ==========================================

export type BotStartResponse = BackendStatusResponse;
export type BotStopResponse = BackendStatusResponse;

/** Local table pagination metadata. */
export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
  totalPages: number;
  hasNextPage: boolean;
  hasPrevPage: boolean;
}
