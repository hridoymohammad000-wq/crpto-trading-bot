import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { TradingSymbol } from '../types';

export interface SymbolSelectorProps {
  selectedSymbol: TradingSymbol;
  onSelectSymbol: (symbol: TradingSymbol) => void;
  symbols?: TradingSymbol[];
  className?: string;
  size?: 'sm' | 'md';
}

const DEFAULT_SYMBOLS: TradingSymbol[] = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
const VALID_SYMBOL = /^[A-Z0-9]+USDT$/;

export const SymbolSelector: React.FC<SymbolSelectorProps> = ({
  selectedSymbol,
  onSelectSymbol,
  symbols = DEFAULT_SYMBOLS,
  className = '',
  size = 'sm',
}) => {
  const [search, setSearch] = useState('');
  const [searchError, setSearchError] = useState<string | null>(null);

  const padClass =
    size === 'sm'
      ? 'px-2.5 py-1 text-xs'
      : 'px-3 py-1.5 text-xs sm:text-sm';

  const visibleSymbols = useMemo(
    () => Array.from(new Set([selectedSymbol, ...symbols])),
    [selectedSymbol, symbols]
  );

  const submitSearch = () => {
    const normalized = search.trim().toUpperCase();

    if (!normalized) {
      setSearchError('Enter a symbol');
      return;
    }

    if (!VALID_SYMBOL.test(normalized)) {
      setSearchError('Use a valid USDT symbol, e.g. XRPUSDT');
      return;
    }

    setSearchError(null);
    onSelectSymbol(normalized);
    setSearch('');
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div
        id="symbol-selector"
        className="flex items-center p-0.5 bg-slate-900 border border-slate-800 rounded font-mono overflow-x-auto custom-scrollbar"
      >
        {visibleSymbols.map((sym) => {
          const isSelected = selectedSymbol === sym;

          return (
            <button
              key={sym}
              id={`btn-symbol-${sym.toLowerCase()}`}
              type="button"
              onClick={() => {
                setSearchError(null);
                onSelectSymbol(sym);
              }}
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

      <div className="relative flex items-center">
        <Search
          size={12}
          className="absolute left-2 text-slate-500 pointer-events-none"
        />

        <input
          id="chart-symbol-search"
          type="text"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value.toUpperCase());
            setSearchError(null);
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              submitSearch();
            }
          }}
          placeholder="XRPUSDT"
          spellCheck={false}
          autoComplete="off"
          className="w-28 sm:w-32 bg-slate-950 border border-slate-800 rounded pl-7 pr-2 py-1 text-xs font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-slate-600"
        />

        {searchError && (
          <div className="absolute top-full right-0 mt-1 z-30 whitespace-nowrap rounded border border-rose-800/60 bg-rose-950 px-2 py-1 text-[10px] font-mono text-rose-300">
            {searchError}
          </div>
        )}
      </div>
    </div>
  );
};
