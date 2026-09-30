/**
 * Convert API/runtime numeric values safely.
 */
function safeNumber(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * Format numeric currency values with configurable decimals and sign prefix
 */
export function formatCurrency(
  value: number | string | null | undefined,
  options?: {
    decimals?: number;
    showSign?: boolean;
    currencySymbol?: string;
  }
): string {
  const numericValue = safeNumber(value);
  if (numericValue === null) return '—';

  const decimals = options?.decimals ?? 2;
  const showSign = options?.showSign ?? false;
  const symbol = options?.currencySymbol ?? '$';

  const sign = showSign && numericValue > 0 ? '+' : numericValue < 0 ? '-' : '';
  const absValue = Math.abs(numericValue);

  const formattedNumber = absValue.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return `${sign}${symbol}${formattedNumber}`;
}

/**
 * Format percentage values safely.
 */
export function formatPercentage(
  value: number | string | null | undefined,
  options?: {
    decimals?: number;
    showSign?: boolean;
  }
): string {
  const numericValue = safeNumber(value);
  if (numericValue === null) return '—';

  const decimals = options?.decimals ?? 2;
  const showSign = options?.showSign ?? false;

  const sign = showSign && numericValue > 0 ? '+' : '';
  return `${sign}${numericValue.toFixed(decimals)}%`;
}

/**
 * Format cryptocurrency prices cleanly
 */
export function formatPrice(
  price: number | string | null | undefined,
  decimals: number = 2
): string {
  const numericPrice = safeNumber(price);
  if (numericPrice === null) return 'Unavailable';

  return numericPrice.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function getPnlColor(value: number): string {
  if (value > 0) return 'text-emerald-400';
  if (value < 0) return 'text-rose-400';
  return 'text-slate-400';
}

export function getPnlBadgeClasses(value: number): string {
  if (value > 0) return 'bg-emerald-950/60 text-emerald-400 border-emerald-800/50';
  if (value < 0) return 'bg-rose-950/60 text-rose-400 border-rose-800/50';
  return 'bg-slate-800/60 text-slate-400 border-slate-700/50';
}
