import ReactMarkdown from 'react-markdown';
import React, { useEffect, useState, useRef } from 'react';
import { BrainCircuit, ShieldCheck, Sparkles, X, Send, Loader2, MessageSquare } from 'lucide-react';
import { getAIStatus, requestAIAnalysis, AIStatus } from '../../api/ai';
import { fetchScannerStatus, fetchScannerCandidates, fetchScannerWatchlist } from '../../api/scanner';
import { apiClient } from '../../api/client';
import { buildEnrichedAIContext } from './contextBuilder';

interface AIAnalystDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  contextData: Record<string, unknown>;
}

export const AIAnalystDrawer: React.FC<AIAnalystDrawerProps> = ({ isOpen, onClose, contextData }) => {
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [messages, setMessages] = useState<{role: 'user' | 'ai', content: string}[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getAIStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading]);

  const runAnalysis = async (question: string) => {
    if (!question.trim()) return;
    
    setMessages(prev => [...prev, { role: 'user', content: question }]);
    setInput('');
    setLoading(true);
    
    try {
      const [scannerStatus, scannerCandidates, scannerWatchlist, botRuntime] = await Promise.all([
        fetchScannerStatus().catch(() => null),
        fetchScannerCandidates().catch(() => null),
        fetchScannerWatchlist().catch(() => null),
        apiClient.get('/bot/runtime').catch(() => null)
      ]);

      const enrichedContext = buildEnrichedAIContext(
        contextData,
        scannerStatus,
        scannerCandidates,
        scannerWatchlist,
        botRuntime
      );
      
      const result = await requestAIAnalysis(enrichedContext, question);
      setMessages(prev => [...prev, { role: 'ai', content: result.analysis }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', content: `Error: ${err instanceof Error ? err.message : 'AI analysis failed'}` }]);
    } finally {
      setLoading(false);
    }
  };

  const quickPrompts = [
    "Why no signals?",
    "Summarize scanner",
    "Best current setups",
    "Explain blocked symbols",
    "Summarize today's performance",
    "System health"
  ];

  const ready = Boolean(status?.enabled && status?.configured);

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-slate-950/50 backdrop-blur-sm z-40 transition-opacity"
          onClick={onClose}
        />
      )}
      
      {/* Drawer */}
      <div 
        className={`fixed top-0 right-0 h-full w-full sm:w-[400px] bg-slate-950 border-l border-slate-800 z-50 transform transition-transform duration-300 ease-in-out flex flex-col font-mono shadow-2xl ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-2">
            <BrainCircuit size={18} className="text-violet-400" />
            <h2 className="text-sm font-semibold text-slate-100 font-sans tracking-tight">AI Analyst</h2>
            <span className={`ml-2 rounded border px-1.5 py-0.5 text-[9px] ${ready ? 'border-emerald-800/60 bg-emerald-950/40 text-emerald-300' : 'border-slate-700 bg-slate-950 text-slate-400'}`}>
              {ready ? status?.model : 'Offline'}
            </span>
          </div>
          <button onClick={onClose} className="p-1.5 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
          <div className="rounded border border-emerald-900/50 bg-emerald-950/20 px-3 py-2 text-[10px] text-emerald-300/90 flex gap-2 items-start">
            <ShieldCheck size={14} className="shrink-0 mt-0.5" />
            <p className="leading-relaxed">READ-ONLY MODE: AI cannot place orders, approve risk, change SL/TP, bypass readiness, alter strategy settings, or start/stop the bot.</p>
          </div>

          {messages.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center gap-3 text-slate-500 opacity-80 mt-8">
              <BrainCircuit size={48} className="text-slate-700 mb-2" />
              <p className="text-xs max-w-[250px]">Ask me anything about the current trading state, scanner behavior, or system health.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-4 pb-4">
              {messages.map((msg, i) => (
                <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  <div className="flex items-center gap-1.5 mb-1.5 px-1">
                    {msg.role === 'ai' ? (
                      <><Sparkles size={10} className="text-violet-400"/><span className="text-[10px] text-violet-400 font-semibold tracking-wider">AI ANALYST</span></>
                    ) : (
                      <><span className="text-[10px] text-slate-500 tracking-wider">USER</span></>
                    )}
                  </div>
                  <div className={`text-[12px] px-3 py-2 rounded-md max-w-[95%] leading-relaxed ${
                    msg.role === 'user' 
                      ? 'bg-slate-800/80 text-slate-200 border border-slate-700' 
                      : 'bg-violet-950/20 text-slate-300 border border-violet-900/30 whitespace-pre-wrap'
                  }`}>
                    {msg.role === 'ai' ? <ReactMarkdown>{msg.content}</ReactMarkdown> : msg.content}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex items-start">
                  <div className="text-[12px] px-3 py-2 rounded-md bg-violet-950/20 text-violet-300 border border-violet-900/30 flex items-center gap-2">
                    <Loader2 size={12} className="animate-spin" /> Analyzing...
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="p-3 bg-slate-900/50 border-t border-slate-800">
          <div className="flex flex-wrap gap-1.5 mb-3">
            {quickPrompts.map(prompt => (
              <button 
                key={prompt}
                onClick={() => runAnalysis(prompt)}
                disabled={loading || !ready}
                className="px-2 py-1 bg-slate-800/50 hover:bg-slate-700 border border-slate-700 rounded text-[10px] text-slate-300 transition-colors disabled:opacity-40"
              >
                {prompt}
              </button>
            ))}
          </div>
          <form 
            onSubmit={(e) => { e.preventDefault(); runAnalysis(input); }}
            className="flex gap-2 relative"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={ready ? "Ask about strategy, scanner..." : "AI Offline"}
              disabled={!ready || loading}
              className="flex-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-violet-500 transition-colors disabled:opacity-50"
            />
            <button 
              type="submit"
              disabled={!input.trim() || !ready || loading}
              className="bg-violet-600 hover:bg-violet-500 text-white p-2 rounded flex items-center justify-center transition-colors disabled:opacity-50 disabled:hover:bg-violet-600 shrink-0"
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      </div>
    </>
  );
};



