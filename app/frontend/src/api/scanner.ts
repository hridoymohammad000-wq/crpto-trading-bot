import { API_BASE_URL } from "./client.ts";

export interface ScannerStatus {
  last_refresh: string | null;
  universe_count: number;
  eligible_count: number;
  watching_count: number;
  armed_count: number;
  open_positions: number;
}

export interface ScannerCandidate {
  symbol: string;
  adx: number | null;
  rvol: number | null;
  regime: string;
  bias: string | null;
  market_quality_score: number;
  setup_quality_score: number;
  state: string;
  reason_codes: string[];
}

export interface ScannerSymbolState {
  symbol: string;
  state: string;
  execution_allowed: boolean;
  trend_1h: { trend_valid?: boolean; trend?: string };
  setup_15m: { setup_valid?: boolean };
  entry_5m: { entry_valid?: boolean; entry_status?: boolean };
  reason_codes: string[];
}

export interface ScannerWatchlist {
  core_symbols: string[];
  dynamic_symbols: string[];
  open_position_symbols: string[];
  cooldown_symbols: Record<string, string>;
  symbol_states: Record<string, ScannerSymbolState>;
}

async function readJson<T>(res: Response, message: string): Promise<T> {
  if (!res.ok) throw new Error(message);
  return res.json() as Promise<T>;
}

export async function fetchScannerStatus(): Promise<ScannerStatus> {
  const res = await fetch(`${API_BASE_URL}/scanner/status`);
  return readJson<ScannerStatus>(res, "Failed to fetch scanner status");
}

export async function fetchScannerUniverse(): Promise<ScannerCandidate[]> {
  const res = await fetch(`${API_BASE_URL}/scanner/universe`);
  return readJson<ScannerCandidate[]>(res, "Failed to fetch scanner universe");
}

export async function fetchScannerWatchlist(): Promise<ScannerWatchlist> {
  const res = await fetch(`${API_BASE_URL}/scanner/watchlist`);
  return readJson<ScannerWatchlist>(res, "Failed to fetch scanner watchlist");
}

export async function fetchScannerCandidates(): Promise<ScannerCandidate[]> {
  const res = await fetch(`${API_BASE_URL}/scanner/candidates`);
  return readJson<ScannerCandidate[]>(res, "Failed to fetch scanner candidates");
}
