import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  BrainCircuit,
  Loader2,
  Send,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';

import {
  AIAnalysisResponse,
  AIStatus,
  getAIStatus,
  requestAIAnalysis,
} from '../../api/ai';
import {
  fetchScannerCandidates,
  fetchScannerStatus,
  fetchScannerWatchlist,
} from '../../api/scanner';
import { apiClient } from '../../api/client';
import { buildEnrichedAIContext } from './contextBuilder';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  contextData: Record<string, unknown>;
}

interface HistoryItem extends AIAnalysisResponse {
  id: string;
  question: string;
  analyzedAt: string;
  contextSnapshot: Record<string, unknown>;
}

export const AIAnalystDrawer: React.FC<Props> = ({
  isOpen,
  onClose,
  contextData,
}) => {
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [latest, setLatest] = useState<HistoryItem | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getAIStatus()
      .then((value) => {
        setStatus(value);
        setStatusError(null);
      })
      .catch((err) => {
        setStatus(null);
        setStatusError(
          err instanceof Error ? err.message : 'Unable to load AI status'
        );
      });
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, loading]);

  const ready = Boolean(status?.enabled && status?.configured);

  const runAnalysis = async (question: string) => {
    if (!question.trim() || !ready || loading) return;

    setLoading(true);
    setRuntimeError(null);
    setInput('');

    try {
      const [
        scannerStatus,
        scannerCandidates,
        scannerWatchlist,
        botRuntime,
      ] = await Promise.all([
        fetchScannerStatus().catch(() => null),
        fetchScannerCandidates().catch(() => null),
        fetchScannerWatchlist().catch(() => null),
        apiClient.get('/bot/runtime').catch(() => null),
      ]);

      const enriched = buildEnrichedAIContext(
        contextData,
        scannerStatus,
        scannerCandidates,
        scannerWatchlist,
        botRuntime
      );

      const result = await requestAIAnalysis(
        enriched,
        question
      );

      const item: HistoryItem = {
        ...result,
        id: `${Date.now()}`,
        question,
        analyzedAt: new Date().toISOString(),
        contextSnapshot: enriched,
      };

      setLatest(item);
      setHistory((prev) => [item, ...prev].slice(0, 20));
    } catch (err) {
      setRuntimeError(
        err instanceof Error
          ? err.message
          : 'AI analysis failed'
      );
    } finally {
      setLoading(false);
    }
  };

  const actionClass =
    latest?.action === 'ALLOW'
      ? 'text-emerald-300 border-emerald-800 bg-emerald-950/40'
      : latest?.action === 'BLOCK'
      ? 'text-rose-300 border-rose-800 bg-rose-950/40'
      : latest?.action === 'CAUTION'
      ? 'text-amber-300 border-amber-800 bg-amber-950/40'
      : 'text-slate-400 border-slate-700 bg-slate-900';

  const quickPrompts = [
    'Why no signals?',
    'Summarize scanner',
    'Best current setups',
    'Explain blocked symbols',
    "Summarize today's performance",
    'System health',
  ];

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-950/50 backdrop-blur-sm"
          onClick={onClose}
        />
      )}

      <div
        className={`fixed right-0 top-0 z-50 flex h-full w-full flex-col border-l border-slate-800 bg-slate-950 font-mono shadow-2xl transition-transform duration-300 sm:w-[460px] ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center gap-2">
            <BrainCircuit size={18} className="text-violet-400" />
            <div>
              <div className="text-sm font-semibold text-slate-100">
                AI Analyst
              </div>
              <div className="text-[10px] text-slate-500">
                READ-ONLY ADVISORY
              </div>
            </div>

            <span
              className={`ml-2 rounded border px-1.5 py-0.5 text-[9px] ${
                ready
                  ? 'border-emerald-800 bg-emerald-950/40 text-emerald-300'
                  : 'border-rose-800 bg-rose-950/40 text-rose-300'
              }`}
            >
              {ready ? 'ACTIVE' : 'OFFLINE'}
            </span>
          </div>

          <button
            onClick={onClose}
            className="rounded p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-100"
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="rounded border border-slate-800 bg-slate-900/60 p-2">
              <div className="text-slate-500">Provider</div>
              <div className="mt-1 text-slate-200">
                {status?.provider || 'Unavailable'}
              </div>
            </div>

            <div className="rounded border border-slate-800 bg-slate-900/60 p-2">
              <div className="text-slate-500">Model</div>
              <div className="mt-1 truncate text-slate-200">
                {status?.model || 'Unavailable'}
              </div>
            </div>

            <div className="rounded border border-slate-800 bg-slate-900/60 p-2">
              <div className="text-slate-500">Configured</div>
              <div className="mt-1 text-slate-200">
                {status?.configured ? 'YES' : 'NO'}
              </div>
            </div>

            <div className="rounded border border-slate-800 bg-slate-900/60 p-2">
              <div className="text-slate-500">Mode</div>
              <div className="mt-1 text-emerald-300">
                ANALYSIS ONLY
              </div>
            </div>
          </div>

          <div className="flex gap-2 rounded border border-emerald-900/50 bg-emerald-950/20 px-3 py-2 text-[10px] text-emerald-300">
            <ShieldCheck size={14} className="mt-0.5 shrink-0" />
            <span>
              AI cannot place orders, approve risk, change SL/TP,
              bypass readiness, or start/stop the bot.
            </span>
          </div>

          {(statusError || runtimeError) && (
            <div className="rounded border border-rose-800/60 bg-rose-950/30 px-3 py-2 text-[10px] text-rose-300">
              {statusError || runtimeError}
            </div>
          )}

          {latest && (
            <section className="space-y-3 rounded border border-violet-900/50 bg-violet-950/10 p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-[10px] font-semibold text-violet-300">
                  <Sparkles size={11} />
                  LATEST AI ANALYSIS
                </div>

                <span
                  className={`rounded border px-2 py-0.5 text-[10px] font-bold ${actionClass}`}
                >
                  {latest.action || 'UNAVAILABLE'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div>
                  <span className="text-slate-500">Symbol:</span>{' '}
                  <span className="text-slate-200">
                    {latest.symbol || 'Unavailable'}
                  </span>
                </div>

                <div>
                  <span className="text-slate-500">Confidence:</span>{' '}
                  <span className="text-slate-200">
                    {latest.confidence == null
                      ? 'Unavailable'
                      : `${latest.confidence}%`}
                  </span>
                </div>

                <div>
                  <span className="text-slate-500">Regime:</span>{' '}
                  <span className="text-slate-200">
                    {latest.market_regime || 'Unavailable'}
                  </span>
                </div>

                <div>
                  <span className="text-slate-500">Time:</span>{' '}
                  <span className="text-slate-200">
                    {new Date(latest.analyzedAt).toLocaleTimeString()}
                  </span>
                </div>
              </div>

              <div className="rounded border border-slate-800 bg-slate-950/60 p-2 text-[11px] leading-relaxed text-slate-300">
                <ReactMarkdown>{latest.analysis}</ReactMarkdown>
              </div>

              <details className="rounded border border-slate-800 bg-slate-950/50 p-2">
                <summary className="cursor-pointer text-[10px] text-cyan-300">
                  FACTUAL CONTEXT SENT TO AI
                </summary>

                <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all text-[9px] text-slate-500">
                  {JSON.stringify(latest.contextSnapshot, null, 2)}
                </pre>
              </details>
            </section>
          )}

          <section className="space-y-2">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Analysis History
            </div>

            {history.length === 0 ? (
              <div className="rounded border border-slate-800 bg-slate-900/40 p-4 text-center text-[11px] text-slate-600">
                No AI analysis has been run in this session.
              </div>
            ) : (
              history.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setLatest(item)}
                  className="w-full rounded border border-slate-800 bg-slate-900/50 p-2 text-left hover:border-slate-700"
                >
                  <div className="flex justify-between gap-2 text-[10px]">
                    <span className="truncate text-slate-300">
                      {item.question}
                    </span>
                    <span className="shrink-0 text-slate-600">
                      {new Date(item.analyzedAt).toLocaleTimeString()}
                    </span>
                  </div>

                  <div className="mt-1 flex gap-2 text-[9px] text-slate-500">
                    <span>{item.symbol || 'No symbol'}</span>
                    <span>•</span>
                    <span>{item.action || 'No action'}</span>
                    <span>•</span>
                    <span>
                      {item.confidence == null
                        ? 'No confidence'
                        : `${item.confidence}%`}
                    </span>
                  </div>
                </button>
              ))
            )}
          </section>

          {loading && (
            <div className="flex items-center gap-2 text-xs text-violet-300">
              <Loader2 size={12} className="animate-spin" />
              AI analyzing current factual snapshot...
            </div>
          )}

          <div ref={endRef} />
        </div>

        <div className="border-t border-slate-800 bg-slate-900/50 p-3">
          <div className="mb-3 flex flex-wrap gap-1.5">
            {quickPrompts.map((prompt) => (
              <button
                key={prompt}
                onClick={() => runAnalysis(prompt)}
                disabled={!ready || loading}
                className="rounded border border-slate-700 bg-slate-800/50 px-2 py-1 text-[10px] text-slate-300 hover:bg-slate-700 disabled:opacity-40"
              >
                {prompt}
              </button>
            ))}
          </div>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              runAnalysis(input);
            }}
            className="flex gap-2"
          >
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={
                ready
                  ? 'Ask AI about current bot state...'
                  : 'AI unavailable'
              }
              disabled={!ready || loading}
              className="flex-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-violet-500 focus:outline-none disabled:opacity-50"
            />

            <button
              type="submit"
              disabled={!input.trim() || !ready || loading}
              className="rounded bg-violet-600 p-2 text-white hover:bg-violet-500 disabled:opacity-40"
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      </div>
    </>
  );
};
