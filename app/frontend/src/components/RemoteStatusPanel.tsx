import React from 'react';
import { HealthCheckResponse, AccountSummary } from '../api/types';
import { formatCurrency } from '../utils/formatters';

interface Props {
  health: HealthCheckResponse | null;
  account: AccountSummary;
}

export const RemoteStatusPanel: React.FC<Props> = ({ health, account }) => {
  if (!health) return null;

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m ${s}s`;
  };

  const criticalErrors = Object.entries(health.critical_states || {})
    .filter(([_, v]) => v)
    .map(([k]) => k)
    .join(', ') || 'None';

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-md p-4 space-y-4">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">System Health Panel</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
        <div className="space-y-1">
          <p className="text-slate-500">Bot Status</p>
          <p className={health.bot_status === 'running' ? 'text-emerald-400' : 'text-slate-300'}>{health.bot_status.toUpperCase()}</p>
        </div>
        <div className="space-y-1">
          <p className="text-slate-500">Uptime</p>
          <p className="text-slate-300">{formatDuration(health.uptime_seconds)}</p>
        </div>
        <div className="space-y-1">
          <p className="text-slate-500">Backend</p>
          <p className={health.backend_healthy ? 'text-emerald-400' : 'text-rose-400'}>{health.backend_healthy ? 'HEALTHY' : 'UNHEALTHY'}</p>
        </div>
        <div className="space-y-1">
          <p className="text-slate-500">Bybit DB</p>
          <p className={health.db_healthy ? 'text-emerald-400' : 'text-rose-400'}>{health.db_healthy ? 'HEALTHY' : 'UNHEALTHY'}</p>
        </div>
        
        <div className="space-y-1">
          <p className="text-slate-500">Scanner</p>
          <p className={health.scanner_running ? 'text-emerald-400' : 'text-slate-300'}>{health.scanner_running ? 'RUNNING' : 'STOPPED'}</p>
        </div>
        <div className="space-y-1">
          <p className="text-slate-500">Last Scan</p>
          <p className="text-slate-300 truncate" title={health.last_scan_at || 'N/A'}>{health.last_scan_at ? new Date(health.last_scan_at).toLocaleTimeString() : 'N/A'}</p>
        </div>
        <div className="space-y-1">
          <p className="text-slate-500">BE Manager</p>
          <p className={health.position_manager_running ? 'text-emerald-400' : 'text-slate-300'}>{health.position_manager_running ? 'ACTIVE' : 'INACTIVE'}</p>
        </div>
        <div className="space-y-1">
          <p className="text-slate-500">Open Positions</p>
          <p className="text-slate-300">{health.open_positions}</p>
        </div>
        <div className="space-y-1">
          <p className="text-slate-500">Errors 24h</p>
          <p className={criticalErrors !== 'None' ? 'text-rose-400' : 'text-emerald-400'}>{criticalErrors}</p>
        </div>

        <div className="col-span-2 md:col-span-4 border-t border-slate-800 my-2"></div>

        <div className="space-y-1">
          <p className="text-slate-500">Balance</p>
          <p className="text-slate-200">{formatCurrency(account.balance)}</p>
        </div>
        <div className="space-y-1">
          <p className="text-slate-500">Equity</p>
          <p className="text-slate-200">{formatCurrency(account.equity)}</p>
        </div>
        <div className="space-y-1">
          <p className="text-slate-500">Available</p>
          <p className="text-slate-200">{formatCurrency(account.availableBalance)}</p>
        </div>
        <div className="space-y-1">
          <p className="text-slate-500">Used Margin</p>
          <p className="text-slate-200">{formatCurrency(account.margin_used)}</p>
        </div>
      </div>
    </div>
  );
};
