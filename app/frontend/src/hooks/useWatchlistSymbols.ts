import { useEffect, useState } from 'react';
import { fetchScannerWatchlist } from '../api/scanner';
import { TradingSymbol } from '../types';

export function useWatchlistSymbols(): TradingSymbol[] {
  const [symbols, setSymbols] = useState<TradingSymbol[]>(['BTCUSDT', 'ETHUSDT', 'SOLUSDT']);

  useEffect(() => {
    let mounted = true;
    
    async function fetchSymbols() {
      try {
        const data = await fetchScannerWatchlist();
        if (mounted && data) {
          const core = data.core_symbols || [];
          const dynamic = data.dynamic_symbols || [];
          const open = data.open_position_symbols || [];
          
          // Combine and deduplicate
          const combined = Array.from(new Set([...core, ...dynamic, ...open])) as TradingSymbol[];
          
          if (combined.length > 0) {
            // Sort: BTC, ETH, SOL first if they exist, then alphabetically
            const priorities = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
            combined.sort((a, b) => {
              const aIndex = priorities.indexOf(a);
              const bIndex = priorities.indexOf(b);
              if (aIndex !== -1 && bIndex !== -1) return aIndex - bIndex;
              if (aIndex !== -1) return -1;
              if (bIndex !== -1) return 1;
              return a.localeCompare(b);
            });
            
            setSymbols(combined);
          }
        }
      } catch (err) {
        console.error('Failed to load watchlist symbols for chart:', err);
      }
    }
    
    fetchSymbols();
    
    // Optionally poll every 60s
    const interval = setInterval(fetchSymbols, 60000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return symbols;
}
