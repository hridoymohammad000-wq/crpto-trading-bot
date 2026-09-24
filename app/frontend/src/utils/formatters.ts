/**
 * Format numeric currency values with configurable decimals and sign prefix
 */
export function formatCurrency(
  value: number | null | undefined,
  options?: {
    decimals?: number;
    showSign?: boolean;
    currencySymbol?: string;
  }
): string {
  if (value === null || value === undefined || !isFinite(value)) return '—';
  
  const decimals = options?.decimals ?? 2;
  const showSign = options?.showSign ?? false;
  const symbol = options?.currencySymbol ?? '$';

  const sign = showSign && value > 0 ? '+' : value < 0 ? '-' : '';
  const absValue = Math.abs(value);
  const formattedNumber = absValue.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return `${sign}${symbol}${formattedNumber}`;
}

/**
 * Format percentage values with configurable decimals and sign prefix
 */
export function formatPercentage(
  value: number | null | undefined,
  options?: {
    decimals?: number;
    showSign?: boolean;
  }
): string {
  if (value === null || value === undefined || !isFinite(value)) return '—';

  const decimals = options?.decimals ?? 2;
  const showSign = options?.showSign ?? false;

  const sign = showSign && value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}


/**
 * Format cryptocurrency prices cleanly
 */
export function formatPrice(price: number | null | undefined, decimals: number = 2): string {
  if (price === null || price === undefined) return 'Unavailable';
  return price.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * Get standard Tailwind text color class based on profit/loss value
 */
export function getPnlColor(value: number): string {
  if (value > 0) return 'text-emerald-400';
  if (value < 0) return 'text-rose-400';
  return 'text-slate-400';
}

/**
 * Get standard Tailwind badge style class based on profit/loss value
 */
export function getPnlBadgeClasses(value: number): string {
  if (value > 0) return 'bg-emerald-950/60 text-emerald-400 border-emerald-800/50';
  if (value < 0) return 'bg-rose-950/60 text-rose-400 border-rose-800/50';
  return 'bg-slate-800/60 text-slate-400 border-slate-700/50';
}
