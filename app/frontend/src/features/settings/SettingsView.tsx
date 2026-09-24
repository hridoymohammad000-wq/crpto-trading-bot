import React from 'react';
import { Check, RotateCcw, Save, Shield, Sliders } from 'lucide-react';
import { useBotSettings } from '../../hooks';
import { StrategyKey, Timeframe, TradingSymbol } from '../../types';
import { ConnectionStatusPanel } from '../integrations/ConnectionStatusPanel';
import { ConnectionStatus } from '../../types';

export interface SettingsViewProps {
  className?: string;
  backendStatus: ConnectionStatus;
  websocketStatus: 'Connected' | 'Reconnecting' | 'Offline';
  reconciliationStatus?: string;
}

const STRATEGIES: { key: StrategyKey; label: string; description: string }[] = [
  { key: 'emaRsi', label: 'EMA + RSI', description: 'EMA pullback with RSI confirmation' },
  { key: 'bollingerSqueeze', label: 'Bollinger Squeeze', description: 'Volatility squeeze setup' },
];
const SYMBOLS: TradingSymbol[] = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m'];

const fieldClass =
  'w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30 disabled:cursor-not-allowed disabled:opacity-60';

interface ToggleProps {
  checked: boolean;
  label: string;
  description?: string;
  onChange: () => void;
}

const Toggle: React.FC<ToggleProps> = ({ checked, label, description, onChange }) => (
  <label className="flex cursor-pointer items-center justify-between gap-4 rounded border border-slate-800 bg-slate-950/80 p-3">
    <span>
      <span className="block text-sm font-semibold text-slate-200">{label}</span>
      {description && <span className="mt-0.5 block text-[11px] text-slate-500">{description}</span>}
    </span>
    <input type="checkbox" checked={checked} onChange={onChange} className="sr-only" />
    <span
      aria-hidden="true"
      className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${checked ? 'bg-emerald-500' : 'bg-slate-700'}`}
    >
      <span
        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${checked ? 'translate-x-4.5' : 'translate-x-0.5'}`}
      />
    </span>
  </label>
);

interface ChoiceGroupProps<T extends string> {
  legend: string;
  values: readonly T[];
  selected: readonly T[];
  error?: string;
  onToggle: (value: T) => void;
}

function ChoiceGroup<T extends string>({ legend, values, selected, error, onToggle }: ChoiceGroupProps<T>) {
  return (
    <fieldset>
      <legend className="mb-2 text-xs font-medium text-slate-400">{legend}</legend>
      <div className="grid grid-cols-3 gap-2">
        {values.map((value) => {
          const isSelected = selected.includes(value);
          return (
            <label
              key={value}
              className={`cursor-pointer rounded border px-2 py-2 text-center text-xs transition ${
                isSelected
                  ? 'border-emerald-700 bg-emerald-950/50 text-emerald-300'
                  : 'border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700'
              }`}
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={isSelected}
                onChange={() => onToggle(value)}
              />
              {value}
            </label>
          );
        })}
      </div>
      {error && <p className="mt-1.5 text-[11px] text-rose-400">{error}</p>}
    </fieldset>
  );
}

