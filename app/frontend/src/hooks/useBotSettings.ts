import { useCallback, useMemo, useState } from 'react';
import { BotSettings, BotSettingsErrors, StrategyKey, Timeframe, TradingSymbol } from '../types';

const STORAGE_KEY = 'crypto-intraday-bot:settings:v1';
const VALID_SYMBOLS: TradingSymbol[] = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
const VALID_TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m'];

export const DEFAULT_BOT_SETTINGS: BotSettings = {
  strategies: { emaRsi: true, bollingerSqueeze: true },
  riskPerTrade: 1,
  symbols: [...VALID_SYMBOLS],
  timeframes: [...VALID_TIMEFRAMES],
  spreadFilterThreshold: 0.1,
  volatilityFilterEnabled: true,
  maxOpenPositions: 3,
  mode: 'DEMO',
};

function isStoredSettings(value: unknown): value is BotSettings {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<BotSettings>;
  return (
    candidate.mode === 'DEMO' &&
    typeof candidate.riskPerTrade === 'number' &&
    typeof candidate.spreadFilterThreshold === 'number' &&
    typeof candidate.volatilityFilterEnabled === 'boolean' &&
    typeof candidate.maxOpenPositions === 'number' &&
    Array.isArray(candidate.symbols) &&
    candidate.symbols.every((item) => VALID_SYMBOLS.includes(item)) &&
    Array.isArray(candidate.timeframes) &&
    candidate.timeframes.every((item) => VALID_TIMEFRAMES.includes(item)) &&
    !!candidate.strategies &&
    typeof candidate.strategies.emaRsi === 'boolean' &&
    typeof candidate.strategies.bollingerSqueeze === 'boolean'
  );
}

function readSavedSettings(): BotSettings {
  if (typeof window === 'undefined') return structuredClone(DEFAULT_BOT_SETTINGS);
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT_BOT_SETTINGS);
    const parsed: unknown = JSON.parse(raw);
    return isStoredSettings(parsed) ? parsed : structuredClone(DEFAULT_BOT_SETTINGS);
  } catch {
    return structuredClone(DEFAULT_BOT_SETTINGS);
  }
}

function validate(settings: BotSettings): BotSettingsErrors {
  const errors: BotSettingsErrors = {};
  if (!Object.values(settings.strategies).some(Boolean)) {
    errors.strategies = 'Enable at least one strategy.';
  }
  if (settings.riskPerTrade < 0.1 || settings.riskPerTrade > 2) {
    errors.riskPerTrade = 'Risk per trade must be between 0.1% and 2%.';
  }
  if (settings.symbols.length === 0) errors.symbols = 'Select at least one symbol.';
  if (settings.timeframes.length === 0) errors.timeframes = 'Select at least one timeframe.';
  if (!Number.isFinite(settings.spreadFilterThreshold) || settings.spreadFilterThreshold < 0) {
    errors.spreadFilterThreshold = 'Spread threshold must be zero or greater.';
  }
  if (!Number.isInteger(settings.maxOpenPositions) || settings.maxOpenPositions < 1) {
    errors.maxOpenPositions = 'Max open positions must be a whole number of at least 1.';
  }
  return errors;
}

export function useBotSettings() {
  const [savedSettings, setSavedSettings] = useState<BotSettings>(readSavedSettings);
  const [settings, setSettings] = useState<BotSettings>(() => structuredClone(savedSettings));
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const errors = useMemo(() => validate(settings), [settings]);
  const hasUnsavedChanges = useMemo(
    () => JSON.stringify(settings) !== JSON.stringify(savedSettings),
    [savedSettings, settings],
  );
  const isValid = Object.keys(errors).length === 0;

  const update = useCallback(<K extends keyof BotSettings>(key: K, value: BotSettings[K]) => {
    setSettings((current) => ({ ...current, [key]: value }));
    setSaveMessage(null);
    setSaveError(null);
  }, []);

  const toggleStrategy = useCallback((key: StrategyKey) => {
    setSettings((current) => ({
      ...current,
      strategies: { ...current.strategies, [key]: !current.strategies[key] },
    }));
    setSaveMessage(null);
    setSaveError(null);
  }, []);

  const toggleSymbol = useCallback((symbol: TradingSymbol) => {
    setSettings((current) => ({
      ...current,
      symbols: current.symbols.includes(symbol)
        ? current.symbols.filter((item) => item !== symbol)
        : [...current.symbols, symbol],
    }));
    setSaveMessage(null);
    setSaveError(null);
  }, []);

  const toggleTimeframe = useCallback((timeframe: Timeframe) => {
    setSettings((current) => ({
      ...current,
      timeframes: current.timeframes.includes(timeframe)
        ? current.timeframes.filter((item) => item !== timeframe)
        : [...current.timeframes, timeframe],
    }));
    setSaveMessage(null);
    setSaveError(null);
  }, []);

  const save = useCallback(async () => {
    const currentErrors = validate(settings);
    if (Object.keys(currentErrors).length > 0 || typeof window === 'undefined') return;
    setIsSaving(true);
    setSaveMessage(null);
    setSaveError(null);
    try {
      await new Promise((resolve) => window.setTimeout(resolve, 250));
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
      setSavedSettings(structuredClone(settings));
      setSaveMessage('Settings saved locally.');
    } catch {
      setSaveError('Unable to save settings in this browser. Check storage permissions.');
    } finally {
      setIsSaving(false);
    }
  }, [settings]);

  const reset = useCallback(() => {
    setSettings(structuredClone(DEFAULT_BOT_SETTINGS));
    setSaveMessage(null);
    setSaveError(null);
  }, []);

  return {
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
  };
}
