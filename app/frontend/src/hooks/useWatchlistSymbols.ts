import { useEffect, useState } from 'react';
import { fetchScannerCandidates } from '../api/scanner';
import { TradingSymbol } from '../types';

/**
 * Chart universe mirrors the actionable scanner view: both quality scores >= 60,
 * ranked by the weaker of the two scores, then by combined score, Top 10.
 */
export function useWatchlistSymbols(): TradingSymbol[] {
  const [symbols, setSymbols] = useState<TradingSymbol[]>([]);

  useEffect(() => {
    let mounted = true;

    async function fetchSymbols() {
      try {
        const candidates = await fetchScannerCandidates();
        if (!mounted || !Array.isArray(candidates)) return;

        const qualified = [...candidates]
          .filter((candidate: any) =>
            Number(candidate.market_quality_score) >= 60 &&
            Number(candidate.setup_quality_score) >= 60
          )
          .sort((a: any, b: any) => {
            const aMin = Math.min(Number(a.market_quality_score) || 0, Number(a.setup_quality_score) || 0);
            const bMin = Math.min(Number(b.market_quality_score) || 0, Number(b.setup_quality_score) || 0);
            if (bMin !== aMin) return bMin - aMin;
            return (Number(b.market_quality_score) + Number(b.setup_quality_score)) -
              (Number(a.market_quality_score) + Number(a.setup_quality_score));
          })
          .slice(0, 10)
          .map((candidate: any) => candidate.symbol)
          .filter(Boolean) as TradingSymbol[];

        setSymbols(Array.from(new Set(qualified)));
      } catch (err) {
        console.error('Failed to load qualified scanner symbols for chart:', err);
      }
    }

    fetchSymbols();
    const interval = setInterval(fetchSymbols, 60000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return symbols;
}
