import React from 'react';
import { BotStatus, PositionSide, SignalStatus, TradeResult, TradeSide } from '../types';

interface StatusBadgeProps {
  type:
    | 'side'
    | 'position'
    | 'bot'
    | 'env'
    | 'status'
    | 'connection'
    | 'signal-status'
    | 'trade-result';
  value:
    | TradeSide
    | PositionSide
    | BotStatus
    | SignalStatus
    | TradeResult
    | 'DEMO'
    | 'LIVE'
    | 'TP Hit'
    | 'SL Hit'
    | 'Manual Close'
    | 'Mock'
    | 'Offline'
    | 'Connected'
    | string;
  size?: 'xs' | 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  type,
  value,
  size = 'sm',
}) => {
  const sizeClasses = {
    xs: 'px-1.5 py-0.5 text-[10px]',
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-xs',
  }[size];

  // Side badges (BUY / SELL)
  if (type === 'side') {
    const isBuy = value === 'BUY';
    return (
      <span
        id={`badge-side-${value.toLowerCase()}`}
        className={`inline-flex items-center font-mono font-semibold tracking-wider rounded border ${sizeClasses} ${
          isBuy
            ? 'bg-emerald-950/60 text-emerald-400 border-emerald-700/60'
            : 'bg-rose-950/60 text-rose-400 border-rose-700/60'
        }`}
      >
        {value}
      </span>
    );
  }

  // Position side badges (LONG / SHORT)
  if (type === 'position') {
    const isLong = value === 'LONG';
    return (
      <span
        id={`badge-pos-${value.toLowerCase()}`}
        className={`inline-flex items-center font-mono font-semibold tracking-wider rounded border ${sizeClasses} ${
          isLong
            ? 'bg-emerald-950/60 text-emerald-400 border-emerald-600/50'
            : 'bg-rose-950/60 text-rose-400 border-rose-600/50'
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
            isLong ? 'bg-emerald-400' : 'bg-rose-400'
          }`}
        />
        {value}
      </span>
    );
  }

  // Signal Status badges (New, Approved, Rejected, Executed)
  if (type === 'signal-status') {
    const status = value as SignalStatus;
    const styles: Record<SignalStatus, string> = {
      New: 'bg-sky-950/60 text-sky-400 border-sky-800/60',
      Approved: 'bg-indigo-950/60 text-indigo-300 border-indigo-700/60',
      Executed: 'bg-emerald-950/60 text-emerald-400 border-emerald-700/60',
      Rejected: 'bg-slate-800/60 text-slate-400 border-slate-700/60',
    };

    return (
      <span
        id={`badge-sig-status-${status.toLowerCase()}`}
        className={`inline-flex items-center font-mono font-medium rounded border ${sizeClasses} ${
          styles[status] || 'bg-slate-800 text-slate-300 border-slate-700'
        }`}
      >
        {value}
      </span>
    );
  }

  // Trade Result badges (Win, Loss, Breakeven)
  if (type === 'trade-result') {
    const result = value as TradeResult;
    const isWin = result === 'Win';
    const isLoss = result === 'Loss';

    return (
      <span
        id={`badge-result-${result.toLowerCase()}`}
        className={`inline-flex items-center font-mono font-semibold rounded border ${sizeClasses} ${
          isWin
            ? 'bg-emerald-950/60 text-emerald-400 border-emerald-700/50'
            : isLoss
            ? 'bg-rose-950/60 text-rose-400 border-rose-700/50'
            : 'bg-slate-800/60 text-slate-300 border-slate-700/60'
        }`}
      >
        {value}
      </span>
    );
  }

  // Bot status badges
  if (type === 'bot') {
    const status = value as BotStatus;
    const isStopped = status === 'STOPPED';
    const isRunning = status === 'RUNNING';

    return (
      <span
        id={`badge-bot-${String(status).toLowerCase()}`}
        className={`inline-flex items-center font-mono font-medium rounded border ${sizeClasses} ${
          isStopped
            ? 'bg-amber-950/40 text-amber-300 border-amber-800/50'
            : isRunning
            ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/50'
            : 'bg-slate-800/60 text-slate-300 border-slate-700'
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
            isStopped
              ? 'bg-amber-400'
              : isRunning
              ? 'bg-emerald-400 animate-pulse'
              : 'bg-slate-400'
          }`}
        />
        {value}
      </span>
    );
  }

  // Environment badge (DEMO / LIVE)
  if (type === 'env') {
    const isDemo = value === 'DEMO';
    return (
      <span
        id="badge-environment"
        className={`inline-flex items-center font-mono font-semibold tracking-wider rounded border ${sizeClasses} ${
          isDemo
            ? 'bg-cyan-950/40 text-cyan-300 border-cyan-800/60'
            : 'bg-indigo-950/50 text-indigo-300 border-indigo-700/60'
        }`}
      >
        {value}
      </span>
    );
  }

  // Trade outcome status badges (TP Hit, SL Hit, Manual Close)
  if (type === 'status') {
    const isTP = value === 'TP Hit';
    const isSL = value === 'SL Hit';

    return (
      <span
        id={`badge-status-${String(value).replace(/\s+/g, '-').toLowerCase()}`}
        className={`inline-flex items-center font-mono text-[11px] rounded px-2 py-0.5 border ${
          isTP
            ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/40'
            : isSL
            ? 'bg-rose-950/40 text-rose-400 border-rose-800/40'
            : 'bg-slate-800/50 text-slate-300 border-slate-700/40'
        }`}
      >
        {value}
      </span>
    );
  }

  // Connection indicator badge
  if (type === 'connection') {
    const val = String(value);
    const isConnected = val === 'Connected';
    const isReconnecting = val === 'Reconnecting';
    const isOffline = val === 'Offline';
    const isError = val === 'Error';

    return (
      <span
        id="badge-connection"
        className={`inline-flex items-center font-mono ${sizeClasses} rounded border ${
          isConnected
            ? 'bg-emerald-950/50 text-emerald-300 border-emerald-800/60'
            : isReconnecting
            ? 'bg-amber-950/50 text-amber-300 border-amber-800/60'
            : isError
            ? 'bg-rose-950/50 text-rose-300 border-rose-800/60'
            : isOffline
            ? 'bg-slate-900 text-slate-400 border-slate-800'
            : 'bg-slate-900/80 text-slate-400 border-slate-800'
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
            isConnected
              ? 'bg-emerald-400 animate-pulse'
              : isReconnecting
              ? 'bg-amber-400 animate-ping'
              : isError
              ? 'bg-rose-400'
              : isOffline
              ? 'bg-slate-500'
              : 'bg-slate-500'
          }`}
        />
        {value}
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center rounded border bg-slate-800 text-slate-300 border-slate-700 ${sizeClasses}`}
    >
      {value}
    </span>
  );
};
