import { BotStatus } from './bot';
import { Position } from './position';
import { Signal } from './signal';

/**
 * WebSocket Connection State
 * - Connected: WebSocket connection established and active
 * - Reconnecting: Disconnected, automatically retrying with backoff
 * - Offline: WebSocket disconnected / server unreachable
 */
export type WebSocketConnectionState = 'Connected' | 'Reconnecting' | 'Offline';

/**
 * Approved backend WebSocket event types as defined in specifications:
 * - price_update
 * - signal_generated
 * - position_opened
 * - position_updated
 * - position_closed
 * - bot_status
 * - account_update
 * - system_event
 */
export type WsEventType =
  | 'price_update'
  | 'signal_generated'
  | 'position_opened'
  | 'position_updated'
  | 'position_closed'
  | 'bot_status'
  | 'account_update'
  | 'system_event';

export interface PriceUpdatePayload {
  symbol: string;
  price: number;
  change24h?: number;
  high24h?: number;
  low24h?: number;
  volume24h?: string | number;
  timestamp?: number | string;
}

export interface SignalGeneratedPayload {
  signal: Signal;
  timestamp?: number | string;
}

export interface PositionOpenedPayload {
  position: Position;
  timestamp?: number | string;
}

export interface PositionUpdatedPayload {
  id?: string;
  symbol?: string;
  position?: Partial<Position>;
  current?: number;
  unrealizedPnl?: number;
  pnlPercentage?: number;
  currentR?: string;
  sl?: number;
  tp?: number;
  timestamp?: number | string;
}

export interface PositionClosedPayload {
  id?: string;
  symbol?: string;
  exitPrice?: number;
  realizedPnl?: number;
  pnlPercentage?: number;
  closeReason?: string;
  timestamp?: number | string;
}

export interface BotStatusPayload {
  status: BotStatus;
  isAutomatedExecutionEnabled?: boolean;
  activeStrategyCount?: number;
  message?: string;
  timestamp?: number | string;
}

export interface AccountUpdatePayload {
  balance?: number;
  equity?: number;
  availableBalance?: number;
  available_balance?: number;
  dailyPnl?: number;
  daily_pnl?: number;
  dailyPnlPercentage?: number;
  daily_pnl_percentage?: number;
  timestamp?: number | string;
}

export interface SystemEventPayload {
  event_id?: string;
  id?: string;
  type?: string;
  level?: 'info' | 'warning' | 'error' | 'success';
  message: string;
  details?: unknown;
  timestamp?: number | string;
}

/**
 * Generic WebSocket envelope received from /ws/live
 */
export interface WsMessage<T = unknown> {
  event?: WsEventType;
  type?: WsEventType; // Some backend patterns use 'type'
  data?: T;
  payload?: T; // Some backend patterns use 'payload'
  timestamp?: number | string;
  event_id?: string;
}
