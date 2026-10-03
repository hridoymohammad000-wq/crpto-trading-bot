import React from 'react';
import { Activity } from 'lucide-react';
import { HealthCheckResponse } from '../api/types';

interface Props {
  health: HealthCheckResponse | null;
  websocketStatus: 'Connected' | 'Reconnecting' | 'Offline';
}

/**
 * Compact global status indicator for the Dashboard.
 * Shows a single-line summary of overall system health.
 */
export const GlobalStatusIndicator: React.FC<Props> = ({ health, websocketStatus }) => {
  if (!health) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-slate-800 bg-slate-900/80 px-3 py-2 text-xs font-mono text-slate-500">
        <span className="inline-block h-2 w-2 rounded-full bg-slate-600 animate-pulse" />
        Loading system status…
      </div>
    );
  }

  const allOk =
    health.backend_healthy &&
    health.db_healthy &&
    health.bybit_connected &&
    health.scanner_running &&
    websocketStatus === 'Connected';

  const criticalErrors = Object.entries(health.critical_states || {})
    .filter(([, v]) => v)
    .map(([k]) => k.replace(/_/g, ' '));

  const hasErrors = criticalErrors.length > 0;

  // Determine overall status
  let statusLabel: string;
  let dotClass: string;
  let textClass: string;
  let borderClass: string;

  if (hasErrors) {
    statusLabel = 'CRITICAL';
    dotClass = 'bg-rose-400';
    textClass = 'text-rose-400';
    borderClass = 'border-rose-900/40';
  } else if (allOk) {
    statusLabel = 'ALL SYSTEMS OPERATIONAL';
    dotClass = 'bg-emerald-400';
    textClass = 'text-emerald-400';
    borderClass = 'border-emerald-900/40';
  } else {
    statusLabel = 'DEGRADED';
    dotClass = 'bg-amber-400';
    textClass = 'text-amber-400';
    borderClass = 'border-amber-900/40';
  }

  // Build sub-statuses for the summary chips
  const chips: { label: string; ok: boolean }[] = [
    { label: 'Backend', ok: !!health.backend_healthy },
    { label: 'Bybit', ok: !!health.bybit_connected },
    { label: 'DB', ok: !!health.db_healthy },
    { label: 'Scanner', ok: !!health.scanner_running },
    { label: 'WS', ok: websocketStatus === 'Connected' },
  ];

  return (
    <div className={`rounded-md border ${borderClass} bg-slate-900/80 px-3 py-2 flex flex-wrap items-center gap-x-4 gap-y-1.5`}>
      {/* Overall indicator */}
      <div className="flex items-center gap-2">
        <Activity size={13} className={textClass} />
        <span className={`inline-block h-2 w-2 rounded-full ${dotClass}`} />
        <span className={`text-xs font-mono font-semibold ${textClass}`}>{statusLabel}</span>
      </div>

      {/* Divider */}
      <div className="hidden sm:block h-4 w-px bg-slate-800" />

      {/* Sub-status chips */}
      <div className="flex flex-wrap items-center gap-1.5">
        {chips.map((chip) => (
          <span
            key={chip.label}
            className={`rounded px-1.5 py-0.5 text-[10px] font-mono font-medium ${
              chip.ok
                ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-900/40'
                : 'bg-rose-950/40 text-rose-400 border border-rose-900/40'
            }`}
          >
            {chip.label}
          </span>
        ))}
      </div>

      {/* Error summary */}
      {hasErrors && (
        <>
          <div className="hidden sm:block h-4 w-px bg-slate-800" />
          <span className="text-[10px] font-mono text-rose-400 truncate max-w-xs" title={criticalErrors.join(', ')}>
            ⚠ {criticalErrors.join(', ')}
          </span>
        </>
      )}
    </div>
  );
};
