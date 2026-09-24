import { useCallback, useState } from 'react';
import {
  AccountSummary,
  NavigationTab,
  Position,
  Signal,
  SymbolTickerInfo,
  Timeframe,
  TradingSymbol,
} from '../types';
import {
  AccountUpdatePayload,
  BotStatusPayload,
  PositionClosedPayload,
  PositionOpenedPayload,
  PositionUpdatedPayload,
  PriceUpdatePayload,
  SignalGeneratedPayload,
  SystemEventPayload,
} from '../types/websocket';
import { useAccountData } from './useAccountData';
import { useBotBackend } from './useBotBackend';
import { useLiveWebSocket } from './useLiveWebSocket';
import { usePerformanceData } from './usePerformanceData';
import { usePositionsData } from './usePositionsData';
import { useReconciliation } from './useReconciliation';
import { useSignalsData } from './useSignalsData';
import { useTradesData } from './useTradesData';

export function useDashboard() {
  const [currentTab, setCurrentTab] = useState<NavigationTab>('Dashboard');
  const [selectedSymbol, setSelectedSymbol] = useState<TradingSymbol>('BTCUSDT');
  const [selectedTimeframe, setSelectedTimeframe] = useState<Timeframe>('5m');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // Position detail modal inspection state
  const [selectedPosition, setSelectedPosition] = useState<Position | null>(null);

  // Bot backend API integration hook (REST health and status)
  const botBackend = useBotBackend();

  // Connected Read-Only Trading Data Hooks
  const accountData = useAccountData();
  const positionsData = usePositionsData();
  const reconData = useReconciliation();
  const signalsData = useSignalsData();
  const tradesData = useTradesData();
  const performanceData = usePerformanceData();

  // Real-time state overrides driven by WebSocket /ws/live events
  const [wsPositions, setWsPositions] = useState<Position[]>([]);
  const [wsSignals, setWsSignals] = useState<Signal[]>([]);
  const [liveTickerData, setLiveTickerData] = useState<Record<string, SymbolTickerInfo>>({});
  const [liveAccountDelta, setLiveAccountDelta] = useState<Partial<AccountSummary> | null>(null);
  // Live prices map: symbol → latest WS price. Used to tick PnL for REST-loaded positions.
  const [livePrices, setLivePrices] = useState<Record<string, number>>({});
  const [systemNotification, setSystemNotification] = useState<string | null>(null);

  // WebSocket Event Handlers:
  // 1. price_update
  const handlePriceUpdate = useCallback((payload: PriceUpdatePayload) => {
    if (!payload || !payload.symbol || typeof payload.price !== 'number') return;
    const sym = payload.symbol;
    setLiveTickerData((prev) => {
      const existing = prev[sym] || {
        symbol: sym as TradingSymbol,
        name: `${sym.replace('USDT', '')} / TetherUS`,
        price: payload.price,
        change24h: 0,
        high24h: payload.price,
        low24h: payload.price,
        volume24h: '0',
      };

      return {
        ...prev,
        [sym]: {
          ...existing,
          price: payload.price,
          change24h: typeof payload.change24h === 'number' ? payload.change24h : existing.change24h,
          high24h: typeof payload.high24h === 'number' ? payload.high24h : Math.max(existing.high24h, payload.price),
          low24h: typeof payload.low24h === 'number' ? payload.low24h : Math.min(existing.low24h, payload.price),
          volume24h: payload.volume24h !== undefined ? String(payload.volume24h) : existing.volume24h,
        },
      };
    });

    // Update PnL for any WebSocket-tracked open positions for this symbol
    setWsPositions((prevPositions) => {
      let hasChange = false;
      const updated = prevPositions.map((pos) => {
        if (pos.symbol === sym) {
          hasChange = true;
          const currentPrice = payload.price;
          const entry = pos.entry || 0;
          const qty = pos.quantity || 0;
          if (!entry || !qty) return { ...pos, current: currentPrice };
          const isLong = pos.side === 'LONG';
          const pnl = isLong
            ? (currentPrice - entry) * qty
            : (entry - currentPrice) * qty;
          const pnlPct = (pnl / (entry * qty)) * 100 * (pos.leverage || 1);
          return {
            ...pos,
            current: currentPrice,
            unrealizedPnl: Math.round(pnl * 100) / 100,
            pnlPercentage: Math.round(pnlPct * 100) / 100,
          };
        }
        return pos;
      });
      return hasChange ? updated : prevPositions;
    });


    // Also store the live price for ticking REST-loaded positions
    setLivePrices((prev) => ({ ...prev, [sym]: payload.price }));
  }, []);

  // 2. signal_generated
  const handleSignalGenerated = useCallback((payload: SignalGeneratedPayload) => {
    if (!payload || !payload.signal) return;
    const newSignal = payload.signal;
    setWsSignals((prev) => {
      // Prevent duplicate signal ids
      if (prev.some((s) => s.id === newSignal.id)) return prev;
      return [newSignal, ...prev.slice(0, 49)];
    });
  }, []);

  // 3. position_opened
  const handlePositionOpened = useCallback((payload: PositionOpenedPayload) => {
    if (!payload || !payload.position) return;
    const newPos = payload.position;
    setWsPositions((prev) => {
      const currentList = prev;
      if (currentList.some((p) => p.id === newPos.id)) return currentList;
      return [newPos, ...currentList];
    });
  }, []);

  // 4. position_updated
  const handlePositionUpdated = useCallback((payload: PositionUpdatedPayload) => {
    if (!payload) return;
    setWsPositions((prev) => {
      const currentList = prev;
      return currentList.map((pos) => {
        const matches =
          (payload.id && pos.id === payload.id) ||
          (payload.symbol && pos.symbol === payload.symbol);
        if (!matches) return pos;

        const merged: Position = {
          ...pos,
          ...(payload.position || {}),
          current: payload.current !== undefined ? payload.current : pos.current,
          unrealizedPnl: payload.unrealizedPnl !== undefined ? payload.unrealizedPnl : pos.unrealizedPnl,
          pnlPercentage: payload.pnlPercentage !== undefined ? payload.pnlPercentage : pos.pnlPercentage,
          currentR: payload.currentR !== undefined ? payload.currentR : pos.currentR,
          sl: payload.sl !== undefined ? payload.sl : pos.sl,
          tp: payload.tp !== undefined ? payload.tp : pos.tp,
        };
        return merged;
      });
    });
  }, []);

  // 5. position_closed
  const handlePositionClosed = useCallback((payload: PositionClosedPayload) => {
    if (!payload) return;
    setWsPositions((prev) => {
      const currentList = prev;
      return currentList.filter((pos) => {
        if (payload.id && pos.id === payload.id) return false;
        if (payload.symbol && !payload.id && pos.symbol === payload.symbol) return false;
        return true;
      });
    });
  }, []);

  // 6. bot_status
  const handleBotStatus = useCallback((payload: BotStatusPayload) => {
    if (!payload || !payload.status) return;
    // Trigger background refresh of bot status details
    botBackend.refreshStatus();
  }, [botBackend]);

  // 7. account_update
  const handleAccountUpdate = useCallback((payload: AccountUpdatePayload) => {
    if (!payload) return;
    setLiveAccountDelta((prev) => ({
      ...prev,
      balance: typeof payload.balance === 'number' ? payload.balance : prev?.balance,
      equity: typeof payload.equity === 'number' ? payload.equity : prev?.equity,
      availableBalance:
        typeof payload.availableBalance === 'number'
          ? payload.availableBalance
          : typeof payload.available_balance === 'number'
          ? payload.available_balance
          : prev?.availableBalance,
      dailyPnl:
        typeof payload.dailyPnl === 'number'
          ? payload.dailyPnl
          : typeof payload.daily_pnl === 'number'
          ? payload.daily_pnl
          : prev?.dailyPnl,
      dailyPnlPercentage:
        typeof payload.dailyPnlPercentage === 'number'
          ? payload.dailyPnlPercentage
          : typeof payload.daily_pnl_percentage === 'number'
          ? payload.daily_pnl_percentage
          : prev?.dailyPnlPercentage,
    }));
  }, []);

  // 8. system_event
  const handleSystemEvent = useCallback((payload: SystemEventPayload) => {
    if (!payload || !payload.message) return;
    setSystemNotification(payload.message);
    setTimeout(() => {
      setSystemNotification((curr) => (curr === payload.message ? null : curr));
    }, 6000);
  }, []);

  // Live WebSocket Connection Hook connecting to /ws/live
  const liveWs = useLiveWebSocket({
    onPriceUpdate: handlePriceUpdate,
    onSignalGenerated: handleSignalGenerated,
    onPositionOpened: handlePositionOpened,
    onPositionUpdated: handlePositionUpdated,
    onPositionClosed: handlePositionClosed,
    onBotStatus: handleBotStatus,
    onAccountUpdate: handleAccountUpdate,
    onSystemEvent: handleSystemEvent,
    autoConnect: true,
  });

  // Merge REST positions and WebSocket positions, then apply live price overrides to all
  const mergedPositions: Position[] = wsPositions.length > 0
    ? [...wsPositions, ...positionsData.positions.filter((p) => !wsPositions.some((ws) => ws.id === p.id))]
    : positionsData.positions;

  // Apply real-time price ticks from WebSocket to any position whose symbol has a live price
  const displayedPositions: Position[] = mergedPositions.map((pos) => {
    const livePrice = livePrices[pos.symbol];
    if (livePrice === undefined || livePrice === pos.current) return pos;
    const entry = pos.entry || 0;
    const qty = pos.quantity || 0;
    if (!entry || !qty) return { ...pos, current: livePrice };
    const isLong = pos.side === 'LONG';
    const pnl = isLong
      ? (livePrice - entry) * qty
      : (entry - livePrice) * qty;
    const pnlPct = (pnl / (entry * qty)) * 100 * (pos.leverage || 1);
    return {
      ...pos,
      current: livePrice,
      unrealizedPnl: Math.round(pnl * 100) / 100,
      pnlPercentage: Math.round(pnlPct * 100) / 100,
    };
  });


  // Signals feed: merges WebSocket signals on top of REST signals
  const combinedSignals: Signal[] = wsSignals.length > 0
    ? [...wsSignals, ...signalsData.signals.filter((s) => !wsSignals.some((ws) => ws.id === s.id))]
    : signalsData.signals;
  const displayedSignals: Signal[] = combinedSignals;

  // Account balances: WebSocket delta > Reconciliation data > REST /account.
  // Daily PnL strictly comes from account delta or /account — never from unrealized_pnl.
  const realBalance = liveAccountDelta?.balance !== undefined
    ? liveAccountDelta.balance
    : reconData.data?.wallet?.balance !== undefined
    ? reconData.data.wallet.balance
    : accountData.data?.balance;
  const realEquity = liveAccountDelta?.equity !== undefined
    ? liveAccountDelta.equity
    : reconData.data?.wallet?.equity !== undefined
    ? reconData.data.wallet.equity
    : accountData.data?.equity;
  const realAvailable = liveAccountDelta?.availableBalance !== undefined
    ? liveAccountDelta.availableBalance
    : reconData.data?.wallet?.available_trading_capacity !== undefined
    ? reconData.data.wallet.available_trading_capacity
    : reconData.data?.wallet?.available !== undefined
    ? reconData.data.wallet.available
    : (accountData.data as any)?.available_trading_capacity !== undefined
    ? (accountData.data as any).available_trading_capacity
    : (accountData.data as any)?.available_balance !== undefined
    ? (accountData.data as any).available_balance
    : accountData.data?.availableBalance;
  // Daily PnL: WS account_update delta first, then REST /account — never fall back to unrealized_pnl
  const realDailyPnl = liveAccountDelta?.dailyPnl !== undefined
    ? liveAccountDelta.dailyPnl
    : accountData.data?.dailyPnl;
  const realDailyPnlPercentage = liveAccountDelta?.dailyPnlPercentage !== undefined
    ? liveAccountDelta.dailyPnlPercentage
    : accountData.data?.dailyPnlPercentage;

  const accountInfo: AccountSummary = {
    // Explicit offline-safe defaults — no fabricated values
    environment: accountData.data?.environment ?? '-',
    balance: realBalance,
    equity: realEquity,
    availableBalance: realAvailable,
    dailyPnl: realDailyPnl,
    dailyPnlPercentage: realDailyPnlPercentage,
    botStatus: botBackend.botStatus,
    connectionStatus: botBackend.connectionStatus,
    backendConnection:
      botBackend.connectionStatus === 'Connected'
        ? `FastAPI Connected (${botBackend.apiBaseUrl})`
        : botBackend.connectionStatus === 'Error'
        ? 'FastAPI Error'
        : 'FastAPI Offline',
    lastUpdated: liveWs.lastEventTime
      ? liveWs.lastEventTime.toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }) + ' UTC (WS)'
      : botBackend.lastChecked
      ? botBackend.lastChecked.toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }) + ' UTC'
      : '-',
  };

  const toggleSidebarCollapse = () => setIsSidebarCollapsed((prev) => !prev);
  const toggleMobileSidebar = () => setIsMobileSidebarOpen((prev) => !prev);
  const openMobileSidebar = () => setIsMobileSidebarOpen(true);
  const closeMobileSidebar = () => setIsMobileSidebarOpen(false);
  return {
    currentTab,
    setCurrentTab,
    selectedSymbol,
    setSelectedSymbol,
    selectedTimeframe,
    setSelectedTimeframe,
    isSidebarCollapsed,
    toggleSidebarCollapse,
    isMobileSidebarOpen,
    toggleMobileSidebar,
    openMobileSidebar,
    closeMobileSidebar,
    selectedPosition,
    setSelectedPosition,
    displayedPositions,
    displayedSignals,
    accountInfo,
    metrics: performanceData.metrics,
    botBackend,
    signalsData,
    tradesData,
    performanceData,
    liveWs,
    liveTickerData,
    systemNotification,
    clearSystemNotification: () => setSystemNotification(null),
    reconData,
  };
}
