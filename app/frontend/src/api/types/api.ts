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
  status: 'ok' | 'unhealthy' | 'degraded';
  backend_healthy: boolean;
  bybit_connected: boolean;
  db_healthy: boolean;
  scanner_running: boolean;
  position_manager_running: boolean;
  bot_status: string;
  uptime_seconds: number;
  last_scan_at: string | null;
  last_reconciled_at: string | null;
  last_signal_time: string | null;
  last_order_time: string | null;
  open_positions: number;
  watchdog_running?: boolean;
  watchdog_last_check?: string | null;
  watchdog_last_success?: string | null;
  watchdog_active_incidents?: string[];
  watchdog_last_alert?: string | null;
  watchdog_last_recovery?: string | null;
  critical_states: {
    bybit_disconnected: boolean;
    scanner_stalled: boolean;
    db_write_failure: boolean;
    stale_reconciliation: boolean;
    manager_inactive_with_positions?: boolean;
    repeated_be_failure?: boolean;
  };
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
