import { useCallback, useEffect, useState } from 'react';
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
import { evaluateSignalExpiry } from '../utils/signalLifecycle';

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

    // Keep ticker prices for charts/market display only.
    // Do not recalculate open-position PnL from last-traded price:
    // Bybit values positions using mark price.
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

  // Hook: auto-expire websocket signals
  useEffect(() => {
    const interval = setInterval(() => {
      setWsSignals((sigs) => sigs.map((sig) => evaluateSignalExpiry(sig, Date.now())));
    }, 1000);
    return () => clearInterval(interval);
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

  // Bybit /positions is authoritative for open-position valuation.
  // It supplies the exchange mark price and unrealised PnL used by Bybit itself.
  // WebSocket-only positions are retained temporarily until the next REST refresh.
  const displayedPositions: Position[] = [
    ...positionsData.positions,
    ...wsPositions.filter(
      (ws) =>
        !positionsData.positions.some(
          (rest) =>
            rest.id === ws.id ||
            (rest.symbol === ws.symbol && rest.side === ws.side)
        )
    ),
  ];


  // Signals feed: merges WebSocket signals on top of REST signals
  const combinedSignals: Signal[] = wsSignals.length > 0
    ? [...wsSignals, ...signalsData.signals.filter((s) => !wsSignals.some((ws) => ws.id === s.id))]
    : signalsData.signals;
  const displayedSignals: Signal[] = combinedSignals;

  // Account balances: WebSocket delta > Reconciliation data > REST /account.
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
  // Daily wallet PnL uses Bybit Transaction Log when available:
  // change = cashFlow + funding - fee.
  // The browser's local calendar day defines "today".
  const today = new Date();
  const isSameLocalDay = (value?: string) => {
    if (!value) return false;
    const date = new Date(value);
    return !Number.isNaN(date.getTime()) &&
      date.getFullYear() === today.getFullYear() &&
      date.getMonth() === today.getMonth() &&
      date.getDate() === today.getDate();
  };
  const realizedToday = tradesData.allTrades
    .filter((trade) => isSameLocalDay(trade.closedAtISO))
    .reduce(
      (sum, trade) =>
        sum + (Number.isFinite(trade.pnl) ? trade.pnl : 0),
      0
    );

  const walletTransactions: any[] = Array.isArray(
    reconData.data?.wallet_activity?.transactions
  )
    ? reconData.data.wallet_activity.transactions
    : [];

  const todayWalletTransactions = walletTransactions.filter(
    (row) =>
      isSameLocalDay(row?.transaction_time) &&
      row?.category === 'linear' &&
      ['TRADE', 'SETTLEMENT'].includes(String(row?.type || '').toUpperCase())
  );

  const hasWalletActivitySource =
    reconData.data?.wallet_activity?.source === 'BYBIT_TRANSACTION_LOG';

  const walletNetToday = todayWalletTransactions.reduce(
    (sum, row) => sum + Number(row?.change || 0),
    0
  );

  const walletFeesToday = todayWalletTransactions.reduce(
    (sum, row) =>
      String(row?.type || '').toUpperCase() === 'TRADE'
        ? sum + Number(row?.fee || 0)
        : sum,
    0
  );

  const walletFundingToday = todayWalletTransactions.reduce(
    (sum, row) => sum + Number(row?.funding || 0),
    0
  );

  const walletCashFlowToday = todayWalletTransactions.reduce(
    (sum, row) => sum + Number(row?.cash_flow || 0),
    0
  );

  const selectedDailyPnl = hasWalletActivitySource
    ? walletNetToday
    : realizedToday;

  const realDailyPnl =
    !hasWalletActivitySource &&
    tradesData.isLoading &&
    tradesData.allTrades.length === 0
      ? undefined
      : Math.round(selectedDailyPnl * 100) / 100;

  const estimatedStartBalance =
    realBalance !== undefined
      ? realBalance - selectedDailyPnl
      : undefined;

  const realDailyPnlPercentage =
    estimatedStartBalance && estimatedStartBalance !== 0
      ? (selectedDailyPnl / estimatedStartBalance) * 100
      : undefined;

  const dailyWalletReconciliation = {
    source: hasWalletActivitySource
      ? 'Bybit Transaction Log'
      : 'Closed Trade Fallback',
    walletNet: Math.round(walletNetToday * 10000) / 10000,
    fees: Math.round(walletFeesToday * 10000) / 10000,
    funding: Math.round(walletFundingToday * 10000) / 10000,
    cashFlow: Math.round(walletCashFlowToday * 10000) / 10000,
    closedTradePnl: Math.round(realizedToday * 10000) / 10000,
    adjustment:
      Math.round((walletNetToday - realizedToday) * 10000) / 10000,
    transactionCount: todayWalletTransactions.length,
  };

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
    dailyWalletReconciliation,
  };
}
