import React, { useEffect, useState } from 'react';
import {
  Activity,
  AlertCircle,
  BarChart3,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';

interface LabWorker {
  name: string;
  last_signal_count: number;
  last_evaluation_count: number;
}

interface EvaluationSignal {
  signal_id: string;
  strategy: string;
  side: 'BUY' | 'SELL';
  confidence: number;
  reference_entry_price: string;
  signal_time: string;
}

interface LabEvaluation {
  symbol: string;
  evaluation_time: string;
  has_signal: boolean;
  reason_codes: string[];
  signal?: EvaluationSignal;
}

interface LabHistorySignal {
  signal_id: string;
  strategy: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  signal_time: string;
  entry_price: string;
  confidence: number;
  status: string;
  current_price: string | null;
  pnl_pct: string | null;
  last_marked_at: string | null;
}

interface StrategyPerformance {
  strategy: string;
  total_signals: number;
  open_signals: number;
  marked_signals: number;
  positive_marks: number;
  negative_marks: number;
  avg_pnl_pct: string | null;
  best_pnl_pct: string | null;
  worst_pnl_pct: string | null;
  last_signal_time: string | null;
}

const formatStrategyName = (name: string) =>
  name
    .replace('_STRATEGY', '')
    .replaceAll('_', ' ');

const formatPrice = (value: string | null) => {
  if (value === null) return '-';

  const number = Number(value);

  if (!Number.isFinite(number)) {
    return value;
  }

  if (number >= 1000) {
    return number.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  return number.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
};

const formatPnl = (value: string | null) => {
  if (value === null) return '-';

  const number = Number(value);

  if (!Number.isFinite(number)) {
    return value;
  }

  const prefix = number > 0 ? '+' : '';

  return `${prefix}${number.toFixed(3)}%`;
};

const formatDate = (value: string | null) => {
  if (!value) return '-';

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
};

export const StrategyLabPage: React.FC = () => {
  const [workers, setWorkers] = useState<LabWorker[]>([]);
  const [signals, setSignals] = useState<
    Record<string, LabEvaluation[]>
  >({});

  const [history, setHistory] = useState<LabHistorySignal[]>([]);
  const [performance, setPerformance] = useState<
    StrategyPerformance[]
  >([]);

  const [symbols, setSymbols] = useState(
    'BTCUSDT,ETHUSDT,SOLUSDT'
  );

  const [isWorkersLoading, setIsWorkersLoading] =
    useState(true);

  const [isSignalsLoading, setIsSignalsLoading] =
    useState(false);

  const [isHistoryLoading, setIsHistoryLoading] =
    useState(true);

  const [isMarking, setIsMarking] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const baseUrl =
    import.meta.env.VITE_API_BASE_URL || '';

  const fetchWorkers = async () => {
    setIsWorkersLoading(true);

    try {
      const response = await fetch(
        `${baseUrl}/strategy-lab/workers`
      );

      if (!response.ok) {
        throw new Error(
          'Failed to fetch Strategy Lab workers'
        );
      }

      const data = await response.json();

      setWorkers(data.workers || []);
    } finally {
      setIsWorkersLoading(false);
    }
  };

  const fetchHistory = async () => {
    setIsHistoryLoading(true);

    try {
      const response = await fetch(
        `${baseUrl}/strategy-lab/history?limit=100`
      );

      if (!response.ok) {
        throw new Error(
          'Failed to fetch Strategy Lab history'
        );
      }

      const data = await response.json();

      setHistory(data.signals || []);
    } finally {
      setIsHistoryLoading(false);
    }
  };

  const fetchPerformance = async () => {
    const response = await fetch(
      `${baseUrl}/strategy-lab/performance`
    );

    if (!response.ok) {
      throw new Error(
        'Failed to fetch Strategy Lab performance'
      );
    }

    const data = await response.json();

    setPerformance(data.strategies || []);
  };

  const refreshDashboard = async () => {
    setError(null);

    try {
      await Promise.all([
        fetchWorkers(),
        fetchHistory(),
        fetchPerformance(),
      ]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to refresh Strategy Lab'
      );
    }
  };

  const fetchSignals = async () => {
    if (!symbols.trim()) {
      return;
    }

    setIsSignalsLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${baseUrl}/strategy-lab/signals?symbols=${encodeURIComponent(
          symbols
        )}`
      );

      if (!response.ok) {
        throw new Error(
          'Failed to run Strategy Lab evaluation'
        );
      }

      const data = await response.json();

      setSignals(data.results || {});

      await Promise.all([
        fetchWorkers(),
        fetchHistory(),
        fetchPerformance(),
      ]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to evaluate strategies'
      );
    } finally {
      setIsSignalsLoading(false);
    }
  };

  const markSignals = async () => {
    setIsMarking(true);
    setError(null);

    try {
      const response = await fetch(
        `${baseUrl}/strategy-lab/mark`,
        {
          method: 'POST',
        }
      );

      if (!response.ok) {
        throw new Error(
          'Failed to mark Strategy Lab signals'
        );
      }

      await response.json();

      await Promise.all([
        fetchHistory(),
        fetchPerformance(),
      ]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to mark Strategy Lab signals'
      );
    } finally {
      setIsMarking(false);
    }
  };

  useEffect(() => {
    refreshDashboard();
  }, []);

  const totalSignals = performance.reduce(
    (sum, item) => sum + item.total_signals,
    0
  );

  const totalMarked = performance.reduce(
    (sum, item) => sum + item.marked_signals,
    0
  );

  const totalPositive = performance.reduce(
    (sum, item) => sum + item.positive_marks,
    0
  );

  const totalNegative = performance.reduce(
    (sum, item) => sum + item.negative_marks,
    0
  );

  return (
    <div className="space-y-5 max-w-[1500px]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between pb-3 border-b border-slate-800">
        <div>
          <h2 className="text-base font-semibold font-mono text-slate-100 flex items-center gap-2">
            <Activity
              size={18}
              className="text-emerald-400"
            />
            Strategy Lab
          </h2>

          <p className="text-xs text-slate-400 font-mono mt-1">
            Paper-only multi-strategy research,
            persistence and mark-to-market analytics
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={markSignals}
            disabled={isMarking || history.length === 0}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-medium disabled:bg-slate-800 disabled:text-slate-500 transition-colors"
          >
            <BarChart3 size={14} />

            {isMarking
              ? 'Marking...'
              : 'Mark PnL'}
          </button>

          <button
            onClick={refreshDashboard}
            disabled={
              isWorkersLoading ||
              isHistoryLoading ||
              isMarking
            }
            className="p-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-50"
            title="Refresh Strategy Lab"
          >
            <RefreshCw
              size={14}
              className={
                isWorkersLoading ||
                isHistoryLoading
                  ? 'animate-spin'
                  : ''
              }
            />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-900/30 border border-red-800 rounded flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div>
        <h3 className="text-sm font-semibold text-slate-300 mb-3 font-mono">
          Active Workers ({workers.length})
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {workers.map((worker) => (
            <div
              key={worker.name}
              className="p-3 bg-slate-900 border border-slate-800 rounded"
            >
              <div className="text-xs font-semibold text-indigo-400 mb-2">
                {formatStrategyName(worker.name)}
              </div>

              <div className="flex justify-between text-xs text-slate-400 font-mono">
                <span>Evaluations</span>
                <span className="text-slate-200">
                  {worker.last_evaluation_count}
                </span>
              </div>

              <div className="flex justify-between text-xs text-slate-400 font-mono mt-1">
                <span>Signals found</span>

                <span
                  className={
                    worker.last_signal_count > 0
                      ? 'text-emerald-400 font-semibold'
                      : 'text-slate-500'
                  }
                >
                  {worker.last_signal_count}
                </span>
              </div>
            </div>
          ))}

          {!isWorkersLoading &&
            workers.length === 0 && (
              <div className="col-span-full p-4 text-center text-slate-500 text-sm border border-slate-800 rounded border-dashed">
                No Strategy Lab workers registered.
              </div>
            )}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-300 mb-3 font-mono">
          Lab Overview
        </h3>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-slate-900 border border-slate-800 rounded p-3">
            <div className="text-[11px] text-slate-500 uppercase font-mono">
              Total Signals
            </div>

            <div className="text-xl font-semibold text-slate-100 mt-1">
              {totalSignals}
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded p-3">
            <div className="text-[11px] text-slate-500 uppercase font-mono">
              Marked
            </div>

            <div className="text-xl font-semibold text-indigo-400 mt-1">
              {totalMarked}
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded p-3">
            <div className="text-[11px] text-slate-500 uppercase font-mono">
              Positive
            </div>

            <div className="text-xl font-semibold text-emerald-400 mt-1">
              {totalPositive}
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded p-3">
            <div className="text-[11px] text-slate-500 uppercase font-mono">
              Negative
            </div>

            <div className="text-xl font-semibold text-red-400 mt-1">
              {totalNegative}
            </div>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-300 mb-3 font-mono">
          Strategy Performance
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {performance.map((item) => {
            const avg = item.avg_pnl_pct
              ? Number(item.avg_pnl_pct)
              : null;

            return (
              <div
                key={item.strategy}
                className="bg-slate-900 border border-slate-800 rounded p-4"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold text-indigo-400">
                    {formatStrategyName(
                      item.strategy
                    )}
                  </span>

                  {avg !== null &&
                    (avg >= 0 ? (
                      <TrendingUp
                        size={16}
                        className="text-emerald-400"
                      />
                    ) : (
                      <TrendingDown
                        size={16}
                        className="text-red-400"
                      />
                    ))}
                </div>

                <div className="space-y-1.5 text-xs font-mono">
                  <div className="flex justify-between text-slate-400">
                    <span>Signals</span>
                    <span className="text-slate-200">
                      {item.total_signals}
                    </span>
                  </div>

                  <div className="flex justify-between text-slate-400">
                    <span>Marked</span>
                    <span className="text-slate-200">
                      {item.marked_signals}
                    </span>
                  </div>

                  <div className="flex justify-between text-slate-400">
                    <span>Positive</span>
                    <span className="text-emerald-400">
                      {item.positive_marks}
                    </span>
                  </div>

                  <div className="flex justify-between text-slate-400">
                    <span>Negative</span>
                    <span className="text-red-400">
                      {item.negative_marks}
                    </span>
                  </div>

                  <div className="border-t border-slate-800 pt-2 mt-2 flex justify-between text-slate-400">
                    <span>Avg PnL</span>

                    <span
                      className={
                        avg === null
                          ? 'text-slate-500'
                          : avg >= 0
                            ? 'text-emerald-400'
                            : 'text-red-400'
                      }
                    >
                      {formatPnl(
                        item.avg_pnl_pct
                      )}
                    </span>
                  </div>

                  <div className="flex justify-between text-slate-400">
                    <span>Best</span>
                    <span className="text-emerald-400">
                      {formatPnl(
                        item.best_pnl_pct
                      )}
                    </span>
                  </div>

                  <div className="flex justify-between text-slate-400">
                    <span>Worst</span>
                    <span className="text-red-400">
                      {formatPnl(
                        item.worst_pnl_pct
                      )}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}

          {!isHistoryLoading &&
            performance.length === 0 && (
              <div className="col-span-full p-4 text-center text-slate-500 border border-dashed border-slate-800 rounded text-sm">
                No persisted Strategy Lab signals
                yet.
              </div>
            )}
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded p-4">
        <h3 className="text-sm font-semibold text-slate-300 mb-3 font-mono">
          Run Diagnostics
        </h3>

        <div className="flex flex-col sm:flex-row gap-2 mb-4">
          <input
            type="text"
            value={symbols}
            onChange={(event) =>
              setSymbols(
                event.target.value.toUpperCase()
              )
            }
            placeholder="BTCUSDT,ETHUSDT,SOLUSDT"
            className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-sm font-mono text-slate-200 outline-none focus:border-indigo-500 transition-colors"
          />

          <button
            onClick={fetchSignals}
            disabled={
              isSignalsLoading ||
              !symbols.trim()
            }
            className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white px-4 py-1.5 rounded text-sm font-medium transition-colors flex items-center justify-center gap-2"
          >
            {isSignalsLoading ? (
              <RefreshCw
                size={14}
                className="animate-spin"
              />
            ) : (
              <Activity size={14} />
            )}

            Evaluate
          </button>
        </div>

        {Object.keys(signals).length > 0 && (
          <div className="space-y-6 mt-6">
            {Object.entries(signals).map(
              ([strategyName, evaluations]) => (
                <div key={strategyName}>
                  <h4 className="text-xs font-semibold text-slate-400 mb-2 font-mono uppercase tracking-wider border-b border-slate-800/50 pb-1">
                    {formatStrategyName(
                      strategyName
                    )}
                  </h4>

                  <div className="overflow-x-auto rounded border border-slate-800">
                    <table className="w-full text-left text-[11px] sm:text-xs text-slate-300 whitespace-nowrap">
                      <thead className="bg-slate-800/50 text-slate-400 font-mono">
                        <tr>
                          <th className="px-3 py-2 font-medium">
                            Symbol
                          </th>

                          <th className="px-3 py-2 font-medium">
                            Result
                          </th>

                          <th className="px-3 py-2 font-medium">
                            Side
                          </th>

                          <th className="px-3 py-2 font-medium">
                            Price
                          </th>

                          <th className="px-3 py-2 font-medium">
                            Confidence
                          </th>

                          <th className="px-3 py-2 font-medium">
                            Reasons
                          </th>
                        </tr>
                      </thead>

                      <tbody className="divide-y divide-slate-800/50">
                        {evaluations.map(
                          (evaluation, index) => (
                            <tr
                              key={`${evaluation.symbol}-${index}`}
                              className="hover:bg-slate-800/30"
                            >
                              <td className="px-3 py-2 font-medium text-slate-200">
                                {
                                  evaluation.symbol
                                }
                              </td>

                              <td className="px-3 py-2">
                                {evaluation.has_signal ? (
                                  <span className="text-emerald-400 font-semibold bg-emerald-400/10 px-1.5 py-0.5 rounded">
                                    SIGNAL
                                  </span>
                                ) : (
                                  <span className="text-slate-500">
                                    NO SIGNAL
                                  </span>
                                )}
                              </td>

                              <td className="px-3 py-2 font-mono">
                                {evaluation.signal
                                  ?.side ===
                                  'BUY' && (
                                  <span className="text-emerald-400">
                                    LONG
                                  </span>
                                )}

                                {evaluation.signal
                                  ?.side ===
                                  'SELL' && (
                                  <span className="text-red-400">
                                    SHORT
                                  </span>
                                )}

                                {!evaluation.signal &&
                                  '-'}
                              </td>

                              <td className="px-3 py-2 font-mono">
                                {evaluation.signal
                                  ? formatPrice(
                                      evaluation
                                        .signal
                                        .reference_entry_price
                                    )
                                  : '-'}
                              </td>

                              <td className="px-3 py-2 font-mono">
                                {evaluation.signal
                                  ? `${evaluation.signal.confidence}%`
                                  : '-'}
                              </td>

                              <td
                                className="px-3 py-2 text-[10px] truncate max-w-[300px]"
                                title={evaluation.reason_codes.join(
                                  ', '
                                )}
                              >
                                {evaluation.reason_codes.join(
                                  ', '
                                ) || '-'}
                              </td>
                            </tr>
                          )
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            )}
          </div>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-300 font-mono">
            Recent Lab Signals
          </h3>

          <span className="text-[11px] text-slate-500 font-mono">
            {history.length} records
          </span>
        </div>

        <div className="overflow-x-auto bg-slate-900 border border-slate-800 rounded">
          <table className="w-full text-left text-xs text-slate-300 whitespace-nowrap">
            <thead className="bg-slate-800/50 text-slate-400 font-mono">
              <tr>
                <th className="px-3 py-2 font-medium">
                  Time
                </th>

                <th className="px-3 py-2 font-medium">
                  Strategy
                </th>

                <th className="px-3 py-2 font-medium">
                  Symbol
                </th>

                <th className="px-3 py-2 font-medium">
                  Side
                </th>

                <th className="px-3 py-2 font-medium">
                  Entry
                </th>

                <th className="px-3 py-2 font-medium">
                  Current
                </th>

                <th className="px-3 py-2 font-medium">
                  PnL
                </th>

                <th className="px-3 py-2 font-medium">
                  Confidence
                </th>

                <th className="px-3 py-2 font-medium">
                  Status
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-800/50">
              {history.map((signal) => {
                const pnl =
                  signal.pnl_pct !== null
                    ? Number(signal.pnl_pct)
                    : null;

                return (
                  <tr
                    key={signal.signal_id}
                    className="hover:bg-slate-800/30"
                  >
                    <td
                      className="px-3 py-2 text-slate-500"
                      title={formatDate(
                        signal.signal_time
                      )}
                    >
                      {new Date(
                        signal.signal_time
                      ).toLocaleTimeString()}
                    </td>

                    <td className="px-3 py-2 text-indigo-400">
                      {formatStrategyName(
                        signal.strategy
                      )}
                    </td>

                    <td className="px-3 py-2 font-semibold text-slate-200">
                      {signal.symbol}
                    </td>

                    <td className="px-3 py-2 font-mono">
                      {signal.side ===
                      'BUY' ? (
                        <span className="text-emerald-400">
                          LONG
                        </span>
                      ) : (
                        <span className="text-red-400">
                          SHORT
                        </span>
                      )}
                    </td>

                    <td className="px-3 py-2 font-mono">
                      {formatPrice(
                        signal.entry_price
                      )}
                    </td>

                    <td className="px-3 py-2 font-mono">
                      {formatPrice(
                        signal.current_price
                      )}
                    </td>

                    <td
                      className={`px-3 py-2 font-mono font-semibold ${
                        pnl === null
                          ? 'text-slate-500'
                          : pnl >= 0
                            ? 'text-emerald-400'
                            : 'text-red-400'
                      }`}
                    >
                      {formatPnl(
                        signal.pnl_pct
                      )}
                    </td>

                    <td className="px-3 py-2 font-mono">
                      {signal.confidence}%
                    </td>

                    <td className="px-3 py-2">
                      <span className="text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded">
                        {signal.status}
                      </span>
                    </td>
                  </tr>
                );
              })}

              {!isHistoryLoading &&
                history.length === 0 && (
                  <tr>
                    <td
                      colSpan={9}
                      className="px-4 py-8 text-center text-slate-500"
                    >
                      No Strategy Lab signals
                      recorded yet.
                    </td>
                  </tr>
                )}

              {isHistoryLoading && (
                <tr>
                  <td
                    colSpan={9}
                    className="px-4 py-8 text-center text-slate-500"
                  >
                    Loading Strategy Lab
                    history...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <p className="mt-2 text-[10px] text-slate-500 font-mono">
          Strategy Lab signals are paper/research
          signals only and are isolated from order
          execution.
        </p>
      </div>
    </div>
  );
};