export const SettingsView: React.FC<SettingsViewProps> = ({ className = '', backendStatus, websocketStatus, reconciliationStatus }) => {
  const {
    settings,
    errors,
    isValid,
    isSaving,
    hasUnsavedChanges,
    saveMessage,
    saveError,
    update,
    toggleStrategy,
    toggleSymbol,
    toggleTimeframe,
    save,
    reset,
  } = useBotSettings();

  return (
    <div id="view-settings" className={`mx-auto max-w-5xl space-y-4 ${className}`}>
      <div className="flex flex-col gap-3 border-b border-slate-800 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="flex items-center gap-2 font-mono text-base font-semibold tracking-tight text-slate-100">
            <Sliders size={16} className="text-emerald-400" />
            Bot Settings
          </h2>
          <p className="mt-0.5 font-mono text-xs text-slate-400">
            Saved in this browser only • No backend settings endpoint is used
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px]">
          {hasUnsavedChanges && (
            <span className="rounded border border-amber-800/60 bg-amber-950/40 px-2 py-1 text-amber-300">
              Unsaved changes
            </span>
          )}
          <span className="rounded border border-slate-800 bg-slate-900 px-2 py-1 text-slate-400">
            Local configuration
          </span>
        </div>
      </div>

      <ConnectionStatusPanel
        backendStatus={backendStatus}
        websocketStatus={websocketStatus}
        reconciliationStatus={reconciliationStatus}
      />

      <div className="flex items-start gap-3 rounded-md border border-slate-800 bg-slate-900/90 p-3">
        <Shield size={16} className="mt-0.5 shrink-0 text-emerald-400" />
        <p className="font-mono text-xs leading-relaxed text-slate-400">
          These controls configure the dashboard only. They do not calculate strategies, manage risk,
          connect to Bybit, or place orders.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="space-y-4 rounded-md border border-slate-800 bg-slate-900/70 p-4 font-mono">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">Strategies & Markets</h3>
                      </div>

          <fieldset className="space-y-2">
            <legend className="mb-2 text-xs font-medium text-slate-400">Strategy toggles</legend>
            {STRATEGIES.map((strategy) => (
              <Toggle
                key={strategy.key}
                checked={settings.strategies[strategy.key]}
                label={strategy.label}
                description={strategy.description}
                onChange={() => toggleStrategy(strategy.key)}
              />
            ))}
            {errors.strategies && <p className="text-[11px] text-rose-400">{errors.strategies}</p>}
          </fieldset>

          <ChoiceGroup
            legend="Symbols"
            values={SYMBOLS}
            selected={settings.symbols}
            error={errors.symbols}
            onToggle={toggleSymbol}
          />
          <ChoiceGroup
            legend="Timeframes"
            values={TIMEFRAMES}
            selected={settings.timeframes}
            error={errors.timeframes}
            onToggle={toggleTimeframe}
          />
        </section>

        <section className="space-y-4 rounded-md border border-slate-800 bg-slate-900/70 p-4 font-mono">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">Filters & Limits</h3>
            <p className="mt-1 text-[11px] text-slate-500">Validated local limits for the dashboard configuration.</p>
          </div>

          <div>
            <label htmlFor="risk-per-trade" className="mb-1 block text-xs text-slate-400">Risk per trade (%)</label>
            <input
              id="risk-per-trade"
              type="number"
              min="0.1"
              max="2"
              step="0.1"
              value={settings.riskPerTrade}
              onChange={(event) => update('riskPerTrade', Number(event.target.value))}
              aria-describedby={errors.riskPerTrade ? 'risk-per-trade-error' : undefined}
              className={fieldClass}
            />
            {errors.riskPerTrade && <p id="risk-per-trade-error" className="mt-1.5 text-[11px] text-rose-400">{errors.riskPerTrade}</p>}
          </div>

          <div>
            <label htmlFor="spread-threshold" className="mb-1 block text-xs text-slate-400">Spread filter threshold (%)</label>
            <input
              id="spread-threshold"
              type="number"
              min="0"
              step="0.01"
              value={settings.spreadFilterThreshold}
              onChange={(event) => update('spreadFilterThreshold', Number(event.target.value))}
              aria-describedby={errors.spreadFilterThreshold ? 'spread-threshold-error' : undefined}
              className={fieldClass}
            />
            {errors.spreadFilterThreshold && <p id="spread-threshold-error" className="mt-1.5 text-[11px] text-rose-400">{errors.spreadFilterThreshold}</p>}
          </div>

          <Toggle
            checked={settings.volatilityFilterEnabled}
            label="Volatility filter"
            description="Enable the frontend configuration flag"
            onChange={() => update('volatilityFilterEnabled', !settings.volatilityFilterEnabled)}
          />

          <div>
            <label htmlFor="max-open-positions" className="mb-1 block text-xs text-slate-400">Max open positions</label>
            <input
              id="max-open-positions"
              type="number"
              min="1"
              step="1"
              value={settings.maxOpenPositions}
              onChange={(event) => update('maxOpenPositions', Number(event.target.value))}
              aria-describedby={errors.maxOpenPositions ? 'max-open-positions-error' : undefined}
              className={fieldClass}
            />
            {errors.maxOpenPositions && <p id="max-open-positions-error" className="mt-1.5 text-[11px] text-rose-400">{errors.maxOpenPositions}</p>}
          </div>

          <div>
            <label htmlFor="trading-mode" className="mb-1 block text-xs text-slate-400">Trading mode</label>
            <input id="trading-mode" readOnly value={settings.mode} className={`${fieldClass} cursor-not-allowed text-emerald-300`} />
            <p className="mt-1.5 text-[11px] text-slate-500">Read-only. This project is scoped to Bybit Demo Trading.</p>
          </div>
        </section>
      </div>

      <div className="flex flex-col gap-3 rounded-md border border-slate-800 bg-slate-900/80 p-3 sm:flex-row sm:items-center sm:justify-between">
        <div aria-live="polite" className="min-h-4 font-mono text-xs">
          {saveError ? (
            <span className="text-rose-400">{saveError}</span>
          ) : saveMessage ? (
            <span className="flex items-center gap-1.5 text-emerald-400"><Check size={13} />{saveMessage}</span>
          ) : hasUnsavedChanges ? (
            <span className="text-amber-300">Review validation, then save your changes.</span>
          ) : (
            <span className="text-slate-500">All changes saved.</span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={reset}
            disabled={isSaving}
            className="inline-flex items-center justify-center gap-2 rounded border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-300 transition hover:border-slate-600 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RotateCcw size={13} /> Reset to defaults
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={isSaving || !hasUnsavedChanges || !isValid}
            className="inline-flex items-center justify-center gap-2 rounded border border-emerald-700 bg-emerald-600 px-4 py-2 font-mono text-xs font-semibold text-slate-950 transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
          >
            <Save size={13} className={isSaving ? 'animate-pulse' : ''} />
            {isSaving ? 'Saving…' : 'Save settings'}
          </button>
        </div>
      </div>
      
    </div>
  );
};
