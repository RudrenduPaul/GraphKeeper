/**
 * Shared types for GraphKeeper's local knowledge-graph store.
 *
 * The store is a single JSON file, `.graphkeeper/graph.json`, containing:
 *  - co-change data mined from `git log` (GraphKeeper's own contribution)
 *  - optionally, symbol/call-graph data merged in from graphify, if graphify
 *    is installed and enrichment succeeded (see src/graphify.ts)
 */

/** One unordered pair of files that changed together in one or more commits. */
export interface CoChangeEdge {
  a: string;
  b: string;
  count: number;
}

/** A node from graphify's `graph.json` (symbol, file, or other concept). */
export interface GraphifyNode {
  id: string;
  label: string;
  file_type?: string;
  source_file?: string;
  source_location?: string;
  _origin?: string;
  [key: string]: unknown;
}

/** An edge from graphify's `graph.json` (e.g. `calls`, `imports`, `contains`). */
export interface GraphifyEdge {
  source: string;
  target: string;
  relation: string;
  confidence?: string;
  context?: string;
  source_file?: string;
  source_location?: string;
  weight?: number;
  _origin?: string;
  [key: string]: unknown;
}

/** Raw shape of graphify's own `graph.json` output, as produced by `graphify extract`. */
export interface GraphifyRawGraph {
  nodes: GraphifyNode[];
  edges: GraphifyEdge[];
  hyperedges?: unknown[];
  input_tokens?: number;
  output_tokens?: number;
}

/** Result of attempting graphify enrichment during a build. */
export interface GraphifyEnrichment {
  enriched: boolean;
  /** Version string reported by `graphify --version`, if detected. */
  version: string | null;
  /** Human-readable reason enrichment was skipped, if it was. */
  skippedReason: string | null;
  nodes: GraphifyNode[];
  edges: GraphifyEdge[];
}

/** The full on-disk store written to `.graphkeeper/graph.json`. */
export interface GraphKeeperStore {
  /** Store schema version, for forward compatibility. */
  version: 1;
  generatedAt: string;
  /** Absolute path to the repo this graph was built from. */
  repoPath: string;
  /** Number of commits walked to build the co-change graph. */
  commitsAnalyzed: number;
  /** Number of commits skipped for exceeding maxFilesPerCommit. */
  commitsSkipped: number;
  /** Co-change edges, deduplicated and unordered (a < b lexicographically). */
  coChange: CoChangeEdge[];
  /** Per-file commit counts, used to normalize co-change frequency. */
  fileCommitCounts: Record<string, number>;
  graphify: GraphifyEnrichment;
}

export interface BuildOptions {
  /** Skip commits touching more than this many files (default: 100). */
  maxFilesPerCommit?: number;
  /** Skip graphify enrichment even if graphify is installed. */
  skipGraphify?: boolean;
  /** Directory graphify's raw extraction output is written into (contained within .graphkeeper/). */
  graphifyTimeoutMs?: number;
}

export interface BuildResult {
  store: GraphKeeperStore;
  outputPath: string;
}

export interface CoChangeQueryResult {
  file: string;
  results: Array<{ file: string; count: number }>;
}

export interface CallsQueryResult {
  symbol: string;
  available: boolean;
  unavailableReason: string | null;
  node: GraphifyNode | null;
  calls: Array<{ node: GraphifyNode | null; edge: GraphifyEdge }>;
  calledBy: Array<{ node: GraphifyNode | null; edge: GraphifyEdge }>;
}
