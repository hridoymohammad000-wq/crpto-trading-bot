import React from 'react';
import {
  AlertTriangle,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { ChartPanelSkeleton } from '../../components/LoadingSkeleton';
import { SymbolSelector } from '../../components/SymbolSelector';
import { TimeframeSelector } from '../../components/TimeframeSelector';
import { useCandles } from '../../hooks/useCandles';
import { Position, Signal, SymbolTickerInfo, Timeframe, TradingSymbol } from '../../types';
import { formatPrice } from '../../utils/formatters';
import { LightweightCandlestickChart } from './LightweightCandlestickChart';

export interface ChartPanelProps {
  selectedSymbol: TradingSymbol;
  onSelectSymbol: (symbol: TradingSymbol) => void;
  selectedTimeframe: Timeframe;
  onSelectTimeframe: (timeframe: Timeframe) => void;
  positions?: Position[];
  signals?: Signal[];
  tickerData?: Record<string, SymbolTickerInfo>;
  isLivePrice?: boolean;
  isLoading?: boolean;
  className?: string;
}

export const ChartPanel: React.FC<ChartPanelProps> = ({
  selectedSymbol,
  onSelectSymbol,
  selectedTimeframe,
  onSelectTimeframe,
  positions,
  signals,
  tickerData,
  isLivePrice = false,
  isLoading = false,
  className = '',
}) => {
  // Use isolated candle hook accessing frontend data layer
  const {
    candles,
    markers,
    isLoading: isCandlesLoading,
    isError,
    errorMessage,
    refetch,
    activeLevels,
  } = useCandles({
    symbol: selectedSymbol,
    timeframe: selectedTimeframe,
    positions,
    signals,
  });

  if (isLoading || (isCandlesLoading && candles.length === 0)) {
    return <ChartPanelSkeleton />;
  }

  const currentTicker = tickerData?.[selectedSymbol] ?? null;
  const isPositive = (currentTicker?.change24h ?? 0) >= 0;
  const priceDecimals = 2;

  return (
    <div
      id="panel-chart"
      className={`bg-slate-900/80 border border-slate-800 rounded-md flex flex-col overflow-hidden shadow-xs ${className}`}
    >
      {/* Chart Panel Header Controls */}
      <div className="px-3 py-2.5 bg-slate-950/90 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
        {/* Symbol Selector and Ticker Info */}
        <div className="flex items-center gap-3">
          {/* Reusable Symbol Selector */}
          <SymbolSelector
            selectedSymbol={selectedSymbol}
            onSelectSymbol={onSelectSymbol}
          />

          {/* Realtime Ticker Summary */}
          <div className="flex items-center gap-2.5 pl-1 sm:pl-2 text-xs font-mono">
            <span
              id="chart-price-display"
              className={`text-sm sm:text-base font-bold flex items-center gap-1.5 ${
                isPositive ? 'text-emerald-400' : 'text-rose-400'
              }`}
            >
              {currentTicker ? `$${formatPrice(currentTicker.price, priceDecimals)}` : <span className="text-slate-500 text-xs">Awaiting price…</span>}
              {isLivePrice && currentTicker && (
                <span
                  className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"
                  title="Real-time WebSocket price update active"
                />
              )}
            </span>

            {currentTicker ? (
              <span
                id="chart-change-display"
                className={`flex items-center gap-0.5 text-xs font-semibold px-1.5 py-0.5 rounded ${
                  isPositive
                    ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50'
                    : 'bg-rose-950/60 text-rose-400 border border-rose-800/50'
                }`}
              >
                {isPositive ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                {isPositive ? '+' : ''}
                {currentTicker.change24h}%
              </span>
            ) : null}

            <div className="hidden xl:flex items-center gap-3 text-slate-400 text-[11px] pl-2 border-l border-slate-800">
              <span>
                24h High: <span className="text-slate-200 font-medium">{currentTicker ? `$${currentTicker.high24h.toLocaleString()}` : '—'}</span>
              </span>
              <span>
                24h Low: <span className="text-slate-200 font-medium">{currentTicker ? `$${currentTicker.low24h.toLocaleString()}` : '—'}</span>
              </span>
              <span>
                Volume: <span className="text-slate-200 font-medium">{currentTicker?.volume24h ?? '—'}</span>
              </span>
            </div>
          </div>
        </div>

        {/* Timeframe Selector & Chart Indicators Header */}
        <div className="flex items-center gap-2">
          {/* Reusable Timeframe Selector */}
          <TimeframeSelector
            selectedTimeframe={selectedTimeframe}
            onSelectTimeframe={onSelectTimeframe}
          />

          <button
            type="button"
            onClick={() => refetch()}
            title="Refresh Candles"
            className="p-1 rounded bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <RefreshCw size={12} className={isCandlesLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* 24h High / Low / Volume Strip for Medium & Small Screens */}
      <div className="flex xl:hidden items-center justify-between px-3 py-1 bg-slate-950/70 border-b border-slate-800/80 text-[10px] font-mono text-slate-400">
        <div>24h High: <span className="text-slate-200">{currentTicker ? `$${currentTicker.high24h.toLocaleString()}` : '—'}</span></div>
        <div>24h Low: <span className="text-slate-200">{currentTicker ? `$${currentTicker.low24h.toLocaleString()}` : '—'}</span></div>
        <div>Volume: <span className="text-slate-200">{currentTicker?.volume24h ?? '—'}</span></div>
      </div>

      {/* Error notification banner if candle fetch failed */}
      {isError && (
        <div className="px-3 py-2 bg-rose-950/40 border-b border-rose-800/50 flex items-center justify-between text-xs font-mono text-rose-300">
          <div className="flex items-center gap-2">
            <AlertTriangle size={14} className="text-rose-400" />
            <span>Candle Data Warning: {errorMessage || 'Failed to load candle dataset'}</span>
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            className="px-2 py-0.5 rounded bg-rose-900/60 hover:bg-rose-900 text-rose-200 border border-rose-700/50 text-[11px]"
          >
            Retry
          </button>
        </div>
      )}

      {/* Real TradingView Lightweight Candlestick and Volume Chart */}
      <LightweightCandlestickChart
        candles={candles}
        markers={markers}
        activeLevels={activeLevels}
        selectedSymbol={selectedSymbol}
        selectedTimeframe={selectedTimeframe}
      />
    </div>
  );
};
