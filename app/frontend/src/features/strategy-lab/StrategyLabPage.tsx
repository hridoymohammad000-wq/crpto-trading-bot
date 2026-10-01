import React, { useEffect, useMemo, useState } from 'react';
import { Activity, AlertCircle, BarChart3, RefreshCw, TrendingDown, TrendingUp } from 'lucide-react';

interface LabWorker { name: string; last_signal_count: number; last_evaluation_count: number; }
interface EvaluationSignal { signal_id: string; strategy: string; side: 'BUY' | 'SELL'; confidence: number; reference_entry_price: string; signal_time: string; }
interface LabEvaluation { symbol: string; evaluation_time: string; has_signal: boolean; reason_codes: string[]; signal?: EvaluationSignal; }
interface LabHistorySignal {
  signal_id: string; strategy: string; symbol: string; side: 'BUY' | 'SELL'; signal_time: string; entry_price: string;
  confidence: number; status: string; current_price: string | null; pnl_pct: string | null; last_marked_at: string | null;
  stop_loss?: string | null; take_profit?: string | null; closed_at?: string | null; exit_reason?: string | null; diagnostic_reason?: string | null;
  adx?: string | null; rsi?: string | null; crossover_age_candles?: number | null;
  fund_starting_balance?: string | null; risk_pct?: string | null; risk_amount?: string | null;
  position_size?: string | null; pnl_usdt?: string | null; r_multiple?: string | null;
  exit_price?: string | null; balance_after_close?: string | null;
}
interface StrategyPerformance {
  strategy: string; total_signals: number; total_trades: number; open_signals: number; closed_trades: number; wins: number; losses: number;
  sl_hits: number; tp_hits: number; expired: number; win_rate_pct: string; net_pnl_pct: string; avg_r: string | null;
  marked_signals: number; positive_marks: number; negative_marks: number; avg_pnl_pct: string | null; best_pnl_pct: string | null;
  worst_pnl_pct: string | null; last_signal_time: string | null;
  starting_balance: string; realized_pnl_usdt: string; open_pnl_usdt: string;
  current_equity: string; return_pct: string; last_balance_after_close?: string | null;
}

const formatStrategyName = (name: string) => name.replace('_STRATEGY', '').replaceAll('_', ' ');
const formatPrice = (value?: string | null) => {
  if (!value) return '-';
  const number = Number(value);
  if (!Number.isFinite(number)) return value;
  return number.toLocaleString(undefined, { minimumFractionDigits: number >= 1000 ? 2 : 2, maximumFractionDigits: number >= 1000 ? 2 : 4 });
};
const formatPnl = (value?: string | null) => {
  if (value == null) return '-';
  const number = Number(value);
  if (!Number.isFinite(number)) return value;
  return `${number > 0 ? '+' : ''}${number.toFixed(3)}%`;
};
const formatDate = (value?: string | null) => {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
};

