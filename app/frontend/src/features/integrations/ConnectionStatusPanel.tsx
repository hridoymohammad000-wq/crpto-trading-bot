import React, { useCallback, useEffect, useState } from 'react';
import { Bot, BrainCircuit, Cable, MessageCircleMore, Radio, RefreshCw } from 'lucide-react';
import { getIntegrationStatus, IntegrationStatusResponse } from '../../api/integrations';
import { ConnectionStatus } from '../../types';

interface Props {
  backendStatus: ConnectionStatus;
  websocketStatus: 'Connected' | 'Reconnecting' | 'Offline';
  reconciliationStatus?: string;
}

const badge = (ok: boolean, label: string) => (
  <span className={`rounded border px-2 py-1 text-[10px] font-mono ${ok ? 'border-emerald-800/60 bg-emerald-950/40 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-400'}`}>
    {label}
  </span>
);

export const ConnectionStatusPanel: React.FC<Props> = ({ backendStatus, websocketStatus, reconciliationStatus }) => {
  const [status, setStatus] = useState<IntegrationStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setStatus(await getIntegrationStatus());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load integration status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const bybitLive = Boolean(status?.bybit.configured) && reconciliationStatus === 'SYNCED';
  const cards = [
    {
      name: 'Backend API',
      icon: Cable,
      ok: backendStatus === 'Connected',
      label: backendStatus,
      note: 'FastAPI application service',
    },
    {
      name: 'Live WebSocket',
      icon: Radio,
      ok: websocketStatus === 'Connected',
      label: websocketStatus,
      note: 'Realtime market and bot events',
    },
    {
      name: 'Bybit Demo',
      icon: Bot,
      ok: bybitLive,
      label: bybitLive ? 'SYNCED' : status?.bybit.configured ? 'Configured' : 'Not configured',
      note: status?.bybit.demo ? 'Demo trading connection' : 'Demo mode required',
    },
    {
      name: 'Telegram',
      icon: MessageCircleMore,
      ok: Boolean(status?.telegram.configured),
      label: status?.telegram.configured ? 'Configured' : 'Not configured',
      note: 'Notification integration',
    },
    {
      name: 'AI Analyst',
      icon: BrainCircuit,
      ok: Boolean(status?.ai.enabled && status?.ai.configured),
      label: status?.ai.enabled ? (status?.ai.configured ? 'Ready' : 'Key missing') : 'Disabled',
      note: status?.ai.model ? `${status.ai.provider} • ${status.ai.model}` : 'Analysis-only integration',
    },
  ];

  return (
    <section className="space-y-3 rounded-md border border-slate-800 bg-slate-900/70 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">Connections & Integrations</h3>
          <p className="mt-1 text-[11px] font-mono text-slate-500">Live connection state is kept here instead of the Dashboard header.</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading} className="rounded border border-slate-800 bg-slate-950 p-2 text-slate-400 hover:text-slate-200 disabled:opacity-50" title="Refresh connections">
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''}/>
        </button>
      </div>

      {error && <div className="rounded border border-amber-800/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">{error}</div>}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.name} className="rounded border border-slate-800 bg-slate-950/70 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Icon size={15} className={item.ok ? 'text-emerald-400' : 'text-slate-500'} />
                  <span className="text-sm font-medium text-slate-200">{item.name}</span>
                </div>
                {badge(item.ok, item.label)}
              </div>
              <p className="mt-2 text-[11px] font-mono text-slate-500">{item.note}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
};
