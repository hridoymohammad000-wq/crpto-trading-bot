import React from 'react';
import { Sparkles, BrainCircuit } from 'lucide-react';
import { PerformanceCards } from '../../components/PerformanceCards';
import { PerformanceAnalytics } from './PerformanceAnalytics';
import { StrategyMonitor } from '../strategy/StrategyMonitor';
import { PerformanceData, PerformanceMetrics } from '../../types';

interface Props {
  metrics: PerformanceMetrics;
  data: PerformanceData | null;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
  onRetry: () => Promise<void>;
  onOpenAIAnalyst?: () => void;
}

export const PerformanceStrategyPage: React.FC<Props> = ({ metrics, data, isLoading, isError, errorMessage, onRetry, onOpenAIAnalyst }) => (
  <div className="space-y-6">
    <section className="space-y-3">
      <div className="border-b border-slate-800 pb-2">
        <h2 className="text-base font-semibold font-mono text-slate-100">Performance & Strategy</h2>
        <p className="text-xs font-mono text-slate-400">Strategy state, realized results, and execution monitoring.</p>
      </div>
      <StrategyMonitor />
    </section>

    <section className="space-y-3">
      <PerformanceCards metrics={metrics} isLoading={isLoading} isError={isError} errorMessage={errorMessage} onRetry={onRetry} />
      <PerformanceAnalytics data={data} isLoading={isLoading} isError={isError} errorMessage={errorMessage} onRetry={onRetry} />
    </section>

    {onOpenAIAnalyst && (
      <section className="rounded-md border border-violet-900/50 bg-violet-950/20 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BrainCircuit size={20} className="text-violet-400" />
          <div>
            <h3 className="text-sm font-semibold text-slate-200">AI Insight</h3>
            <p className="text-xs text-slate-400 mt-0.5 max-w-[300px]">Ask the AI Analyst about your performance, blocked symbols, or scanner state.</p>
          </div>
        </div>
        <button 
          onClick={onOpenAIAnalyst}
          className="inline-flex items-center gap-2 rounded border border-violet-800 bg-violet-900/40 px-4 py-2 text-xs font-semibold text-violet-300 hover:bg-violet-900/60 transition-colors"
        >
          <Sparkles size={14} /> Open AI Analyst
        </button>
      </section>
    )}
  </div>
);
