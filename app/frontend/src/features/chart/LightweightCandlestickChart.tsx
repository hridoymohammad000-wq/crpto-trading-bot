import React, { useEffect, useRef, useState } from 'react';
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  CrosshairMode,
  HistogramSeries,
  IChartApi,
  IPriceLine,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  LineStyle,
  SeriesMarker,
  Time,
  UTCTimestamp,
} from 'lightweight-charts';
import {
  ActiveTradeLevels,
  Candle,
  ChartSignalMarker,
  Timeframe,
  TradingSymbol,
} from '../../types';
import { formatPrice } from '../../utils/formatters';

export interface LightweightCandlestickChartProps {
  candles: Candle[];
  markers: ChartSignalMarker[];
  activeLevels: ActiveTradeLevels | null;
  selectedSymbol: TradingSymbol;
  selectedTimeframe: Timeframe;
  className?: string;
}

export interface OHLCVDisplay {
  time?: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  change: number;
  changePct: number;
}

export const LightweightCandlestickChart: React.FC<LightweightCandlestickChartProps> = ({
  candles,
  markers,
  activeLevels,
  selectedSymbol,
  selectedTimeframe,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);

  // State for legend display of hovered / latest candle OHLCV
  const [hoveredOHLCV, setHoveredOHLCV] = useState<OHLCVDisplay | null>(null);

  // Derive latest candle for fallback display
  const latestCandle = candles.length > 0 ? candles[candles.length - 1] : null;

  // Compute active display candle
  const displayData: OHLCVDisplay | null = hoveredOHLCV || (latestCandle ? {
    time: latestCandle.time,
    open: latestCandle.open,
    high: latestCandle.high,
    low: latestCandle.low,
    close: latestCandle.close,
    volume: latestCandle.volume,
    change: latestCandle.close - latestCandle.open,
    changePct: latestCandle.open !== 0 ? ((latestCandle.close - latestCandle.open) / latestCandle.open) * 100 : 0,
  } : null);

  const priceDecimals = selectedSymbol === 'BTCUSDT' ? 2 : 2;

  // Initialize TradingView Lightweight Chart
  useEffect(() => {
    if (!containerRef.current) return;

    // Create Chart instance with dark trading-terminal aesthetic
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth || 800,
      height: containerRef.current.clientHeight || 380,
      layout: {
        background: { type: ColorType.Solid, color: '#030712' }, // slate-950
        textColor: '#94a3b8', // slate-400
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#0f172a' }, // subtle grid lines
        horzLines: { color: '#0f172a' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#475569',
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: '#1e293b',
        },
        horzLine: {
          color: '#475569',
          width: 1,
          style: LineStyle.Dashed,
          labelBackgroundColor: '#1e293b',
        },
      },
      rightPriceScale: {
        borderColor: '#1e293b',
        scaleMargins: {
          top: 0.08,
          bottom: 0.22, // Reserve lower area for volume series
        },
        autoScale: true,
      },
      timeScale: {
        borderColor: '#1e293b',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 6,
        barSpacing: 8,
        minBarSpacing: 4,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
    });

    // Add Candlestick Series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981', // emerald-500
      downColor: '#f43f5e', // rose-500
      borderUpColor: '#10b981',
      borderDownColor: '#f43f5e',
      wickUpColor: '#10b981',
      wickDownColor: '#f43f5e',
      priceFormat: {
        type: 'price',
        precision: priceDecimals,
        minMove: selectedSymbol === 'BTCUSDT' ? 0.1 : 0.01,
      },
    });

    // Add Volume Series (overlay at bottom)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '', // overlay
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8, // volume takes bottom 20% of chart
        bottom: 0,
      },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Subscribe to Crosshair Move for live OHLCV inspection
    chart.subscribeCrosshairMove((param) => {
      if (
        !param.time ||
        !param.point ||
        param.point.x < 0 ||
        param.point.y < 0 ||
        !candleSeriesRef.current
      ) {
        setHoveredOHLCV(null);
        return;
      }

      const candleData = param.seriesData.get(candleSeriesRef.current) as {
        time: UTCTimestamp;
        open: number;
        high: number;
        low: number;
        close: number;
      } | undefined;

      const volumeData = volumeSeriesRef.current
        ? (param.seriesData.get(volumeSeriesRef.current) as { value: number } | undefined)
        : undefined;

      if (candleData && typeof candleData.close === 'number') {
        const chg = candleData.close - candleData.open;
        const chgPct = candleData.open !== 0 ? (chg / candleData.open) * 100 : 0;
        setHoveredOHLCV({
          time: Number(candleData.time),
          open: candleData.open,
          high: candleData.high,
          low: candleData.low,
          close: candleData.close,
          volume: volumeData ? volumeData.value : 0,
          change: chg,
          changePct: chgPct,
        });
      } else {
        setHoveredOHLCV(null);
      }
    });

    // Responsive ResizeObserver
    const resizeObserver = new ResizeObserver((entries) => {
      if (!entries.length || !chartRef.current || !containerRef.current) return;
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) {
        chartRef.current.applyOptions({ width, height });
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      markersPluginRef.current = null;
      priceLinesRef.current = [];
    };
  }, [selectedSymbol, priceDecimals]);

  // Update Candlestick and Volume Data when candles change
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || candles.length === 0) return;

    // Format candlestick data for Lightweight Charts
    const formattedCandles = candles.map((c) => ({
      time: c.time as UTCTimestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    // Format volume histogram data
    const formattedVolume = candles.map((c) => ({
      time: c.time as UTCTimestamp,
      value: c.volume,
      color: c.close >= c.open ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.4)',
    }));

    candleSeriesRef.current.setData(formattedCandles);
    volumeSeriesRef.current.setData(formattedVolume);

    // Initial fit to content
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [candles]);

  // Update Signal and Entry Markers
  useEffect(() => {
    if (!candleSeriesRef.current || candles.length === 0) return;

    // Convert markers to Lightweight Charts SeriesMarker format
    const formattedMarkers: SeriesMarker<Time>[] = markers.map((m) => ({
      time: m.time as UTCTimestamp,
      position: m.position,
      shape: m.shape,
      color: m.color,
      text: m.text,
      id: m.id,
      size: m.shape === 'arrowUp' || m.shape === 'arrowDown' ? 1.5 : 1.2,
    }));

    // Sort markers chronologically (Lightweight Charts strict requirement)
    formattedMarkers.sort((a, b) => Number(a.time) - Number(b.time));

    if (!markersPluginRef.current) {
      markersPluginRef.current = createSeriesMarkers(
        candleSeriesRef.current,
        formattedMarkers
      );
    } else {
      markersPluginRef.current.setMarkers(formattedMarkers);
    }
  }, [markers, candles]);

  // Update Stop Loss, Take Profit, and Entry Price Lines
  useEffect(() => {
    if (!candleSeriesRef.current) return;

    // Clean up previous price lines
    priceLinesRef.current.forEach((line) => {
      try {
        candleSeriesRef.current?.removePriceLine(line);
      } catch {
        // Line might already be removed
      }
    });
    priceLinesRef.current = [];

    if (!activeLevels) return;

    const newLines: IPriceLine[] = [];

    // 1. Stop Loss Line (Dashed Red)
    if (typeof activeLevels.stopLoss === 'number' && activeLevels.stopLoss > 0) {
      const slLine = candleSeriesRef.current.createPriceLine({
        price: activeLevels.stopLoss,
        color: '#f43f5e', // rose-500
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: `SL: $${formatPrice(activeLevels.stopLoss, priceDecimals)}`,
      });
      newLines.push(slLine);
    }

    // 2. Take Profit Line (Dashed Green)
    if (typeof activeLevels.takeProfit === 'number' && activeLevels.takeProfit > 0) {
      const tpLine = candleSeriesRef.current.createPriceLine({
        price: activeLevels.takeProfit,
        color: '#10b981', // emerald-500
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: `TP: $${formatPrice(activeLevels.takeProfit, priceDecimals)}`,
      });
      newLines.push(tpLine);
    }

    // 3. Entry Price Line (Dotted Sky Blue)
    if (typeof activeLevels.entryPrice === 'number' && activeLevels.entryPrice > 0) {
      const entryLine = candleSeriesRef.current.createPriceLine({
        price: activeLevels.entryPrice,
        color: '#38bdf8', // sky-400
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: true,
        title: `ENTRY: $${formatPrice(activeLevels.entryPrice, priceDecimals)}`,
      });
      newLines.push(entryLine);
    }

    priceLinesRef.current = newLines;
  }, [activeLevels, priceDecimals]);

  const isUp = (displayData?.change ?? 0) >= 0;

  return (
    <div className={`relative flex flex-col w-full bg-slate-950 overflow-hidden ${className}`}>
      {/* Top HUD: OHLCV Inspection Bar & Active Levels Summary */}
      <div className="flex flex-wrap items-center justify-between px-3 py-1.5 bg-slate-950/95 border-b border-slate-800/80 text-[11px] font-mono gap-2 select-none">
        {/* Left: Active OHLCV coordinates */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-slate-400 font-semibold">
            <span className="text-slate-200">{selectedSymbol}</span>
            <span className="text-slate-600">•</span>
            <span className="text-emerald-400">{selectedTimeframe}</span>
          </div>

          {displayData && (
            <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-[10px] sm:text-[11px]">
              <span className="text-slate-400">
                O: <span className="text-slate-200 font-medium">${formatPrice(displayData.open, priceDecimals)}</span>
              </span>
              <span className="text-slate-400">
                H: <span className="text-emerald-400 font-medium">${formatPrice(displayData.high, priceDecimals)}</span>
              </span>
              <span className="text-slate-400">
                L: <span className="text-rose-400 font-medium">${formatPrice(displayData.low, priceDecimals)}</span>
              </span>
              <span className="text-slate-400">
                C: <span className={`font-semibold ${isUp ? 'text-emerald-400' : 'text-rose-400'}`}>
                  ${formatPrice(displayData.close, priceDecimals)}
                </span>
              </span>
              <span className="text-slate-400 hidden sm:inline">
                Vol: <span className="text-slate-200 font-medium">{displayData.volume.toLocaleString()}</span>
              </span>
              <span
                className={`text-[10px] font-semibold px-1 py-0.2 rounded ${
                  isUp
                    ? 'text-emerald-400 bg-emerald-950/40 border border-emerald-800/30'
                    : 'text-rose-400 bg-rose-950/40 border border-rose-800/30'
                }`}
              >
                {isUp ? '+' : ''}{displayData.changePct.toFixed(2)}%
              </span>
            </div>
          )}
        </div>

        {/* Right: Active Levels Badges (SL, TP, Entry) */}
        <div className="flex items-center gap-2 text-[10px]">
          {activeLevels && (
            <div className="flex items-center gap-1.5">
              {activeLevels.entryPrice && (
                <span
                  className="px-1.5 py-0.5 rounded bg-sky-950/60 text-sky-400 border border-sky-800/50"
                  title="Position Entry Price"
                >
                  ENTRY: ${formatPrice(activeLevels.entryPrice, priceDecimals)}
                </span>
              )}
              {activeLevels.stopLoss && (
                <span
                  className="px-1.5 py-0.5 rounded bg-rose-950/60 text-rose-400 border border-rose-800/50"
                  title="Stop Loss Price Line"
                >
                  SL: ${formatPrice(activeLevels.stopLoss, priceDecimals)}
                </span>
              )}
              {activeLevels.takeProfit && (
                <span
                  className="px-1.5 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/50"
                  title="Take Profit Price Line"
                >
                  TP: ${formatPrice(activeLevels.takeProfit, priceDecimals)}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Real Candlestick & Volume Chart Canvas */}
      <div
        ref={containerRef}
        id="tradingview-candlestick-container"
        className="w-full h-[320px] sm:h-[360px] md:h-[400px] min-h-[300px]"
      />

      {/* Chart Legend / Guide Footer */}
      <div className="flex flex-wrap items-center justify-between px-3 py-1 bg-slate-950/90 border-t border-slate-800/80 text-[10px] font-mono text-slate-500 select-none">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-xs bg-emerald-500 inline-block" /> Up
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-xs bg-rose-500 inline-block" /> Down
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-1 border-b border-rose-500 border-dashed inline-block" /> Stop Loss
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-1 border-b border-emerald-500 border-dashed inline-block" /> Take Profit
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-1 border-b border-sky-400 border-dotted inline-block" /> Entry
          </span>
        </div>
        <div className="hidden sm:flex items-center gap-2 text-slate-400">
          <span>TradingView Lightweight Charts v5.2</span>
          <span>•</span>
          <span>Scroll to Zoom • Drag to Pan</span>
        </div>
      </div>
    </div>
  );
};
