import { mineCoChange } from "./git.js";
import { runGraphifyEnrichment } from "./graphify.js";
import { resolveRepoRoot, writeStore } from "./store.js";
import type { BuildOptions, BuildResult, GraphKeeperStore } from "./types.js";

/**
 * Builds (or rebuilds) the GraphKeeper store for a repo: mines `git log` for
 * file-level co-change, optionally enriches it with graphify's symbol/call
 * graph if graphify is installed, and writes the merged result to
 * `.graphkeeper/graph.json`.
 */
export function build(targetPath: string, options: BuildOptions = {}): BuildResult {
  const repoRoot = resolveRepoRoot(targetPath);

  const mined = mineCoChange(
    repoRoot,
    options.maxFilesPerCommit !== undefined ? { maxFilesPerCommit: options.maxFilesPerCommit } : {},
  );

  const graphify = options.skipGraphify
    ? {
        enriched: false,
        version: null,
        skippedReason: "graphify enrichment skipped via --no-graphify.",
        nodes: [],
        edges: [],
      }
    : runGraphifyEnrichment(repoRoot);

  const store: GraphKeeperStore = {
    version: 1,
    generatedAt: new Date().toISOString(),
    repoPath: repoRoot,
    commitsAnalyzed: mined.commitsAnalyzed,
    commitsSkipped: mined.commitsSkipped,
    coChange: mined.coChange,
    fileCommitCounts: mined.fileCommitCounts,
    graphify,
  };

  const outputPath = writeStore(repoRoot, store);
  return { store, outputPath };
}
