export function buildEnrichedAIContext(
  baseContext: Record<string, unknown>,
  scannerStatus: unknown | null,
  scannerCandidates: unknown[] | null,
  scannerWatchlist: unknown | null,
  botRuntime: unknown | null
) {
  return {
    ...baseContext,
    scannerStatus,
    scannerCandidates,
    scannerWatchlist,
    botRuntime
  };
}
