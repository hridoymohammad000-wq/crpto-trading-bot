import React from 'react';
import { Timeframe } from '../types';

export interface TimeframeSelectorProps {
  selectedTimeframe: Timeframe;
  onSelectTimeframe: (timeframe: Timeframe) => void;
  timeframes?: Timeframe[];
  className?: string;
  size?: 'sm' | 'md';
}

const DEFAULT_TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m'];

export const TimeframeSelector: React.FC<TimeframeSelectorProps> = ({
  selectedTimeframe,
  onSelectTimeframe,
  timeframes = DEFAULT_TIMEFRAMES,
  className = '',
  size = 'sm',
}) => {
  const padClass = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  return (
    <div
      id="timeframe-selector"
      className={`flex items-center p-0.5 bg-slate-900 border border-slate-800 rounded font-mono ${className}`}
    >
      {timeframes.map((tf) => {
        const isSelected = selectedTimeframe === tf;
        return (
          <button
            key={tf}
            id={`btn-timeframe-${tf}`}
            type="button"
            onClick={() => onSelectTimeframe(tf)}
            className={`${padClass} rounded-xs font-semibold transition-colors ${
              isSelected
                ? 'bg-emerald-950/90 text-emerald-300 border border-emerald-800/80 shadow-xs'
                : 'text-slate-400 hover:text-slate-200 border border-transparent'
            }`}
          >
            {tf}
          </button>
        );
      })}
    </div>
  );
};
