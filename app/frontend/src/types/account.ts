import { BotStatus } from './bot';

export type EnvironmentType = 'DEMO' | 'LIVE' | '-';
export type ConnectionStatus = 'Connected' | 'Offline' | 'Error' | 'Mock';

/**
 * Account summary representing the trading account's balances and day performance
 */
export interface AccountSummary {
  balance?: number;
  equity?: number;
  availableBalance?: number;
  availableTradingCapacity?: number;
  capacitySource?: string;
  dailyPnl?: number;
  dailyPnlPercentage?: number;
  environment: EnvironmentType;
  botStatus: BotStatus;
  connectionStatus: ConnectionStatus;
  backendConnection: string; // e.g. "Mock / Disconnected"
  lastUpdated: string; // e.g. "14:07:25 UTC"
}

/** Backward compatibility alias for AccountSummary */
export type AccountInfo = AccountSummary;
