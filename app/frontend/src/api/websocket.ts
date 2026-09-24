import { WebSocketConnectionState, WsEventType, WsMessage } from '../types/websocket';

import { API_BASE_URL } from './client';

/**
 * Derives the base WebSocket URL.
 * Prefers VITE_WS_BASE_URL if explicitly provided.
 * Otherwise derives ws:// or wss:// from API_BASE_URL.
 */
export function getWebSocketBaseUrl(): string {
  const envWsUrl = import.meta.env.VITE_WS_BASE_URL as string | undefined;
  if (envWsUrl && envWsUrl.trim().length > 0) {
    return envWsUrl.trim().replace(/\/+$/, '');
  }

  if (API_BASE_URL && API_BASE_URL.trim().length > 0) {
    try {
      // API_BASE_URL might be a relative path like '/api' in some setups
      // but in our current setup it's an absolute URL
      if (API_BASE_URL.startsWith('http')) {
        const parsed = new URL(API_BASE_URL.trim());
        const protocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${parsed.host}`;
      } else {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}`;
      }
    } catch {
      // Ignore URL parse error and proceed to fallback
    }
  }

  return '';
}


export interface WebSocketClientOptions {
  path?: string; // Must be '/ws/live'
  reconnectBaseDelayMs?: number; // Base delay in ms (default 2000)
  reconnectMaxDelayMs?: number; // Max backoff in ms (default 15000)
  duplicateWindowMs?: number; // Window for deduplication in ms (default 5000)
  onStatusChange?: (state: WebSocketConnectionState) => void;
}

export type EventHandler<T = unknown> = (payload: T, rawMessage: WsMessage<T>) => void;
type UnknownEventHandler = EventHandler<unknown>;

const WS_EVENT_TYPES = new Set<WsEventType>([
  'price_update',
  'signal_generated',
  'position_opened',
  'position_updated',
  'position_closed',
  'bot_status',
  'account_update',
  'system_event',
]);

/**
 * Isolated, robust WebSocket client for /ws/live
 * Features:
 * - Exponential backoff reconnection with jitter
 * - Connection state management (Connected, Reconnecting, Offline)
 * - Safe JSON parsing and malformed message protection
 * - Duplicate event filtering via message ID / hash cache
 * - Clean teardown and unsubscribe
 */
export class LiveWebSocketClient {
  private url: string;
  private ws: WebSocket | null = null;
  private connectionState: WebSocketConnectionState = 'Offline';
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private isIntentionallyClosed = false;

  private reconnectBaseDelayMs: number;
  private reconnectMaxDelayMs: number;
  private duplicateWindowMs: number;

  private listeners: Map<WsEventType | '*', Set<UnknownEventHandler>> = new Map();
  private statusListeners: Set<(state: WebSocketConnectionState) => void> = new Set();
  
  // Cache for recent event IDs / signatures to avoid processing duplicates
  private recentEventIds: Map<string, number> = new Map();

  constructor(options: WebSocketClientOptions = {}) {
    const baseUrl = getWebSocketBaseUrl();
    const path = options.path || '/ws/live';
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    this.url = baseUrl ? `${baseUrl}${cleanPath}` : '';

    this.reconnectBaseDelayMs = options.reconnectBaseDelayMs ?? 2000;
    this.reconnectMaxDelayMs = options.reconnectMaxDelayMs ?? 15000;
    this.duplicateWindowMs = options.duplicateWindowMs ?? 5000;

    if (options.onStatusChange) {
      this.statusListeners.add(options.onStatusChange);
    }
  }

  public getStatus(): WebSocketConnectionState {
    return this.connectionState;
  }

  public getUrl(): string {
    return this.url;
  }

  /**
   * Connect to /ws/live
   */
  public connect(): void {
    if (!this.url) {
      this.setConnectionState('Offline');
      return;
    }
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isIntentionallyClosed = false;
    this.clearReconnectTimer();

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.setConnectionState('Connected');
      };

      this.ws.onmessage = (event: MessageEvent) => {
        this.handleMessage(event.data);
      };

      this.ws.onerror = () => {
        // Handled through onclose for reconnection
      };

