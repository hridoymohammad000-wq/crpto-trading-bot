import React, { useEffect, useState } from 'react';
import { ShieldAlert, RotateCcw } from 'lucide-react';
import { fetchScannerCandidates } from '../api/scanner';
import { UseReconciliationReturn } from '../hooks/useReconciliation';

export interface ReconciliationAlertsProps {
  reconData: UseReconciliationReturn;
  className?: string;
}

export const ReconciliationAlerts: React.FC<ReconciliationAlertsProps> = ({ reconData, className = '' }) => {
  const [stuckSymbols, setStuckSymbols] = useState<string[]>([]);

  useEffect(() => {
    let isMounted = true;
    
    const checkCandidates = async () => {
      try {
        const candidates = await fetchScannerCandidates();
        if (isMounted && Array.isArray(candidates)) {
          const stuck = candidates
            .filter(c => 
              c.execution?.execution_status === 'UNKNOWN_RECONCILING' ||
              c.reason_codes?.includes('RECONCILIATION_MISMATCH')
            )
            .map(c => c.symbol);
          setStuckSymbols(stuck);
        }
      } catch (err) {
        // Silently fail, banner handles its own best-effort fetch
      }
    };

    checkCandidates();
    const intervalId = setInterval(checkCandidates, 30000); // Check every 30s
    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, []);

  const hasReconErrors = reconData.isError || (reconData.data && reconData.data.status !== 'SYNCED');
  const mismatches: string[] = reconData.data?.mismatches || [];
  const hasStuckSymbols = stuckSymbols.length > 0;

  if (!hasReconErrors && !hasStuckSymbols) {
    return null; // Nothing to report
  }

  return (
    <div className={`rounded-md border border-rose-800/60 bg-rose-950/40 p-4 shadow-sm font-mono text-sm ${className}`}>
      <div className="flex items-start gap-3">
        <ShieldAlert size={18} className="mt-0.5 shrink-0 text-rose-500" />
        <div className="flex-1">
          <h3 className="font-semibold text-rose-400 flex items-center justify-between">
            Reconciliation Warnings
            <button 
              onClick={() => reconData.refetch()} 
              disabled={reconData.isLoading}
              className="flex items-center gap-1.5 text-xs text-rose-300 hover:text-rose-100 disabled:opacity-50 transition-colors"
            >
              <RotateCcw size={12} className={reconData.isLoading ? "animate-spin" : ""} />
              Force Sync
            </button>
          </h3>
          
          <div className="mt-2 space-y-3">
            {reconData.isError && (
              <p className="text-rose-200/90 text-xs">{reconData.errorMessage || "Failed to fetch reconciliation state."}</p>
            )}

            {reconData.data && reconData.data.status !== 'SYNCED' && (
              <div className="space-y-1 text-xs">
                <p className="text-rose-300 font-medium">Backend Status: <span className="text-rose-200">{reconData.data.status}</span></p>
                {mismatches.length > 0 ? (
                  <ul className="list-disc pl-4 space-y-1 text-rose-200/80">
                    {mismatches.map((m, i) => <li key={i}>{m}</li>)}
                  </ul>
                ) : (
                  <p className="text-rose-200/80">State is out of sync but no specific mismatches were returned.</p>
                )}
              </div>
            )}

            {hasStuckSymbols && (
              <div className="space-y-1 text-xs pt-1 border-t border-rose-800/30">
                <p className="text-amber-400 font-medium">Stuck Symbols (Execution Blocked):</p>
                <p className="text-amber-200/80">
                  The following symbols have unverified execution intents and are locked from trading until manually resolved:
                  <span className="ml-2 font-semibold text-amber-300 bg-amber-950/50 px-1.5 py-0.5 rounded border border-amber-800/50">
                    {stuckSymbols.join(", ")}
                  </span>
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
