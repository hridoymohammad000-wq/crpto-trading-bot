import React from 'react';
import { CheckCircle2, Clock, Loader2, Menu, Power, Settings, ShieldAlert, X } from 'lucide-react';
import { AccountSummary, BotStatus } from '../types';
import { formatCurrency, formatPercentage } from '../utils/formatters';
import { StatusBadge } from './StatusBadge';

export interface HeaderProps {
  accountInfo: AccountSummary;
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  onOpenSettings?: () => void;
  onOpenAIAnalyst?: () => void;
  botStatus?: BotStatus;
  isStatusLoading?: boolean;
  isActionLoading?: boolean;
  onToggleBot?: () => void;
  errorMessage?: string | null;
  successMessage?: string | null;
  onClearMessage?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  accountInfo,
  isSidebarOpen,
  onToggleSidebar,
  onOpenSettings,
  onOpenAIAnalyst,
  botStatus = accountInfo.botStatus,
  isStatusLoading = false,
  isActionLoading = false,
  onToggleBot,
  errorMessage,
  successMessage,
  onClearMessage,
}) => (
  <header id="app-header" className="sticky top-0 z-30 w-full shrink-0 bg-slate-950/95 border-b border-slate-800 backdrop-blur-sm">
    <div className="px-3 sm:px-4 py-2.5 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2.5 sm:gap-3.5 shrink-0">
        <button id="btn-toggle-sidebar" type="button" onClick={onToggleSidebar} aria-label="Toggle navigation menu" className="p-1.5 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800/70 md:hidden transition-colors">
          {isSidebarOpen ? <X size={18}/> : <Menu size={18}/>} 
        </button>
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-mono font-black text-sm">▲</div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm sm:text-base tracking-tight text-slate-100">Crypto Intraday Bot</span>
              <StatusBadge type="env" value={accountInfo.environment} size="xs" />
            </div>
            <div className="hidden sm:block text-[10px] text-slate-500 font-mono">BYBIT DEMO • DETERMINISTIC EXECUTION</div>
          </div>
        </div>
      </div>

      <div id="header-metrics-strip" className="hidden lg:flex items-center gap-4 px-3 py-1 bg-slate-900/80 border border-slate-800 rounded-md text-xs font-mono">
        <div className="flex items-center gap-1.5"><span className="text-slate-500 uppercase text-[10px]">Balance</span><span className="text-slate-200 font-semibold">{formatCurrency(accountInfo.balance)}</span></div>
        <div className="h-3 w-px bg-slate-800"/>
        <div className="flex items-center gap-1.5"><span className="text-slate-500 uppercase text-[10px]">Equity</span><span className="text-slate-100 font-bold">{formatCurrency(accountInfo.equity)}</span></div>
        <div className="h-3 w-px bg-slate-800"/>
        <div className="flex items-center gap-1.5"><span className="text-slate-500 uppercase text-[10px]">Available</span><span className="text-slate-300 font-medium">{formatCurrency(accountInfo.availableBalance)}</span></div>
        <div className="h-3 w-px bg-slate-800"/>
        <div className="flex items-center gap-1.5"><span className="text-slate-500 uppercase text-[10px]">Daily PnL</span><span className={accountInfo.dailyPnl != null && accountInfo.dailyPnl < 0 ? 'text-rose-400 font-semibold' : 'text-emerald-400 font-semibold'}>{formatCurrency(accountInfo.dailyPnl, { showSign: true })}<span className="ml-1 text-[10px] opacity-80">({formatPercentage(accountInfo.dailyPnlPercentage, { showSign: true })})</span></span></div>
        <div className="h-3 w-px bg-slate-800"/>
        <div className="flex items-center gap-1 text-[11px] text-slate-500"><Clock size={11}/><span>{accountInfo.lastUpdated}</span></div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <button id="btn-bot-toggle-control" type="button" onClick={onToggleBot} disabled={isActionLoading || isStatusLoading} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded font-mono text-xs font-medium border transition ${botStatus === 'RUNNING' ? 'bg-emerald-950/40 text-emerald-300 border-emerald-700/60' : 'bg-amber-950/40 text-amber-300 border-amber-700/60'} disabled:opacity-50`}>
          {isActionLoading || isStatusLoading ? <Loader2 size={12} className="animate-spin"/> : <Power size={12}/>}<span>{isActionLoading ? 'WORKING…' : botStatus}</span>
        </button>
        {onOpenAIAnalyst && (
          <button type="button" onClick={onOpenAIAnalyst} className="p-1.5 rounded text-violet-400 hover:text-violet-200 hover:bg-violet-900/30 border border-transparent hover:border-violet-800/50 transition-colors flex items-center gap-1" title="Open AI Analyst">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/><path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4 4.5 4.5 0 0 1 3 4 4.5 4.5 0 0 1 3-4Z"/></svg>
          </button>
        )}
        <button id="btn-header-settings" type="button" onClick={onOpenSettings} aria-label="Open settings" className="p-1.5 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent hover:border-slate-800 transition-colors"><Settings size={16}/></button>
      </div>
    </div>

    <div className="flex lg:hidden items-center justify-around px-3 py-1.5 bg-slate-900/60 border-t border-slate-800/80 text-[11px] font-mono">
      <span className="text-slate-400">Bal <strong className="text-slate-200">{formatCurrency(accountInfo.balance)}</strong></span>
      <span className="text-slate-400">Eq <strong className="text-slate-100">{formatCurrency(accountInfo.equity)}</strong></span>
      <span className="text-slate-400">Avail <strong className="text-slate-300">{formatCurrency(accountInfo.availableBalance)}</strong></span>
    </div>

    {errorMessage && <div className="bg-rose-950/90 border-b border-rose-800/70 px-4 py-2 text-xs text-rose-200 flex items-center justify-between font-mono"><div className="flex items-center gap-2"><ShieldAlert size={15}/><span>{errorMessage}</span></div>{onClearMessage && <button onClick={onClearMessage}><X size={14}/></button>}</div>}
    {successMessage && <div className="bg-emerald-950/90 border-b border-emerald-800/70 px-4 py-2 text-xs text-emerald-200 flex items-center justify-between font-mono"><div className="flex items-center gap-2"><CheckCircle2 size={15}/><span>{successMessage}</span></div>{onClearMessage && <button onClick={onClearMessage}><X size={14}/></button>}</div>}
  </header>
);
