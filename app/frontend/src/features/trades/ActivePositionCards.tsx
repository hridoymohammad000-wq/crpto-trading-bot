import React from 'react';
import { Activity, Clock3, Crosshair, Target } from 'lucide-react';
import { Position } from '../../types';
import { formatCurrency, formatPercentage } from '../../utils/formatters';

interface Props {
  positions: Position[];
  onSelectPosition?: (position: Position) => void;
  isLiveUpdates?: boolean;
}

export const ActivePositionCards: React.FC<Props> = ({ positions, onSelectPosition, isLiveUpdates = false }) => {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold font-mono text-slate-100">
            <Activity size={15} className="text-emerald-400" />
            Active Trades
          </h2>
          <p className="mt-0.5 text-[11px] font-mono text-slate-500">
            All currently open positions are always shown for safety.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isLiveUpdates && (
            <span className="rounded border border-emerald-800/60 bg-emerald-950/40 px-2 py-1 text-[10px] font-mono text-emerald-300">
              WS LIVE
            </span>
          )}
          <span className="rounded border border-slate-800 bg-slate-900 px-2 py-1 text-[10px] font-mono text-slate-400">
            {positions.length} active
          </span>
        </div>
      </div>

      {positions.length === 0 ? (
        <div className="rounded-md border border-slate-800 bg-slate-900/70 p-6 text-center font-mono">
          <Crosshair size={22} className="mx-auto mb-2 text-slate-600" />
          <div className="text-sm text-slate-300">No active trades</div>
          <div className="mt-1 text-xs text-slate-500">The bot currently has no open positions.</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          {positions.map((position) => {
            const pnlPositive = position.unrealizedPnl >= 0;
            return (
              <button
                key={position.id}
                type="button"
                onClick={() => onSelectPosition?.(position)}
                className="rounded-md border border-slate-800 bg-slate-900/80 p-4 text-left transition hover:border-slate-700 hover:bg-slate-900"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-base font-bold text-slate-100">{position.symbol}</span>
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${position.side === 'LONG' ? 'bg-emerald-950/70 text-emerald-300' : 'bg-rose-950/70 text-rose-300'}`}>
                        {position.side}
                      </span>
                    </div>
                    <div className="mt-1 text-[11px] font-mono text-slate-500">Leverage {position.leverage}x • Qty {position.quantity}</div>
                  </div>
                  <div className={`text-right font-mono ${pnlPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                    <div className="text-base font-bold">{formatCurrency(position.unrealizedPnl, { showSign: true })}</div>
                    <div className="text-[11px]">{formatPercentage(position.pnlPercentage, { showSign: true })}</div>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3 text-xs font-mono">
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500">Entry</div>
                    <div className="mt-1 text-slate-200">${position.entry.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500">Current</div>
                    <div className="mt-1 text-slate-200">${position.current.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500"><Crosshair size={10}/>SL</div>
                    <div className="mt-1 text-rose-300">${position.sl.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500"><Target size={10}/>TP</div>
                    <div className="mt-1 text-emerald-300">${position.tp.toLocaleString()}</div>
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-slate-800 pt-3 text-[11px] font-mono text-slate-500">
                  <span className="flex items-center gap-1"><Clock3 size={11}/>{position.duration || position.openedTime}</span>
                  <span>{position.currentR}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
};
