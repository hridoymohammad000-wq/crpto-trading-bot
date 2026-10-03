import React from 'react';
import {
  Activity,
  Database,
  Cpu,
  Radio,
  Server,
  Shield,
  Timer,
  TrendingUp,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import { HealthCheckResponse, AccountSummary } from '../../api/types';
import { formatCurrency } from '../../utils/formatters';

/* ────────────────────────────────────────────────────────
   Props
   ──────────────────────────────────────────────────────── */
interface Props {
  health: HealthCheckResponse | null;
  account: AccountSummary;
  websocketStatus: 'Connected' | 'Reconnecting' | 'Offline';
}

/* ────────────────────────────────────────────────────────
   Shared tiny helpers
   ──────────────────────────────────────────────────────── */
type StatusColor = 'green' | 'red' | 'neutral';

const dotColor: Record<StatusColor, string> = {
  green: 'bg-emerald-400',
  red: 'bg-rose-400',
  neutral: 'bg-slate-500',
};

const textColor: Record<StatusColor, string> = {
  green: 'text-emerald-400',
  red: 'text-rose-400',
  neutral: 'text-slate-400',
};

const borderColor: Record<StatusColor, string> = {
  green: 'border-emerald-900/40',
  red: 'border-rose-900/40',
  neutral: 'border-slate-800',
};

const StatusDot: React.FC<{ color: StatusColor }> = ({ color }) => (
  <span className={`inline-block h-2 w-2 rounded-full ${dotColor[color]}`} />
);

const formatDuration = (seconds?: number | null) => {
  if (seconds == null || seconds <= 0) return 'N/A';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h}h ${m}m ${s}s`;
};

const formatTime = (iso?: string | null) => {
  if (!iso) return 'N/A';
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return 'N/A';
  }
};

/* ────────────────────────────────────────────────────────
   Compact status card
   ──────────────────────────────────────────────────────── */
interface StatusCardProps {
  icon: React.ElementType;
  title: string;
  status: string;
  color: StatusColor;
  detail?: string;
}

const StatusCard: React.FC<StatusCardProps> = ({ icon: Icon, title, status, color, detail }) => (
  <div className={`rounded-lg border ${borderColor[color]} bg-slate-950/70 p-3 flex items-start gap-3`}>
    <div className={`mt-0.5 rounded-md p-1.5 ${color === 'green' ? 'bg-emerald-950/60' : color === 'red' ? 'bg-rose-950/60' : 'bg-slate-900'}`}>
      <Icon size={14} className={textColor[color]} />
    </div>
    <div className="min-w-0 flex-1">
      <p className="text-xs font-medium text-slate-300 truncate">{title}</p>
      <div className="mt-1 flex items-center gap-1.5">
        <StatusDot color={color} />
        <span className={`text-[11px] font-mono font-semibold ${textColor[color]}`}>{status}</span>
      </div>
      {detail && <p className="mt-1 text-[10px] font-mono text-slate-500 truncate" title={detail}>{detail}</p>}
    </div>
  </div>
);

/* ────────────────────────────────────────────────────────
   Runtime Diagnostics card (wider)
   ──────────────────────────────────────────────────────── */
interface DiagnosticRowProps {
  label: string;
  value: string;
  color?: StatusColor;
}

const DiagnosticRow: React.FC<DiagnosticRowProps> = ({ label, value, color = 'neutral' }) => (
  <div className="flex items-center justify-between py-1.5 border-b border-slate-800/60 last:border-b-0">
    <span className="text-[11px] font-mono text-slate-500">{label}</span>
    <span className={`text-[11px] font-mono font-medium ${textColor[color]}`}>{value}</span>
  </div>
);

/* ────────────────────────────────────────────────────────
   Main component
   ──────────────────────────────────────────────────────── */
export const SystemHealthDiagnostics: React.FC<Props> = ({ health, account, websocketStatus }) => {
  if (!health) {
    return (
      <section className="space-y-3 rounded-md border border-slate-800 bg-slate-900/70 p-4">
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300">
          <Activity size={14} className="text-emerald-400" />
          System Health &amp; Diagnostics
        </h3>
        <div className="flex items-center gap-2 rounded border border-slate-800 bg-slate-950/70 p-4 text-xs font-mono text-slate-500">
          <RefreshCw size={12} className="animate-spin" />
          Loading health data…
        </div>
      </section>
    );
  }

  const criticalErrors = Object.entries(health.critical_states || {})
    .filter(([, v]) => v)
    .map(([k]) => k.replace(/_/g, ' '));
  const criticalText = criticalErrors.length > 0 ? criticalErrors.join(', ') : 'None';

  const backendColor: StatusColor = health.backend_healthy ? 'green' : 'red';
  const dbColor: StatusColor = health.db_healthy ? 'green' : 'red';
  const bybitColor: StatusColor = health.bybit_connected ? 'green' : 'red';
  const scannerColor: StatusColor = health.scanner_running ? 'green' : 'neutral';
  const managerColor: StatusColor = health.position_manager_running ? 'green' : 'neutral';
  const wsColor: StatusColor = websocketStatus === 'Connected' ? 'green' : websocketStatus === 'Reconnecting' ? 'neutral' : 'red';
  const botStatusText = (health.bot_status ?? health.status ?? 'unknown').toUpperCase();
  const botColor: StatusColor = ['RUNNING', 'HEALTHY'].includes(botStatusText) ? 'green' : botStatusText === 'UNHEALTHY' ? 'red' : 'neutral';

  return (
    <section className="space-y-4 rounded-md border border-slate-800 bg-slate-900/70 p-4">
      {/* Section header */}
      <div>
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300">
          <Activity size={14} className="text-emerald-400" />
          System Health &amp; Diagnostics
        </h3>
        <p className="mt-1 text-[11px] font-mono text-slate-500">
          Live system health pulled from the backend <code>/health</code> endpoint
        </p>
      </div>

      {/* Compact status cards grid */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatusCard icon={Server} title="Backend" status={health.backend_healthy ? 'HEALTHY' : 'UNHEALTHY'} color={backendColor} />
        <StatusCard icon={TrendingUp} title="Bybit API" status={health.bybit_connected ? 'CONNECTED' : 'DISCONNECTED'} color={bybitColor} />
        <StatusCard icon={Database} title="Database" status={health.db_healthy ? 'HEALTHY' : 'UNHEALTHY'} color={dbColor} />
        <StatusCard icon={Cpu} title="Scanner" status={health.scanner_running ? 'RUNNING' : 'STOPPED'} color={scannerColor} />
        <StatusCard icon={Shield} title="Position Mgr" status={health.position_manager_running ? 'ACTIVE' : 'INACTIVE'} color={managerColor} />
        <StatusCard icon={Radio} title="WebSocket" status={websocketStatus.toUpperCase()} color={wsColor} />
      </div>

      {/* Runtime Diagnostics & Account cards row */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {/* Runtime diagnostics */}
        <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4 space-y-1">
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Runtime Diagnostics</h4>
          <DiagnosticRow label="Bot Status" value={botStatusText} color={botColor} />
          <DiagnosticRow label="Uptime" value={formatDuration(health.uptime_seconds)} color="green" />
          <DiagnosticRow label="Last Scan" value={formatTime(health.last_scan_at)} />
          <DiagnosticRow label="Open Positions" value={String(health.open_positions ?? 0)} />
          <DiagnosticRow label="Errors 24h" value={criticalText} color={criticalErrors.length > 0 ? 'red' : 'green'} />
          {health.watchdog_running != null && (
            <DiagnosticRow label="Watchdog" value={health.watchdog_running ? 'ACTIVE' : 'INACTIVE'} color={health.watchdog_running ? 'green' : 'neutral'} />
          )}
          {health.watchdog_active_incidents && health.watchdog_active_incidents.length > 0 && (
            <DiagnosticRow label="Active Incidents" value={health.watchdog_active_incidents.join(', ')} color="red" />
          )}
        </div>

        {/* Account summary */}
        <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4 space-y-1">
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Account Summary</h4>
          <DiagnosticRow label="Balance" value={formatCurrency(account.balance)} color="green" />
          <DiagnosticRow label="Equity" value={formatCurrency(account.equity)} color="green" />
          <DiagnosticRow label="Available" value={formatCurrency(account.availableBalance)} />
          <DiagnosticRow label="Used Margin" value={formatCurrency(account.margin_used)} />
        </div>
      </div>

      {/* Critical alerts banner */}
      {criticalErrors.length > 0 && (
        <div className="flex items-start gap-2 rounded border border-rose-800/50 bg-rose-950/30 px-3 py-2 text-xs font-mono text-rose-300">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-rose-400" />
          <div>
            <span className="font-semibold">Critical:</span> {criticalText}
          </div>
        </div>
      )}
    </section>
  );
};
