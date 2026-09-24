export function buildEnrichedAIContext(
  baseContext: Record<string, unknown>,
  scannerStatus: unknown | null,
  scannerCandidates: unknown[] | null,
  scannerWatchlist: unknown | null,
  botRuntime: unknown | null
) {
  return {
    ...baseContext,

    snapshotFetchedAt: new Date().toISOString(),

    dataAvailability: {
      scannerStatus: scannerStatus !== null,
      scannerCandidates: scannerCandidates !== null,
      scannerWatchlist: scannerWatchlist !== null,
      botRuntime: botRuntime !== null,
    },

    scannerStatus,
    scannerCandidates,
    scannerWatchlist,
    botRuntime,
  };
}