      this.ws.onclose = () => {
        this.ws = null;
        if (this.isIntentionallyClosed) {
          this.setConnectionState('Offline');
          return;
        }

        // Automatic reconnection handling
        this.setConnectionState('Reconnecting');
        this.scheduleReconnect();
      };
    } catch {
      // Safe fallback if constructor throws (e.g. invalid URL)
      this.setConnectionState('Offline');
      this.scheduleReconnect();
    }
  }

  /**
   * Intentionally close connection
   */
  public disconnect(): void {
    this.isIntentionallyClosed = true;
    this.clearReconnectTimer();

    if (this.ws) {
      try {
        this.ws.close(1000, 'Client disconnected');
      } catch {
        // Ignore close errors
      }
      this.ws = null;
    }

    this.setConnectionState('Offline');
  }

  /**
   * Subscribe to a specific event type or all events ('*')
   */
  public subscribe<T = unknown>(eventType: WsEventType | '*', handler: EventHandler<T>): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    const handlers = this.listeners.get(eventType)!;
    const wrappedHandler: UnknownEventHandler = (payload, rawMessage) => {
      handler(payload as T, rawMessage as WsMessage<T>);
    };
    handlers.add(wrappedHandler);

    return () => {
      handlers.delete(wrappedHandler);
      if (handlers.size === 0) {
        this.listeners.delete(eventType);
      }
    };
  }

  /**
   * Subscribe to connection status changes
   */
  public onStatusChange(callback: (state: WebSocketConnectionState) => void): () => void {
    this.statusListeners.add(callback);
    callback(this.connectionState);
    return () => {
      this.statusListeners.delete(callback);
    };
  }

  /**
   * Process raw message from WebSocket
   */
  private handleMessage(rawData: unknown): void {
    if (typeof rawData !== 'string') {
      return; // Ignore binary frames safely
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(rawData);
    } catch {
      // Silently ignore malformed non-JSON messages to protect UI
      return;
    }

    if (!parsed || typeof parsed !== 'object') {
      return;
    }
    const record = parsed as Record<string, unknown>;

    const rawEventType = record.event ?? record.type;
    if (typeof rawEventType !== 'string' || !WS_EVENT_TYPES.has(rawEventType as WsEventType)) {
      return;
    }
    const eventType = rawEventType as WsEventType;

    const payload = record.data !== undefined
      ? record.data
      : record.payload !== undefined
      ? record.payload
      : record;

    const explicitEventId = typeof record.event_id === 'string'
      ? record.event_id
      : typeof record.id === 'string'
      ? record.id
      : null;
    const eventId = explicitEventId || (record.timestamp
      ? `${eventType}-${String(record.timestamp)}-${JSON.stringify(payload).slice(0, 40)}`
      : null);
    if (eventId && this.isDuplicate(eventId)) {
      return;
    }

    const rawMessage: WsMessage = {
      event: eventType,
      data: payload,
      timestamp:
        typeof record.timestamp === 'string' || typeof record.timestamp === 'number'
          ? record.timestamp
          : undefined,
      event_id: explicitEventId ?? undefined,
    };
    this.dispatchEvent(eventType, payload, rawMessage);
  }

  private isDuplicate(eventId: string): boolean {
    const now = Date.now();
    this.cleanDuplicateCache(now);

    if (this.recentEventIds.has(eventId)) {
      return true;
    }

    this.recentEventIds.set(eventId, now);
    return false;
  }

  private cleanDuplicateCache(now: number): void {
    for (const [id, time] of this.recentEventIds.entries()) {
      if (now - time > this.duplicateWindowMs) {
        this.recentEventIds.delete(id);
      }
    }
  }

  private dispatchEvent(event: WsEventType, payload: unknown, rawMessage: WsMessage): void {
    // Specific handlers
    const specificHandlers = this.listeners.get(event);
    if (specificHandlers) {
      specificHandlers.forEach((handler) => {
        try {
          handler(payload, rawMessage);
        } catch {
          // Prevent user handler errors from breaking WebSocket receiver
        }
      });
    }

    // Wildcard handlers
    const wildcardHandlers = this.listeners.get('*');
    if (wildcardHandlers) {
      wildcardHandlers.forEach((handler) => {
        try {
          handler(payload, rawMessage);
        } catch {
          // Prevent user handler errors from breaking WebSocket receiver
        }
      });
    }
  }

  private setConnectionState(newState: WebSocketConnectionState): void {
    if (this.connectionState === newState) return;
    this.connectionState = newState;
    this.statusListeners.forEach((listener) => {
      try {
        listener(newState);
      } catch {
        // Prevent listener errors
      }
    });
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();

    this.reconnectAttempts += 1;
    // Exponential backoff with jitter
    const delay = Math.min(
      this.reconnectMaxDelayMs,
      this.reconnectBaseDelayMs * Math.pow(1.5, Math.min(this.reconnectAttempts, 6)) +
        Math.random() * 800
    );

    this.reconnectTimer = setTimeout(() => {
      if (!this.isIntentionallyClosed) {
        this.connect();
      }
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
