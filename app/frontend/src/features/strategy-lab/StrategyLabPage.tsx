import React, { useEffect, useState } from 'react';
import { RefreshCw, Activity, AlertCircle } from 'lucide-react';
import { fetchScannerCandidates } from '../../api/scanner'; // Can reuse this to get universe symbols

interface LabWorker {
  name: string;
  last_signal_count: number;
  last_evaluation_count: number;
}

interface LabSignal {
  symbol: string;
  evaluation_time: string;
  has_signal: boolean;
  reason_codes: string[];
  signal?: {
    signal_id: string;
    side: 'BUY' | 'SELL';
    confidence: number;
    reference_entry_price: string;
    signal_time: string;
  };
}

export const StrategyLabPage: React.FC = () => {
  const [workers, setWorkers] = useState<LabWorker[]>([]);
  const [signals, setSignals] = useState<Record<string, LabSignal[]>>({});
  const [symbols, setSymbols] = useState<string>('BTCUSDT,ETHUSDT,SOLUSDT');
  const [isWorkersLoading, setIsWorkersLoading] = useState(true);
  const [isSignalsLoading, setIsSignalsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchWorkers = async () => {
    setIsWorkersLoading(true);
    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
      const response = await fetch(`${baseUrl}/strategy-lab/workers`);
      if (!response.ok) throw new Error('Failed to fetch workers');
      const data = await response.json();
      setWorkers(data.workers || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect to Strategy Lab');
    } finally {
      setIsWorkersLoading(false);
    }
  };

  const fetchSignals = async () => {
    setIsSignalsLoading(true);
    setError(null);
    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
      const response = await fetch(`${baseUrl}/strategy-lab/signals?symbols=${encodeURIComponent(symbols)}`);
      if (!response.ok) throw new Error('Failed to run strategies');
      const data = await response.json();
      setSignals(data.results || {});
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to evaluate strategies');
    } finally {
      setIsSignalsLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkers();
  }, []);

  return (
    <div className="space-y-4 max-w-[1400px]">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div>
          <h2 className="text-base font-semibold font-mono text-slate-100 flex items-center gap-2">
            <Activity size={18} className="text-emerald-400" />
            Strategy Lab
          </h2>
          <p className="text-xs text-slate-400 font-mono mt-1">
            Parallel multi-strategy execution and diagnostics engine
          </p>
        </div>
        <button
          onClick={fetchWorkers}
          disabled={isWorkersLoading}
          className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-50"
        >
          <RefreshCw size={14} className={isWorkersLoading ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-900/30 border border-red-800 rounded flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Workers Overview */}
      <div>
        <h3 className="text-sm font-semibold text-slate-300 mb-3 font-mono">Active Workers ({workers.length})</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {workers.map((worker) => (
            <div key={worker.name} className="p-3 bg-slate-900 border border-slate-800 rounded">
              <div className="text-xs font-semibold text-indigo-400 mb-2">{worker.name.replace('_STRATEGY', '').replace('_', ' ')}</div>
              <div className="flex justify-between text-xs text-slate-400 font-mono">
                <span>Evaluations:</span>
                <span className="text-slate-200">{worker.last_evaluation_count}</span>
              </div>
              <div className="flex justify-between text-xs text-slate-400 font-mono mt-1">
                <span>Signals found:</span>
                <span className={worker.last_signal_count > 0 ? 'text-emerald-400 font-semibold' : 'text-slate-500'}>
                  {worker.last_signal_count}
                </span>
              </div>
            </div>
          ))}
          {!isWorkersLoading && workers.length === 0 && (
            <div className="col-span-full p-4 text-center text-slate-500 text-sm border border-slate-800 rounded border-dashed">
              No workers registered in Strategy Lab.
            </div>
          )}
        </div>
      </div>

      {/* Test Environment */}
      <div className="bg-slate-900 border border-slate-800 rounded p-4">
        <h3 className="text-sm font-semibold text-slate-300 mb-3 font-mono">Run Diagnostics</h3>
        <div className="flex gap-2 mb-4">
          <input 
            type="text" 
            value={symbols} 
            onChange={(e) => setSymbols(e.target.value.toUpperCase())}
            placeholder="BTCUSDT,ETHUSDT"
            className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-sm font-mono text-slate-200 outline-none focus:border-indigo-500 transition-colors"
          />
          <button 
            onClick={fetchSignals}
            disabled={isSignalsLoading || !symbols.trim()}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white px-4 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-2"
          >
            {isSignalsLoading ? <RefreshCw size={14} className="animate-spin" /> : <Activity size={14} />}
            Evaluate
          </button>
        </div>

        {Object.keys(signals).length > 0 && (
          <div className="space-y-6 mt-6">
            {Object.entries(signals).map(([strategyName, evals]) => (
              <div key={strategyName}>
                <h4 className="text-xs font-semibold text-slate-400 mb-2 font-mono uppercase tracking-wider border-b border-slate-800/50 pb-1">
                  {strategyName}
                </h4>
                <div className="overflow-x-auto rounded border border-slate-800">
                  <table className="w-full text-left text-[11px] sm:text-xs text-slate-300 whitespace-nowrap">
                    <thead className="bg-slate-800/50 text-slate-400 font-mono">
                      <tr>
                        <th className="px-3 py-2 font-medium">Symbol</th>
                        <th className="px-3 py-2 font-medium">Result</th>
                        <th className="px-3 py-2 font-medium">Side</th>
                        <th className="px-3 py-2 font-medium">Price</th>
                        <th className="px-3 py-2 font-medium">Confidence</th>
                        <th className="px-3 py-2 font-medium">Reasons</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {evals.map((ev, i) => (
                        <tr key={i} className="hover:bg-slate-800/30">
                          <td className="px-3 py-2 font-medium text-slate-200">{ev.symbol}</td>
                          <td className="px-3 py-2">
                            {ev.has_signal ? (
                              <span className="text-emerald-400 font-semibold bg-emerald-400/10 px-1.5 py-0.5 rounded">SIGNAL</span>
                            ) : (
                              <span className="text-slate-500">NO SIGNAL</span>
                            )}
                          </td>
                          <td className="px-3 py-2 font-mono">
                            {ev.signal?.side === 'BUY' && <span className="text-emerald-400">LONG</span>}
                            {ev.signal?.side === 'SELL' && <span className="text-red-400">SHORT</span>}
                            {!ev.signal && '-'}
                          </td>
                          <td className="px-3 py-2 font-mono">{ev.signal?.reference_entry_price || '-'}</td>
                          <td className="px-3 py-2 font-mono">{ev.signal ? `${ev.signal.confidence}%` : '-'}</td>
                          <td className="px-3 py-2 text-[10px] truncate max-w-[300px]" title={ev.reason_codes.join(', ')}>
                            {ev.reason_codes.join(', ') || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
