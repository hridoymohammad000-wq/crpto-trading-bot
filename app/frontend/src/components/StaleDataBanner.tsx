import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';

export interface StaleDataBannerProps {
  lastUpdatedIso?: string | null;
  lastUpdatedDate?: Date | null;
  thresholdMinutes?: number;
  dataSourceName: string;
}

export const StaleDataBanner: React.FC<StaleDataBannerProps> = ({
  lastUpdatedIso,
  lastUpdatedDate,
  thresholdMinutes = 15,
  dataSourceName,
}) => {
  const [isStale, setIsStale] = useState(false);
  const [minutesOld, setMinutesOld] = useState(0);

  useEffect(() => {
    const checkStaleness = () => {
      let targetDate: Date | null = null;
      if (lastUpdatedDate) {
        targetDate = lastUpdatedDate;
      } else if (lastUpdatedIso) {
        targetDate = new Date(lastUpdatedIso);
      }

      if (!targetDate || isNaN(targetDate.getTime())) {
        setIsStale(false);
        return;
      }

      const now = new Date();
      const diffMs = now.getTime() - targetDate.getTime();
      const diffMinutes = Math.floor(diffMs / 1000 / 60);

      setIsStale(diffMinutes >= thresholdMinutes);
      setMinutesOld(diffMinutes);
    };

    // Check immediately and then every minute
    checkStaleness();
    const intervalId = setInterval(checkStaleness, 60000);
    return () => clearInterval(intervalId);
  }, [lastUpdatedIso, lastUpdatedDate, thresholdMinutes]);

  if (!isStale) return null;

  return (
    <div className="flex items-center gap-3 rounded border border-amber-800/60 bg-amber-950/40 px-3 py-2.5 font-mono text-xs shadow-sm mb-4">
      <AlertTriangle size={16} className="shrink-0 text-amber-500" />
      <div>
        <span className="font-semibold text-amber-400">Network / Sync Warning: </span>
        <span className="text-amber-200/90">
          {dataSourceName} data is {minutesOld} minutes old. The bot might be experiencing network failures connecting to Bybit or internal sync issues.
        </span>
      </div>
    </div>
  );
};
