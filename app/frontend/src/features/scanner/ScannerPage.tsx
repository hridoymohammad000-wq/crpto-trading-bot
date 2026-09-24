import React, { useEffect, useState } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { StaleDataBanner } from "../../components/StaleDataBanner";
import { fetchScannerStatus, fetchScannerCandidates, fetchScannerWatchlist } from "../../api/scanner";

export const ScannerPage: React.FC = () => {
  const [status, setStatus] = useState<any>(null);
  const [universe, setUniverse] = useState<any[]>([]);
  const [watchlist, setWatchlist] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [statusData, candidatesData, watchlistData] = await Promise.all([
        fetchScannerStatus(),
        fetchScannerCandidates(),
        fetchScannerWatchlist()
      ]);
      setStatus(statusData);
      setUniverse(candidatesData); // Re-use the universe state for candidates
      setWatchlist(watchlistData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load scanner data");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div>
          <h2 className="text-base font-semibold font-mono text-slate-100">Opportunity Scanner</h2>
          <p className="text-xs text-slate-400 font-mono">
            {status ? `Showing ${universe.length} monitored candidates from ${status.eligible_count} eligible markets` : "Dynamic universe and watchlist evaluation"}
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={isLoading}
          className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-50"
        >
          <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-900/30 border border-red-800 rounded flex items-center gap-2 text-red-400 text-sm mb-4">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {status && (
        <StaleDataBanner
          lastUpdatedIso={status.last_refresh}
          dataSourceName="Scanner Universe"
          thresholdMinutes={15}
        />
      )}

      {status && (
        <div className="grid grid-cols-2 sm:grid-cols-6 gap-3">
          <div className="p-3 bg-slate-900 border border-slate-800 rounded">
            <div className="text-xs text-slate-400 mb-1">Universe</div>
            <div className="text-lg font-semibold text-slate-200">{status.universe_count}</div>
          </div>
          <div className="p-3 bg-slate-900 border border-slate-800 rounded">
            <div className="text-xs text-slate-400 mb-1">Eligible</div>
            <div className="text-lg font-semibold text-slate-200">{status.eligible_count}</div>
          </div>
          <div className="p-3 bg-slate-900 border border-slate-800 rounded">
            <div className="text-xs text-slate-400 mb-1">Watching</div>
            <div className="text-lg font-semibold text-amber-400">{watchlist?.symbol_states ? Object.values(watchlist.symbol_states).filter((state: any) => state?.state === "WATCHING").length : status.watching_count}</div>
          </div>
          <div className="p-3 bg-slate-900 border border-slate-800 rounded">
            <div className="text-xs text-slate-400 mb-1">Armed</div>
            <div className="text-lg font-semibold text-emerald-400">{status.armed_count}</div>
          </div>
          <div className="p-3 bg-slate-900 border border-slate-800 rounded">
            <div className="text-xs text-slate-400 mb-1">Triggered</div>
            <div className="text-lg font-semibold text-cyan-400">{universe.filter(o => o.state === "TRIGGERED").length || 0}</div>
          </div>
          <div className="p-3 bg-slate-900 border border-slate-800 rounded">
            <div className="text-xs text-slate-400 mb-1">Positions</div>
            <div className="text-lg font-semibold text-indigo-400">{status.open_positions}</div>
          </div>
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[10px] sm:text-xs text-slate-300">
            <thead className="bg-slate-800/50 text-slate-400 font-mono">
              <tr>
                <th className="px-2 py-2 font-medium">Symbol</th>
                <th className="px-2 py-2 font-medium">State</th>
                <th className="px-2 py-2 font-medium">Regime</th>
                <th className="px-2 py-2 font-medium">Bias</th>
                <th className="px-2 py-2 font-medium">15m Ctx</th>
                <th className="px-2 py-2 font-medium">5m Setup</th>
                <th className="px-2 py-2 font-medium">1m Trigger</th>
                <th className="px-2 py-2 font-medium">ADX</th>
                <th className="px-2 py-2 font-medium">RVOL</th>
                <th className="px-2 py-2 font-medium">Score(M/S)</th>
                <th className="px-2 py-2 font-medium">Allowed</th>
                <th className="px-2 py-2 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {universe.slice(0, 50).map((o) => {
                const isMonitored = watchlist?.core_symbols?.includes(o.symbol) || watchlist?.dynamic_symbols?.includes(o.symbol);
                const sState = watchlist?.symbol_states?.[o.symbol] || {};
                
                const currentState = sState.state || o.state;
                const context15m = sState.context_15m?.context_valid ? "PASS" : "FAIL";
                const setup5m = sState.setup_5m?.setup_valid ? "PASS" : "FAIL";
                const trigger1m = sState.trigger_1m?.trigger_status ? "PASS" : "WAIT";
                const allowed = sState.execution_allowed ? "YES" : "NO";
                
                const reasons = sState.reason_codes?.length ? sState.reason_codes.join(", ") : o.reason_codes?.join(", ") || "-";

                return (
                  <tr key={o.symbol} className={isMonitored ? "bg-slate-800/30" : ""}>
                    <td className="px-2 py-2 font-medium text-slate-200">
                      {o.symbol}
                      {isMonitored && <span className="ml-1 text-[9px] bg-indigo-500/20 text-indigo-300 px-1 rounded">M</span>}
                    </td>
                    <td className="px-2 py-2">
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold
                        ${currentState === "WATCHING" ? "bg-amber-500/20 text-amber-400" : 
                          currentState === "ARMED" ? "bg-emerald-500/20 text-emerald-400" : 
                          currentState === "TRIGGERED" ? "bg-cyan-500/20 text-cyan-400" : 
                          currentState === "EXECUTED" ? "bg-blue-500/20 text-blue-400" : 
                          currentState === "INVALIDATED" ? "bg-red-500/20 text-red-400" : 
                          "bg-slate-800 text-slate-400"}`}>
                        {currentState}
                      </span>
                    </td>
                    <td className="px-2 py-2 truncate max-w-[80px]">{o.regime?.replace("_", " ")}</td>
                    <td className="px-2 py-2">{o.bias || "-"}</td>
                    <td className={`px-2 py-2 font-mono ${context15m === "PASS" ? "text-emerald-400" : "text-slate-500"}`}>{context15m}</td>
                    <td className={`px-2 py-2 font-mono ${setup5m === "PASS" ? "text-emerald-400" : "text-slate-500"}`}>{setup5m}</td>
                    <td className={`px-2 py-2 font-mono ${trigger1m === "PASS" ? "text-cyan-400" : "text-slate-500"}`}>{trigger1m}</td>
                    <td className="px-2 py-2 font-mono">{o.adx?.toFixed(1) || "-"}</td>
                    <td className="px-2 py-2 font-mono">{o.rvol?.toFixed(2) || "-"}</td>
                    <td className="px-2 py-2">{o.market_quality_score}/{o.setup_quality_score}</td>
                    <td className={`px-2 py-2 font-mono ${allowed === "YES" ? "text-emerald-400" : "text-slate-500"}`}>{allowed}</td>
                    <td className="px-2 py-2 max-w-[120px] truncate" title={reasons}>
                      {reasons}
                    </td>
                  </tr>
                );
              })}
              {universe.length === 0 && !isLoading && (
                <tr>
                  <td colSpan={12} className="px-3 py-4 text-center text-slate-500">
                    No universe data available
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};


