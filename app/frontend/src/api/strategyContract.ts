import type {
  StrategyDiagnostic,
  StrategyIndicators,
  StrategyReasonCode,
} from '../types/strategy.ts';

const SYMBOLS = new Set(['BTCUSDT', 'ETHUSDT', 'SOLUSDT']);
const REASON_CODES = new Set<StrategyReasonCode>([
  'NO_CROSSOVER',
  'ENTRY_WINDOW_EXPIRED',
  'RSI_FILTER_FAILED',
  'ADX_FILTER_FAILED',
  'VOLUME_FILTER_FAILED',
  'CANDLE_CONFIRMATION_FAILED',
  'HTF_TREND_FAILED',
  'HTF_SLOPE_FAILED',
  'INSUFFICIENT_DATA',
  'DUPLICATE_SETUP',
]);

export class StrategyContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'StrategyContractError';
  }
}

export function parseStrategyDiagnostic(value: unknown): StrategyDiagnostic {
  const response = record(value, 'strategy response');
  const symbol = requiredString(response.symbol, 'symbol');
  if (!SYMBOLS.has(symbol)) invalid('symbol');
  if (response.strategy !== 'EMA_RSI_ADX_MOMENTUM') invalid('strategy');
  if (response.result !== 'SIGNAL' && response.result !== 'NO_SIGNAL') invalid('result');
  const result = response.result;
  const side = nullableEnum(response.side, ['BUY', 'SELL'], 'side');
  const referenceEntryPrice = nullableNumber(
    response.reference_entry_price,
    'reference_entry_price',
  );
  const confidence = nullableNumber(response.confidence, 'confidence');
  if (confidence !== null && (!Number.isInteger(confidence) || confidence < 0 || confidence > 100)) {
    invalid('confidence');
  }
  if (result === 'SIGNAL' && (side === null || referenceEntryPrice === null || confidence === null)) {
    throw new StrategyContractError('Signal response is missing signal details.');
  }
  if (result === 'NO_SIGNAL' && (side !== null || referenceEntryPrice !== null || confidence !== null)) {
    throw new StrategyContractError('No-signal response contains unexpected signal details.');
  }

  const rawReasons = response.reason_codes;
  if (!Array.isArray(rawReasons)) invalid('reason_codes');
  const reasonCodes = rawReasons.map((reason) => {
    if (typeof reason !== 'string' || !REASON_CODES.has(reason as StrategyReasonCode)) {
      invalid('reason_codes');
    }
    return reason as StrategyReasonCode;
  });
  const crossoverAgeCandles = nullableNumber(
    response.crossover_age_candles,
    'crossover_age_candles',
  );
  if (
    crossoverAgeCandles !== null &&
    (!Number.isInteger(crossoverAgeCandles) || crossoverAgeCandles < 0)
  ) {
    invalid('crossover_age_candles');
  }
  if (typeof response.duplicate_setup !== 'boolean') invalid('duplicate_setup');

  return {
    symbol: symbol as StrategyDiagnostic['symbol'],
    strategy: 'EMA_RSI_ADX_MOMENTUM',
    evaluationTime: isoDate(response.evaluation_time, 'evaluation_time'),
    latest5mCandleTime: nullableIsoDate(
      response.latest_5m_candle_time,
      'latest_5m_candle_time',
    ),
    latest15mCandleTime: nullableIsoDate(
      response.latest_15m_candle_time,
      'latest_15m_candle_time',
    ),
    result,
    side,
    referenceEntryPrice,
    confidence,
    reasonCodes,
    indicators: parseIndicators(response.indicators),
    crossoverAgeCandles,
    duplicateSetup: response.duplicate_setup,
  };
}

function parseIndicators(value: unknown): StrategyIndicators {
  const indicators = record(value, 'indicators');
  return {
    emaFast: nullableNumber(indicators.ema_fast, 'indicators.ema_fast'),
    emaSlow: nullableNumber(indicators.ema_slow, 'indicators.ema_slow'),
    rsi: nullableNumber(indicators.rsi, 'indicators.rsi'),
    adx: nullableNumber(indicators.adx, 'indicators.adx'),
    volume: nullableNumber(indicators.volume, 'indicators.volume'),
    averageVolume: nullableNumber(indicators.average_volume, 'indicators.average_volume'),
    higherTfEmaFast: nullableNumber(
      indicators.higher_tf_ema_fast,
      'indicators.higher_tf_ema_fast',
    ),
    higherTfEmaSlow: nullableNumber(
      indicators.higher_tf_ema_slow,
      'indicators.higher_tf_ema_slow',
    ),
    higherTfEmaFastPrevious: nullableNumber(
      indicators.higher_tf_ema_fast_previous,
      'indicators.higher_tf_ema_fast_previous',
    ),
  };
}

function record(value: unknown, field: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) invalid(field);
  return value as Record<string, unknown>;
}

function requiredString(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.length === 0) invalid(field);
  return value;
}

function nullableNumber(value: unknown, field: string): number | null {
  if (value === null) return null;
  if (typeof value !== 'number' && typeof value !== 'string') invalid(field);
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) invalid(field);
  return parsed;
}

function isoDate(value: unknown, field: string): string {
  const text = requiredString(value, field);
  if (Number.isNaN(Date.parse(text))) invalid(field);
  return text;
}

function nullableIsoDate(value: unknown, field: string): string | null {
  return value === null ? null : isoDate(value, field);
}

function nullableEnum<T extends string>(
  value: unknown,
  allowed: readonly T[],
  field: string,
): T | null {
  if (value === null) return null;
  if (typeof value !== 'string' || !allowed.includes(value as T)) invalid(field);
  return value as T;
}

function invalid(field: string): never {
  throw new StrategyContractError(`Invalid ${field} in strategy response.`);
}
