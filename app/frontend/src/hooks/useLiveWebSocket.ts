import { useEffect, useRef, useState } from 'react';
import { LiveWebSocketClient } from '../api/websocket';
import {
  AccountUpdatePayload,
  BotStatusPayload,
  PositionClosedPayload,
  PositionOpenedPayload,
  PositionUpdatedPayload,
  PriceUpdatePayload,
  SignalGeneratedPayload,
  SystemEventPayload,
  WebSocketConnectionState,
  WsEventType,
} from '../types/websocket';

export interface UseLiveWebSocketOptions {
  onPriceUpdate?: (payload: PriceUpdatePayload) => void;
  onSignalGenerated?: (payload: SignalGeneratedPayload) => void;
  onPositionOpened?: (payload: PositionOpenedPayload) => void;
  onPositionUpdated?: (payload: PositionUpdatedPayload) => void;
  onPositionClosed?: (payload: PositionClosedPayload) => void;
  onBotStatus?: (payload: BotStatusPayload) => void;
  onAccountUpdate?: (payload: AccountUpdatePayload) => void;
  onSystemEvent?: (payload: SystemEventPayload) => void;
  autoConnect?: boolean;
}

export interface UseLiveWebSocketReturn {
  connectionState: WebSocketConnectionState;
  reconnect: () => void;
  disconnect: () => void;
  wsUrl: string;
  lastEventTime: Date | null;
  lastEventType: WsEventType | null;
}

/**
 * React hook for consuming /ws/live real-time events.
 * Manages WebSocket connection lifecycle, states, and event listeners.
 */
export function useLiveWebSocket(options: UseLiveWebSocketOptions = {}): UseLiveWebSocketReturn {
  const {
    onPriceUpdate,
    onSignalGenerated,
    onPositionOpened,
    onPositionUpdated,
    onPositionClosed,
    onBotStatus,
    onAccountUpdate,
    onSystemEvent,
    autoConnect = false,
  } = options;

  const [connectionState, setConnectionState] = useState<WebSocketConnectionState>('Offline');
  const [lastEventTime, setLastEventTime] = useState<Date | null>(null);
  const [lastEventType, setLastEventType] = useState<WsEventType | null>(null);

  const clientRef = useRef<LiveWebSocketClient | null>(null);

  // Store latest handlers in refs to avoid re-subscribing on each render
  const handlersRef = useRef({
    onPriceUpdate,
    onSignalGenerated,
    onPositionOpened,
    onPositionUpdated,
    onPositionClosed,
    onBotStatus,
    onAccountUpdate,
    onSystemEvent,
  });

  useEffect(() => {
    handlersRef.current = {
      onPriceUpdate,
      onSignalGenerated,
      onPositionOpened,
      onPositionUpdated,
      onPositionClosed,
      onBotStatus,
      onAccountUpdate,
      onSystemEvent,
    };
  });

  useEffect(() => {
    // Instantiate WebSocket Client
    const client = new LiveWebSocketClient({
      path: '/ws/live',
      reconnectBaseDelayMs: 2000,
      reconnectMaxDelayMs: 15000,
    });
    clientRef.current = client;

    // Listen for state changes
    const unsubStatus = client.onStatusChange((state) => {
      setConnectionState(state);
    });

    // Register approved event handlers
    const unsubPrice = client.subscribe<PriceUpdatePayload>('price_update', (payload) => {
      setLastEventTime(new Date());
      setLastEventType('price_update');
      handlersRef.current.onPriceUpdate?.(payload);
    });

    const unsubSignal = client.subscribe<SignalGeneratedPayload>('signal_generated', (payload) => {
      setLastEventTime(new Date());
      setLastEventType('signal_generated');
      handlersRef.current.onSignalGenerated?.(payload);
    });

    const unsubPosOpened = client.subscribe<PositionOpenedPayload>('position_opened', (payload) => {
      setLastEventTime(new Date());
      setLastEventType('position_opened');
      handlersRef.current.onPositionOpened?.(payload);
    });

    const unsubPosUpdated = client.subscribe<PositionUpdatedPayload>('position_updated', (payload) => {
      setLastEventTime(new Date());
      setLastEventType('position_updated');
      handlersRef.current.onPositionUpdated?.(payload);
    });

    const unsubPosClosed = client.subscribe<PositionClosedPayload>('position_closed', (payload) => {
      setLastEventTime(new Date());
      setLastEventType('position_closed');
      handlersRef.current.onPositionClosed?.(payload);
    });

    const unsubBot = client.subscribe<BotStatusPayload>('bot_status', (payload) => {
      setLastEventTime(new Date());
      setLastEventType('bot_status');
      handlersRef.current.onBotStatus?.(payload);
    });

    const unsubAccount = client.subscribe<AccountUpdatePayload>('account_update', (payload) => {
      setLastEventTime(new Date());
      setLastEventType('account_update');
      handlersRef.current.onAccountUpdate?.(payload);
    });

    const unsubSystem = client.subscribe<SystemEventPayload>('system_event', (payload) => {
      setLastEventTime(new Date());
      setLastEventType('system_event');
      handlersRef.current.onSystemEvent?.(payload);
    });

    if (autoConnect) {
      client.connect();
    }

    return () => {
      unsubStatus();
      unsubPrice();
      unsubSignal();
      unsubPosOpened();
      unsubPosUpdated();
      unsubPosClosed();
      unsubBot();
      unsubAccount();
      unsubSystem();
      client.disconnect();
      clientRef.current = null;
    };
  }, [autoConnect]);

  const reconnect = () => {
    clientRef.current?.connect();
  };

  const disconnect = () => {
    clientRef.current?.disconnect();
  };

  return {
    connectionState,
    reconnect,
    disconnect,
    wsUrl: clientRef.current?.getUrl() || '',
    lastEventTime,
    lastEventType,
  };
}
