import React from 'react';
import { Crosshair, Lock, X } from 'lucide-react';
import { Position } from '../types';
import { formatCurrency, formatPercentage, getPnlColor } from '../utils/formatters';
import { StatusBadge } from './StatusBadge';

export interface PositionDetailModalProps {
  position: Position | null;
  isOpen: boolean;
  onClose: () => void;
}

export const PositionDetailModal: React.FC<PositionDetailModalProps> = ({
  position,
  isOpen,
  onClose,
}) => {
  if (!isOpen || !position) return null;

  const isProfit = position.unrealizedPnl >= 0;
  const pnlColorClass = getPnlColor(position.unrealizedPnl);

  return (
    <div
      id="modal-position-detail-backdrop"
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/75 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        id="modal-position-detail"
        className="relative w-full max-w-lg bg-slate-950 border border-slate-800 rounded-lg shadow-2xl overflow-hidden font-mono text-xs"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="px-4 py-3 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Crosshair size={16} className="text-emerald-400" />
            <span className="font-semibold text-sm text-slate-100 font-sans">
              Position Details
            </span>
            <span className="text-[10px] text-slate-500 font-mono">
              ID: {position.id}
            </span>
          </div>
          <button
            type="button"
            id="btn-close-position-modal"
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-5 space-y-4 max-h-[80vh] overflow-y-auto">
          {/* Top Banner: Symbol, Direction, PnL */}
          <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-md flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="text-base font-bold text-slate-100 font-sans">
                {position.symbol}
              </span>
              <StatusBadge type="position" value={position.side} size="xs" />
              <span className="text-[10px] text-slate-500 bg-slate-800/80 px-1.5 py-0.5 rounded">
                {position.leverage}x
              </span>
            </div>

            <div className="text-right">
              <div className={`text-sm font-bold ${pnlColorClass}`}>
                {formatCurrency(position.unrealizedPnl, { showSign: true })}
              </div>
              <div className={`text-[11px] ${isProfit ? 'text-emerald-500' : 'text-rose-500'}`}>
                {formatPercentage(position.pnlPercentage, { showSign: true })} ({position.currentR})
              </div>
            </div>
          </div>

          {/* Grid of Key Position Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            {/* Entry Price */}
            <div className="p-2.5 bg-slate-900/40 border border-slate-800/70 rounded">
              <div className="text-[10px] uppercase text-slate-500 tracking-wider">
                Entry Price
              </div>
              <div className="text-slate-200 font-semibold mt-1">
                ${position.entry.toLocaleString('en-US', {
                  minimumFractionDigits: position.symbol === 'SOLUSDT' ? 2 : 1,
                })}
              </div>
            </div>

            {/* Current Price */}
            <div className="p-2.5 bg-slate-900/40 border border-slate-800/70 rounded">
              <div className="text-[10px] uppercase text-slate-500 tracking-wider">
                Current Price
              </div>
              <div className="text-slate-100 font-semibold mt-1">
                ${position.current.toLocaleString('en-US', {
                  minimumFractionDigits: position.symbol === 'SOLUSDT' ? 2 : 1,
                })}
              </div>
            </div>

            {/* Quantity */}
            <div className="p-2.5 bg-slate-900/40 border border-slate-800/70 rounded">
              <div className="text-[10px] uppercase text-slate-500 tracking-wider">
                Quantity
              </div>
              <div className="text-slate-200 font-semibold mt-1">
                {position.quantity}{' '}
                <span className="text-slate-500 text-[10px]">
                  {position.symbol.replace('USDT', '')}
                </span>
              </div>
            </div>

            {/* Position Value */}
            <div className="p-2.5 bg-slate-900/40 border border-slate-800/70 rounded">
              <div className="text-[10px] uppercase text-slate-500 tracking-wider">
                Position Value
              </div>
              <div className="text-slate-200 font-semibold mt-1">
                {formatCurrency(position.positionValue)}
              </div>
            </div>

            {/* Stop Loss */}
            <div className="p-2.5 bg-slate-900/40 border border-slate-800/70 rounded">
              <div className="text-[10px] uppercase text-slate-500 tracking-wider">
                Stop Loss
              </div>
              <div className="text-rose-400 font-semibold mt-1">
                ${position.sl.toLocaleString()}
              </div>
            </div>

            {/* Take Profit */}
            <div className="p-2.5 bg-slate-900/40 border border-slate-800/70 rounded">
              <div className="text-[10px] uppercase text-slate-500 tracking-wider">
                Take Profit
              </div>
              <div className="text-emerald-400 font-semibold mt-1">
                ${position.tp.toLocaleString()}
              </div>
            </div>
          </div>

          {/* Risk & Execution Details */}
          <div className="p-3 bg-slate-900/30 border border-slate-800/60 rounded-md space-y-2">
            <div className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
              Risk Profile & Timing
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-800/40">
                <span className="text-slate-500">Risk Amount:</span>
                <span className="text-slate-200">{formatCurrency(position.riskAmount)}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/40">
                <span className="text-slate-500">Current R:</span>
                <span className={pnlColorClass}>
                  {position.currentR}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/40">
                <span className="text-slate-500">Opened Time:</span>
                <span className="text-slate-200">{position.openedTime}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/40">
                <span className="text-slate-500">Duration:</span>
                <span className="text-slate-200">{position.duration}</span>
              </div>
            </div>
          </div>

          {/* Safety & Action Restrictions */}
          <div className="pt-2">
            <div className="flex items-center gap-2 p-2.5 bg-slate-900/70 border border-slate-800 rounded text-[11px] text-slate-400">
              <Lock size={14} className="text-amber-400 shrink-0" />
              <span>
                Order execution disabled: Exchange actions are unavailable.
              </span>
            </div>

            <div className="mt-3 flex items-center justify-end gap-2.5">
              <button
                type="button"
                disabled
                className="px-3 py-1.5 rounded bg-slate-900 text-slate-500 border border-slate-800 cursor-not-allowed text-xs font-medium"
              >
                Modify SL / TP
              </button>
              <button
                type="button"
                disabled
                className="px-3.5 py-1.5 rounded bg-rose-950/20 text-rose-500/40 border border-rose-900/30 cursor-not-allowed text-xs font-medium flex items-center gap-1.5"
              >
                <Lock size={12} />
                <span>Close Position (Disabled)</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
