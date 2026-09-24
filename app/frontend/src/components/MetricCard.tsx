import React from 'react';

export interface MetricCardProps {
  id: string;
  /** Primary label displayed in the top header */
  label?: string;
  title?: string;
  /** Primary metric value */
  value: string | number;
  /** Secondary change or descriptive sub-text */
  subValue?: string;
  change?: string;
  /** Direction or sentiment for the sub-value styling */
  trend?: 'up' | 'down' | 'neutral';
  changeType?: 'positive' | 'negative' | 'neutral';
  infoTooltip?: string;
  icon?: React.ReactNode;
  className?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  id,
  label,
  title,
  value,
  subValue,
  change,
  trend,
  changeType,
  icon,
  className = '',
}) => {
  const displayTitle = label || title || '';
  const displaySub = change || subValue;

  // Derive sentiment style
  const isUp = trend === 'up' || changeType === 'positive';
  const isDown = trend === 'down' || changeType === 'negative';

  const trendColor = isUp
    ? 'text-emerald-400'
    : isDown
    ? 'text-rose-400'
    : 'text-slate-400';

  return (
    <div
      id={id}
      className={`bg-slate-900/70 border border-slate-800/90 rounded-md p-3 flex flex-col justify-between hover:border-slate-700 transition-colors ${className}`}
    >
      <div className="flex items-center justify-between text-xs text-slate-400 uppercase tracking-wider font-medium">
        <span>{displayTitle}</span>
        {icon && <span className="text-slate-500">{icon}</span>}
      </div>

      <div className="mt-2">
        <div className="text-xl font-bold font-mono text-slate-100 tracking-tight">
          {value}
        </div>
        {displaySub && (
          <div className={`text-xs font-mono font-medium mt-0.5 ${trendColor}`}>
            {displaySub}
          </div>
        )}
      </div>
    </div>
  );
};
