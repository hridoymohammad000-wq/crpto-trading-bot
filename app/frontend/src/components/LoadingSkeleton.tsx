import React from 'react';

export const PerformanceCardsSkeleton: React.FC = () => {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-2 animate-pulse">
      {Array.from({ length: 9 }).map((_, i) => (
        <div
          key={i}
          className="bg-slate-900/70 border border-slate-800/80 rounded-md p-3 space-y-2"
        >
          <div className="h-3 w-16 bg-slate-800 rounded" />
          <div className="h-6 w-20 bg-slate-800 rounded" />
          <div className="h-2.5 w-12 bg-slate-800/70 rounded" />
        </div>
      ))}
    </div>
  );
};

export const ChartPanelSkeleton: React.FC = () => {
  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-md overflow-hidden animate-pulse">
      <div className="px-3 py-2.5 bg-slate-950/80 border-b border-slate-800 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="h-6 w-48 bg-slate-800 rounded" />
          <div className="h-4 w-24 bg-slate-800 rounded" />
        </div>
        <div className="h-6 w-28 bg-slate-800 rounded" />
      </div>
      <div className="h-[340px] bg-slate-950 flex items-center justify-center p-6">
        <div className="space-y-3 w-full max-w-md text-center flex flex-col items-center">
          <div className="h-4 w-32 bg-slate-800 rounded" />
          <div className="h-28 w-full bg-slate-900/50 rounded border border-slate-800/50" />
          <div className="h-3 w-48 bg-slate-800/60 rounded" />
        </div>
      </div>
    </div>
  );
};

export const PositionsTableSkeleton: React.FC = () => {
  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-md overflow-hidden animate-pulse">
      <div className="px-3.5 py-2.5 bg-slate-950/80 border-b border-slate-800 flex justify-between">
        <div className="h-4 w-32 bg-slate-800 rounded" />
        <div className="h-4 w-16 bg-slate-800 rounded" />
      </div>
      <div className="p-3 space-y-2.5">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex justify-between items-center py-2 border-b border-slate-800/40">
            <div className="h-4 w-24 bg-slate-800 rounded" />
            <div className="h-4 w-12 bg-slate-800 rounded" />
            <div className="h-4 w-20 bg-slate-800 rounded" />
            <div className="h-4 w-20 bg-slate-800 rounded" />
            <div className="h-4 w-16 bg-slate-800 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
};

export const SignalFeedSkeleton: React.FC = () => {
  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-md overflow-hidden animate-pulse">
      <div className="px-3.5 py-2.5 bg-slate-950/80 border-b border-slate-800 flex justify-between">
        <div className="h-4 w-28 bg-slate-800 rounded" />
        <div className="h-4 w-16 bg-slate-800 rounded" />
      </div>
      <div className="p-3 space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex justify-between items-center py-2 border-b border-slate-800/40">
            <div className="h-3 w-14 bg-slate-800 rounded" />
            <div className="h-3 w-16 bg-slate-800 rounded" />
            <div className="h-3 w-10 bg-slate-800 rounded" />
            <div className="h-3 w-14 bg-slate-800 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
};

export const TradeHistorySkeleton: React.FC = () => {
  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-md overflow-hidden animate-pulse">
      <div className="px-3.5 py-2.5 bg-slate-950/80 border-b border-slate-800 flex justify-between">
        <div className="h-4 w-32 bg-slate-800 rounded" />
        <div className="h-4 w-24 bg-slate-800 rounded" />
      </div>
      <div className="p-3 space-y-2.5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex justify-between items-center py-2 border-b border-slate-800/40">
            <div className="h-4 w-20 bg-slate-800 rounded" />
            <div className="h-4 w-14 bg-slate-800 rounded" />
            <div className="h-4 w-16 bg-slate-800 rounded" />
            <div className="h-4 w-16 bg-slate-800 rounded" />
            <div className="h-4 w-16 bg-slate-800 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
};
