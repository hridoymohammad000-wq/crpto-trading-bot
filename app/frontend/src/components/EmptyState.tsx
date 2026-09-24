import React from 'react';
import { AlertCircle, FilterX, Inbox, RefreshCw } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: 'inbox' | 'filter' | 'alert';
  actionLabel?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon = 'inbox',
  actionLabel,
  onAction,
}) => {
  return (
    <div
      id="empty-state-container"
      className="p-8 sm:p-10 flex flex-col items-center justify-center text-center font-mono"
    >
      <div className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500 mb-3">
        {icon === 'filter' ? (
          <FilterX size={18} />
        ) : icon === 'alert' ? (
          <AlertCircle size={18} />
        ) : (
          <Inbox size={18} />
        )}
      </div>

      <h3 className="text-sm font-semibold text-slate-200 tracking-tight">
        {title}
      </h3>

      {description && (
        <p className="text-xs text-slate-400 mt-1 max-w-sm leading-relaxed">
          {description}
        </p>
      )}

      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-3.5 inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors"
        >
          <RefreshCw size={12} />
          <span>{actionLabel}</span>
        </button>
      )}
    </div>
  );
};
