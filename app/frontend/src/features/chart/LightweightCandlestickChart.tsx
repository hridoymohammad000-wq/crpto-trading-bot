import React, { useEffect, useRef, useState } from 'react';
import {
  MousePointer2,
  Minus,
  Slash,
  Maximize2,
  Trash2,
} from 'lucide-react';
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
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
  const ema9SeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const ema21SeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const rsiSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);

  // User drawing tools are kept separate from bot Entry / SL / TP lines.
  const drawingSeriesRef = useRef<ISeriesApi<'Line'>[]>([]);
  const drawingPriceLinesRef = useRef<IPriceLine[]>([]);
  const trendStartRef = useRef<{ time: UTCTimestamp; price: number } | null>(null);
  const [drawingMode, setDrawingMode] = useState<'cursor' | 'trend' | 'horizontal'>('cursor');
  const drawingModeRef = useRef<'cursor' | 'trend' | 'horizontal'>('cursor');

  // State for legend display of hovered / latest candle OHLCV
  const [hoveredOHLCV, setHoveredOHLCV] = useState<OHLCVDisplay | null>(null);

  useEffect(() => {
    drawingModeRef.current = drawingMode;
  }, [drawingMode]);

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
        background: { type: ColorType.Solid, color: '#030712' },
        textColor: '#94a3b8',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
        fontSize: 11,
        panes: {
          separatorColor: '#1e293b',
          separatorHoverColor: '#334155',
          enableResize: true,
        },
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
    const volumeSeries = chart.addSeries(
      HistogramSeries,
      {
        priceFormat: {
          type: 'volume',
        },
        priceLineVisible: false,
        lastValueVisible: false,
      },
      1
    );

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.15,
        bottom: 0.05,
      },
    });

    const ema9Series = chart.addSeries(LineSeries, {
      color: '#22d3ee',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    const ema21Series = chart.addSeries(LineSeries, {
      color: '#f59e0b',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    const rsiSeries = chart.addSeries(
      LineSeries,
      {
        color: '#a78bfa',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: true,
      },
      2
    );

    rsiSeries.priceScale().applyOptions({
      autoScale: false,
      scaleMargins: {
        top: 0.1,
        bottom: 0.1,
      },
    });

    rsiSeries.createPriceLine({
      price: 70,
      color: '#475569',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: false,
      title: '70',
    });

    rsiSeries.createPriceLine({
      price: 50,
      color: '#334155',
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: false,
      title: '50',
    });

    rsiSeries.createPriceLine({
      price: 30,
      color: '#475569',
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: false,
      title: '30',
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;
    ema9SeriesRef.current = ema9Series;
    ema21SeriesRef.current = ema21Series;
    rsiSeriesRef.current = rsiSeries;

    const panes = chart.panes();
    if (panes[0]) panes[0].setHeight(420);
    if (panes[1]) panes[1].setHeight(90);
    if (panes[2]) panes[2].setHeight(150);

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

    // User drawing interaction.
    const handleChartClick = (param: any) => {
      if (
        drawingModeRef.current === 'cursor' ||
        !param?.point ||
        !param?.time ||
        !candleSeriesRef.current ||
        !chartRef.current
      ) {
        return;
      }

      const price = candleSeriesRef.current.coordinateToPrice(param.point.y);
      const time = param.time as UTCTimestamp;

      if (price == null || !Number.isFinite(price)) return;

      // One-click horizontal level.
      if (drawingModeRef.current === 'horizontal') {
        const line = candleSeriesRef.current.createPriceLine({
          price,
          color: '#f59e0b',
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `DRAW: $${formatPrice(price, priceDecimals)}`,
        });

        drawingPriceLinesRef.current.push(line);
        setDrawingMode('cursor');
        return;
      }

      // Two-click trend line.
      if (drawingModeRef.current === 'trend') {
        if (!trendStartRef.current) {
          trendStartRef.current = { time, price };
          return;
        }

        const start = trendStartRef.current;
        const end = { time, price };

        const first =
          Number(start.time) <= Number(end.time)
            ? start
            : end;

        const second =
          Number(start.time) <= Number(end.time)
            ? end
            : start;

        const series = chart.addSeries(LineSeries, {
          color: '#38bdf8',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });

        series.setData([
          {
            time: first.time,
            value: first.price,
          },
          {
            time: second.time,
            value: second.price,
          },
        ]);

        drawingSeriesRef.current.push(series);
        trendStartRef.current = null;
        setDrawingMode('cursor');
      }
    };

    chart.subscribeClick(handleChartClick);

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
      chart.unsubscribeClick(handleChartClick);
      drawingSeriesRef.current = [];
      drawingPriceLinesRef.current = [];
      trendStartRef.current = null;
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      ema9SeriesRef.current = null;
      ema21SeriesRef.current = null;
      rsiSeriesRef.current = null;
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

    const closes = candles.map((c) => c.close);

    const calculateEMA = (period: number) => {
      const output: { time: UTCTimestamp; value: number }[] = [];
      if (closes.length < period) return output;

      let emaValue =
        closes.slice(0, period).reduce((sum, value) => sum + value, 0) / period;

      output.push({
        time: candles[period - 1].time as UTCTimestamp,
        value: emaValue,
      });

      const multiplier = 2 / (period + 1);

      for (let i = period; i < closes.length; i++) {
        emaValue = (closes[i] - emaValue) * multiplier + emaValue;
        output.push({
          time: candles[i].time as UTCTimestamp,
          value: emaValue,
        });
      }

      return output;
    };

    const calculateRSI = (period = 14) => {
      const output: { time: UTCTimestamp; value: number }[] = [];
      if (closes.length <= period) return output;

      let gains = 0;
      let losses = 0;

      for (let i = 1; i <= period; i++) {
        const change = closes[i] - closes[i - 1];
        if (change >= 0) gains += change;
        else losses += -change;
      }

      let avgGain = gains / period;
      let avgLoss = losses / period;

      const rsiValue = () => {
        if (avgLoss === 0) return avgGain === 0 ? 50 : 100;
        const rs = avgGain / avgLoss;
        return 100 - 100 / (1 + rs);
      };

      output.push({
        time: candles[period].time as UTCTimestamp,
        value: rsiValue(),
      });

      for (let i = period + 1; i < closes.length; i++) {
        const change = closes[i] - closes[i - 1];
        const gain = Math.max(change, 0);
        const loss = Math.max(-change, 0);

        avgGain = (avgGain * (period - 1) + gain) / period;
        avgLoss = (avgLoss * (period - 1) + loss) / period;

        output.push({
          time: candles[i].time as UTCTimestamp,
          value: rsiValue(),
        });
      }

      return output;
    };

    ema9SeriesRef.current?.setData(calculateEMA(9));
    ema21SeriesRef.current?.setData(calculateEMA(21));
    rsiSeriesRef.current?.setData(calculateRSI(14));

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

  const clearUserDrawings = () => {
    const chart = chartRef.current;
    const candleSeries = candleSeriesRef.current;

    if (chart) {
      drawingSeriesRef.current.forEach((series) => {
        try {
          chart.removeSeries(series);
        } catch {
          // Already removed.
        }
      });
    }

    if (candleSeries) {
      drawingPriceLinesRef.current.forEach((line) => {
        try {
          candleSeries.removePriceLine(line);
        } catch {
          // Already removed.
        }
      });
    }

    drawingSeriesRef.current = [];
    drawingPriceLinesRef.current = [];
    trendStartRef.current = null;
    setDrawingMode('cursor');
  };

  const fitChart = () => {
    chartRef.current?.timeScale().fitContent();
  };

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

      {/* Drawing Toolbar */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-slate-800 bg-slate-950/95">
        <button
          type="button"
          onClick={() => {
            trendStartRef.current = null;
            setDrawingMode('cursor');
          }}
          title="Cursor"
          className={`p-1.5 rounded border transition-colors ${
            drawingMode === 'cursor'
              ? 'border-sky-700 bg-sky-950/60 text-sky-300'
              : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200'
          }`}
        >
          <MousePointer2 size={14} />
        </button>

        <button
          type="button"
          onClick={() => {
            trendStartRef.current = null;
            setDrawingMode('trend');
          }}
          title="Trend Line ? click two points"
          className={`p-1.5 rounded border transition-colors ${
            drawingMode === 'trend'
              ? 'border-sky-700 bg-sky-950/60 text-sky-300'
              : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200'
          }`}
        >
          <Slash size={14} />
        </button>

        <button
          type="button"
          onClick={() => {
            trendStartRef.current = null;
            setDrawingMode('horizontal');
          }}
          title="Horizontal Line ? click chart"
          className={`p-1.5 rounded border transition-colors ${
            drawingMode === 'horizontal'
              ? 'border-amber-700 bg-amber-950/60 text-amber-300'
              : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200'
          }`}
        >
          <Minus size={14} />
        </button>

        <div className="mx-1 h-5 w-px bg-slate-800" />

        <button
          type="button"
          onClick={fitChart}
          title="Fit Chart"
          className="p-1.5 rounded border border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200"
        >
          <Maximize2 size={14} />
        </button>

        <button
          type="button"
          onClick={clearUserDrawings}
          title="Clear Drawings"
          className="p-1.5 rounded border border-slate-800 bg-slate-900 text-slate-400 hover:text-rose-300 hover:border-rose-900"
        >
          <Trash2 size={14} />
        </button>

        <span className="ml-2 text-[10px] font-mono text-slate-500">
          {drawingMode === 'trend'
            ? trendStartRef.current
              ? 'Trend: click second point'
              : 'Trend: click first point'
            : drawingMode === 'horizontal'
            ? 'Horizontal: click price level'
            : 'Drawing tools'}
        </span>
      </div>

      {/* Real Candlestick & Volume Chart Canvas */}
      <div
        ref={containerRef}
        id="tradingview-candlestick-container"
        className="w-full h-[560px] sm:h-[600px] md:h-[660px] min-h-[520px]"
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