export const StrategyLabPage: React.FC = () => {
  const [workers, setWorkers] = useState<LabWorker[]>([]);
  const [evaluations, setEvaluations] = useState<Record<string, LabEvaluation[]>>({});
  const [history, setHistory] = useState<LabHistorySignal[]>([]);
  const [performance, setPerformance] = useState<StrategyPerformance[]>([]);
  const [symbols, setSymbols] = useState('BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,AVAXUSDT,LINKUSDT,DOTUSDT');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [marking, setMarking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '';

  const fetchWorkers = async () => {
    const response = await fetch(`${baseUrl}/strategy-lab/workers`);
    if (!response.ok) throw new Error('Failed to fetch Strategy Lab workers');
    const data = await response.json(); setWorkers(data.workers || []);
  };
  const fetchHistory = async () => {
    const response = await fetch(`${baseUrl}/strategy-lab/history?limit=100`);
    if (!response.ok) throw new Error('Failed to fetch Strategy Lab history');
    const data = await response.json(); setHistory(data.signals || []);
  };
  const fetchPerformance = async () => {
    const response = await fetch(`${baseUrl}/strategy-lab/performance`);
    if (!response.ok) throw new Error('Failed to fetch Strategy Lab performance');
    const data = await response.json(); setPerformance(data.strategies || []);
  };
  const refresh = async () => {
    setLoading(true); setError(null);
    try { await Promise.all([fetchWorkers(), fetchHistory(), fetchPerformance()]); }
    catch (err) { setError(err instanceof Error ? err.message : 'Failed to refresh Strategy Lab'); }
    finally { setLoading(false); }
  };
  const runDiagnostics = async () => {
    if (!symbols.trim()) return;
    setRunning(true); setError(null);
    try {
      const response = await fetch(`${baseUrl}/strategy-lab/signals?symbols=${encodeURIComponent(symbols)}`);
      if (!response.ok) throw new Error('Failed to run Strategy Lab evaluation');
      const data = await response.json(); setEvaluations(data.results || {});
      await Promise.all([fetchWorkers(), fetchHistory(), fetchPerformance()]);
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed to evaluate strategies'); }
    finally { setRunning(false); }
  };
  const mark = async () => {
    setMarking(true); setError(null);
    try {
      const response = await fetch(`${baseUrl}/strategy-lab/mark`, { method: 'POST' });
      if (!response.ok) throw new Error('Failed to mark Strategy Lab paper trades');
      await response.json(); await Promise.all([fetchHistory(), fetchPerformance()]);
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed to mark Strategy Lab paper trades'); }
    finally { setMarking(false); }
  };
  useEffect(() => { refresh(); }, []);

  const totals = useMemo(() => performance.reduce((acc, item) => ({
    total: acc.total + (item.total_trades ?? item.total_signals ?? 0),
    open: acc.open + (item.open_signals || 0),
    closed: acc.closed + (item.closed_trades || 0),
    wins: acc.wins + (item.wins || 0),
    losses: acc.losses + (item.losses || 0),
    sl: acc.sl + (item.sl_hits || 0),
    tp: acc.tp + (item.tp_hits || 0),
    net: acc.net + Number(item.net_pnl_pct || 0),
  }), { total: 0, open: 0, closed: 0, wins: 0, losses: 0, sl: 0, tp: 0, net: 0 }), [performance]);
  const strategyOrder = [
    'ICT_STRATEGY',
    'SMC_STRATEGY',
    'AMD_STRATEGY',
    'LIQUIDITY_SWEEP',
  ];

  const visiblePerformance = strategyOrder.map((strategy) => {
    const found = performance.find((item) => item.strategy === strategy);

    return found || {
      strategy,
      total_signals: 0,
      total_trades: 0,
      open_signals: 0,
      closed_trades: 0,
      wins: 0,
      losses: 0,
      sl_hits: 0,
      tp_hits: 0,
      expired: 0,
      win_rate_pct: '0',
      net_pnl_pct: '0',
      avg_r: null,
      marked_signals: 0,
      positive_marks: 0,
      negative_marks: 0,
      avg_pnl_pct: null,
      best_pnl_pct: null,
      worst_pnl_pct: null,
      last_signal_time: null,
      starting_balance: '100',
      realized_pnl_usdt: '0',
      open_pnl_usdt: '0',
      current_equity: '100',
      return_pct: '0',
      last_balance_after_close: null,
    } as StrategyPerformance;
  });
  const resolved = totals.wins + totals.losses;
  const winRate = resolved ? (totals.wins / resolved) * 100 : 0;

  const metricCards = [
    ['Total Paper Trades', totals.total, 'text-slate-100'], ['Open', totals.open, 'text-cyan-400'], ['Closed', totals.closed, 'text-indigo-400'],
    ['Wins', totals.wins, 'text-emerald-400'], ['Losses', totals.losses, 'text-rose-400'], ['SL Hit', totals.sl, 'text-rose-300'],
    ['TP Hit', totals.tp, 'text-emerald-300'], ['Win Rate', `${winRate.toFixed(1)}%`, 'text-amber-300'],
  ] as const;

  return (
    <div className="space-y-5 w-full max-w-none">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between pb-3 border-b border-slate-800">
        <div>
          <h2 className="text-base font-semibold font-mono text-slate-100 flex items-center gap-2"><Activity size={18} className="text-emerald-400" />Strategy Lab</h2>
          <p className="text-xs text-slate-400 font-mono mt-1">Paper-only research ledger Ã¢â‚¬Â¢ fixed benchmark: 1% paper SL / 2% paper TP (2R) Ã¢â‚¬Â¢ never submits exchange orders</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={mark} disabled={marking || history.length === 0} className="flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-medium disabled:bg-slate-800 disabled:text-slate-500"><BarChart3 size={14} />{marking ? 'MarkingÃ¢â‚¬Â¦' : 'Mark Paper PnL'}</button>
          <button onClick={refresh} disabled={loading || marking} className="p-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-50" title="Refresh Strategy Lab"><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /></button>
        </div>
      </div>

      {error && <div className="p-3 bg-red-900/30 border border-red-800 rounded flex items-center gap-2 text-red-400 text-sm"><AlertCircle size={16} />{error}</div>}

      <section>
        <h3 className="text-sm font-semibold text-slate-300 mb-3 font-mono">Paper Trade Overview</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3">
          {metricCards.map(([label, value, cls]) => <div key={label} className="bg-slate-900 border border-slate-800 rounded p-3"><div className="text-[10px] text-slate-500 uppercase font-mono">{label}</div><div className={`text-xl font-semibold mt-1 ${cls}`}>{value}</div></div>)}
        </div>
        <div className="mt-2 text-[11px] font-mono text-slate-500">Closed paper net PnL: <span className={totals.net >= 0 ? 'text-emerald-400' : 'text-rose-400'}>{totals.net >= 0 ? '+' : ''}{totals.net.toFixed(3)}%</span>. Floating positive/negative marks are not counted as wins/losses.</div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-slate-300 mb-3 font-mono">Active Workers ({workers.length})</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 2xl:grid-cols-4 gap-3">
          {workers.map((worker) => <div key={worker.name} className="p-3 bg-slate-900 border border-slate-800 rounded"><div className="text-xs font-semibold text-indigo-400 mb-2">{formatStrategyName(worker.name)}</div><div className="flex justify-between text-xs text-slate-400 font-mono"><span>Evaluations</span><span className="text-slate-200">{worker.last_evaluation_count}</span></div><div className="flex justify-between text-xs text-slate-400 font-mono mt-1"><span>Signals found</span><span className={worker.last_signal_count ? 'text-emerald-400' : 'text-slate-500'}>{worker.last_signal_count}</span></div></div>)}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-slate-300 mb-3 font-mono">Strategy Performance</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 2xl:grid-cols-4 gap-3">
          {visiblePerformance.map((item) => {
            const net = Number(item.net_pnl_pct || 0);
            return <div key={item.strategy} className="bg-slate-900 border border-slate-800 rounded p-4">
              <div className="flex items-center justify-between mb-3"><span className="text-xs font-semibold text-indigo-400">{formatStrategyName(item.strategy)}</span>{net >= 0 ? <TrendingUp size={16} className="text-emerald-400" /> : <TrendingDown size={16} className="text-rose-400" />}</div>
              <div className="space-y-1.5 text-xs font-mono">
                <div className="flex justify-between text-slate-400"><span>Total / Open</span><span className="text-slate-200">{item.total_trades ?? item.total_signals} / {item.open_signals}</span></div>
                <div className="flex justify-between text-slate-400"><span>Closed</span><span className="text-indigo-300">{item.closed_trades || 0}</span></div>
                <div className="flex justify-between text-slate-400"><span>Wins / Losses</span><span><span className="text-emerald-400">{item.wins || 0}</span> / <span className="text-rose-400">{item.losses || 0}</span></span></div>
                <div className="flex justify-between text-slate-400"><span>SL / TP Hit</span><span><span className="text-rose-300">{item.sl_hits || 0}</span> / <span className="text-emerald-300">{item.tp_hits || 0}</span></span></div>
                <div className="flex justify-between text-slate-400"><span>Win Rate</span><span className="text-amber-300">{Number(item.win_rate_pct || 0).toFixed(1)}%</span></div>
                <div className="flex justify-between border-t border-slate-800 pt-2 text-slate-400"><span>Starting Fund</span><span className="text-slate-200">${Number(item.starting_balance || 100).toFixed(2)}</span></div>
                <div className="flex justify-between text-slate-400"><span>Current Equity</span><span className="text-cyan-300">${Number(item.current_equity || 100).toFixed(2)}</span></div>
                <div className="flex justify-between text-slate-400"><span>Realized PnL</span><span className={Number(item.realized_pnl_usdt || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}>${Number(item.realized_pnl_usdt || 0).toFixed(2)}</span></div>
                <div className="flex justify-between text-slate-400"><span>Open PnL</span><span className={Number(item.open_pnl_usdt || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}>${Number(item.open_pnl_usdt || 0).toFixed(2)}</span></div>
                <div className="flex justify-between text-slate-400"><span>Return</span><span className={Number(item.return_pct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}>{Number(item.return_pct || 0).toFixed(2)}%</span></div>
                <div className="flex justify-between text-slate-400"><span>Closed Net</span><span className={net >= 0 ? 'text-emerald-400' : 'text-rose-400'}>{formatPnl(item.net_pnl_pct)}</span></div>
                <div className="flex justify-between text-slate-400"><span>Avg R</span><span className="text-slate-200">{item.avg_r == null ? '-' : `${Number(item.avg_r).toFixed(2)}R`}</span></div>
              </div>
            </div>;
          })}
        </div>
      </section>
      <section>
        <div className="flex items-end justify-between gap-3 mb-3"><div><h3 className="text-sm font-semibold text-slate-300 font-mono">Paper Trade Ledger</h3><p className="text-[11px] font-mono text-slate-500 mt-1">OPEN is floating. Only TP_HIT / SL_HIT are counted as closed wins/losses. SL diagnostics are heuristic and shown explicitly as such.</p></div><span className="text-xs font-mono text-slate-500">{history.length} rows</span></div>
        <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
          <div className="max-h-[560px] overflow-auto"><table className="w-full min-w-[1750px] text-left text-xs font-mono">
            <thead className="sticky top-0 z-10 bg-slate-950 text-slate-400 shadow-sm"><tr><th className="px-3 py-2">Time</th><th className="px-3 py-2">Strategy</th><th className="px-3 py-2">Symbol</th><th className="px-3 py-2">Side</th><th className="px-3 py-2 text-right">Entry</th><th className="px-3 py-2 text-right">Qty</th><th className="px-3 py-2 text-right">Risk</th><th className="px-3 py-2 text-right">Paper SL</th><th className="px-3 py-2 text-right">Paper TP</th><th className="px-3 py-2 text-right">Current/Exit</th><th className="px-3 py-2 text-right">PnL $</th><th className="px-3 py-2 text-right">PnL %</th><th className="px-3 py-2 text-right">R</th><th className="px-3 py-2 text-right">Balance</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">SL / Exit Reason</th></tr></thead>
            <tbody className="divide-y divide-slate-800/60">
              {history.map((row) => { const pnl = row.pnl_pct == null ? null : Number(row.pnl_pct); return <tr key={row.signal_id} className="text-slate-300"><td className="px-3 py-2 whitespace-nowrap text-slate-500">{formatDate(row.signal_time)}</td><td className="px-3 py-2 whitespace-nowrap text-indigo-300">{formatStrategyName(row.strategy)}</td><td className="px-3 py-2 font-semibold text-slate-100">{row.symbol}</td><td className="px-3 py-2">{row.side}</td><td className="px-3 py-2 text-right">{formatPrice(row.entry_price)}</td><td className="px-3 py-2 text-right">{row.position_size ? Number(row.position_size).toFixed(6) : '-'}</td><td className="px-3 py-2 text-right text-amber-300">{row.risk_amount ? `$${Number(row.risk_amount).toFixed(2)} (${Number(row.risk_pct || 0).toFixed(1)}%)` : '-'}</td><td className="px-3 py-2 text-right text-rose-300">{formatPrice(row.stop_loss)}</td><td className="px-3 py-2 text-right text-emerald-300">{formatPrice(row.take_profit)}</td><td className="px-3 py-2 text-right">{formatPrice(row.exit_price || row.current_price)}</td><td className={`px-3 py-2 text-right font-semibold ${Number(row.pnl_usdt || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{row.pnl_usdt == null ? '-' : `${Number(row.pnl_usdt) >= 0 ? '+' : ''}$${Number(row.pnl_usdt).toFixed(2)}`}</td><td className={`px-3 py-2 text-right font-semibold ${pnl == null ? 'text-slate-500' : pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{formatPnl(row.pnl_pct)}</td><td className="px-3 py-2 text-right">{row.r_multiple == null ? '-' : `${Number(row.r_multiple).toFixed(2)}R`}</td><td className="px-3 py-2 text-right text-cyan-300">{row.balance_after_close == null ? '-' : `$${Number(row.balance_after_close).toFixed(2)}`}</td><td className="px-3 py-2"><span className={`rounded px-1.5 py-0.5 text-[10px] ${row.status === 'TP_HIT' ? 'bg-emerald-950 text-emerald-300' : row.status === 'SL_HIT' ? 'bg-rose-950 text-rose-300' : 'bg-cyan-950 text-cyan-300'}`}>{row.status === 'OPEN' ? 'PAPER OPEN' : row.status}</span></td><td className="px-3 py-2 min-w-[280px]"><div className="text-slate-300">{row.exit_reason || '-'}</div><div className="mt-0.5 text-[10px] text-slate-500">{row.diagnostic_reason || (row.status === 'OPEN' ? 'Still open; no loss diagnosis yet.' : '-')}</div></td></tr>; })}
              {!loading && history.length === 0 && <tr><td colSpan={16} className="px-3 py-6 text-center text-slate-500">No persisted paper trades yet.</td></tr>}
            </tbody>
          </table></div></div></section>
    </div>
  );
};


