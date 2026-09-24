import React from 'react';
import { TradingSymbol } from '../types';

export interface SymbolSelectorProps {
  selectedSymbol: TradingSymbol;
  onSelectSymbol: (symbol: TradingSymbol) => void;
  symbols?: TradingSymbol[];
  className?: string;
  size?: 'sm' | 'md';
}

const DEFAULT_SYMBOLS: TradingSymbol[] = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];

export const SymbolSelector: React.FC<SymbolSelectorProps> = ({
  selectedSymbol,
  onSelectSymbol,
  symbols = DEFAULT_SYMBOLS,
  className = '',
  size = 'sm',
}) => {
  const padClass = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-xs sm:text-sm';

  return (
    <div
      id="symbol-selector"
      className={`flex items-center p-0.5 bg-slate-900 border border-slate-800 rounded font-mono ${className}`}
    >
      {symbols.map((sym) => {
        const isSelected = selectedSymbol === sym;
        return (
          <button
            key={sym}
            id={`btn-symbol-${sym.toLowerCase()}`}
            type="button"
            onClick={() => onSelectSymbol(sym)}
            className={`${padClass} rounded-xs font-semibold transition-colors ${
              isSelected
                ? 'bg-slate-800 text-slate-100 shadow-xs border border-slate-700/70'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border border-transparent'
            }`}
          >
            {sym}
          </button>
        );
      })}
    </div>
  );
};
