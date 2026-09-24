import { useCallback, useEffect, useRef, useState } from 'react';
import {
  API_BASE_URL,
  ApiClientError,
  BackendStatusResponse,
  HealthCheckResponse,
  getHealth,
  getStatus,
  startBot,
  stopBot,
} from '../api';
import { BotStatus, ConnectionStatus } from '../types';

function normalizeBotStatus(status: unknown): BotStatus {
  return status === 'running' ? 'RUNNING' : 'STOPPED';
}

export interface UseBotBackendReturn {
  connectionStatus: ConnectionStatus;
  botStatus: BotStatus;
  isStatusLoading: boolean;
  isActionLoading: boolean;
  errorMessage: string | null;
  successMessage: string | null;
  lastChecked: Date | null;
  backendDetails: BackendStatusResponse | null;
  healthDetails: HealthCheckResponse | null;
  apiBaseUrl: string;
  refreshStatus: () => Promise<void>;
  toggleBot: () => Promise<void>;
  clearMessages: () => void;
}

export function useBotBackend(): UseBotBackendReturn {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('Offline');
  const [botStatus, setBotStatus] = useState<BotStatus>('STOPPED');
  const [isStatusLoading, setIsStatusLoading] = useState(false);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [backendDetails, setBackendDetails] = useState<BackendStatusResponse | null>(null);
  const [healthDetails, setHealthDetails] = useState<HealthCheckResponse | null>(null);

  const isMountedRef = useRef(true);
  const actionInFlightRef = useRef(false);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const clearMessages = useCallback(() => {
    setErrorMessage(null);
    setSuccessMessage(null);
  }, []);

  /**
   * Load backend health and bot status from the FastAPI backend
   */
  const refreshStatus = useCallback(async () => {
    setIsStatusLoading(true);
    try {
      const [health, statusRes] = await Promise.all([
        getHealth({ timeoutMs: 60000 }),
        getStatus({ timeoutMs: 60000 }),
      ]);
      if (!isMountedRef.current) return;

      setHealthDetails(health);
      setBackendDetails(statusRes);
      setConnectionStatus('Connected');
      setBotStatus(normalizeBotStatus(statusRes.bot_status));
      setLastChecked(new Date());
      setErrorMessage(null);
    } catch (err: unknown) {
      if (!isMountedRef.current) return;
      setLastChecked(new Date());

      if (err instanceof ApiClientError) {
        if (err.status && err.status >= 500) {
          setConnectionStatus('Error');
          setErrorMessage(`Backend Server Error (${err.status}): ${err.message}`);
        } else if (err.code === 'TIMEOUT_ERROR' || err.code === 'NETWORK_ERROR') {
          setConnectionStatus('Offline');
          setErrorMessage(
            `Backend offline or unreachable at ${API_BASE_URL}. Ensure your FastAPI server is running.`
          );
        } else {
          setConnectionStatus('Error');
          setErrorMessage(`API Error: ${err.message}`);
        }
      } else {
        setConnectionStatus('Offline');
        setErrorMessage(
          `Unable to connect to backend at ${API_BASE_URL}. Connection refused or network error.`
        );
      }
    } finally {
      if (isMountedRef.current) {
        setIsStatusLoading(false);
      }
    }
  }, []);

  /**
   * Toggle Bot ON/OFF with double-click protection and state synchronization
   */
  const toggleBot = useCallback(async () => {
    if (actionInFlightRef.current) return;

    actionInFlightRef.current = true;
    setIsActionLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    const shouldStart = botStatus !== 'RUNNING';

    try {
      if (shouldStart) {
        const response = await startBot({ timeoutMs: 60000 });

        if (!isMountedRef.current) return;

        setBotStatus(normalizeBotStatus(response.bot_status));
        setConnectionStatus('Connected');
        setSuccessMessage('Trading bot started successfully.');
      } else {
        const response = await stopBot({ timeoutMs: 60000 });

        if (!isMountedRef.current) return;

        setBotStatus(normalizeBotStatus(response.bot_status));
        setConnectionStatus('Connected');
        setSuccessMessage('Trading bot stopped successfully.');
      }

      // Re-synchronize full status in background
      try {
        const refreshed = await getStatus({ timeoutMs: 60000 });
        if (isMountedRef.current && refreshed) {
          setBackendDetails(refreshed);
          setBotStatus(normalizeBotStatus(refreshed.bot_status));
          setLastChecked(new Date());
        }
      } catch {
        // Status refresh failure is non-fatal if start/stop succeeded
      }
    } catch (err: unknown) {
      if (!isMountedRef.current) return;

      if (err instanceof ApiClientError) {
        if (err.code === 'TIMEOUT_ERROR' || err.code === 'NETWORK_ERROR') {
          setConnectionStatus('Offline');
          setErrorMessage(
            `Failed to reach backend at ${API_BASE_URL}. Ensure FastAPI is running.`
          );
        } else {
          setErrorMessage(`Failed to ${shouldStart ? 'start' : 'stop'} bot: ${err.message}`);
        }
      } else {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setErrorMessage(`Failed to ${shouldStart ? 'start' : 'stop'} bot: ${msg}`);
      }
    } finally {
      actionInFlightRef.current = false;
      if (isMountedRef.current) {
        setIsActionLoading(false);
      }
    }
  }, [botStatus]);

  // Initial status check on dashboard mount
  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  return {
    connectionStatus,
    botStatus,
    isStatusLoading,
    isActionLoading,
    errorMessage,
    successMessage,
    lastChecked,
    backendDetails,
    healthDetails,
    apiBaseUrl: API_BASE_URL,
    refreshStatus,
    toggleBot,
    clearMessages,
  };
}
