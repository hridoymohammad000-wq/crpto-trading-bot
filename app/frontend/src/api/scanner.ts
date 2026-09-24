import { API_BASE_URL } from "./client.ts";

export async function fetchScannerStatus() {
  const res = await fetch(`${API_BASE_URL}/scanner/status`);
  if (!res.ok) throw new Error("Failed to fetch scanner status");
  return res.json();
}

export async function fetchScannerUniverse() {
  const res = await fetch(`${API_BASE_URL}/scanner/universe`);
  if (!res.ok) throw new Error("Failed to fetch scanner universe");
  return res.json();
}

export async function fetchScannerWatchlist() {
  const res = await fetch(`${API_BASE_URL}/scanner/watchlist`);
  if (!res.ok) throw new Error("Failed to fetch scanner watchlist");
  return res.json();
}

export async function fetchScannerCandidates() {
  const res = await fetch(`${API_BASE_URL}/scanner/candidates`);
  if (!res.ok) throw new Error("Failed to fetch scanner candidates");
  return res.json();
}

