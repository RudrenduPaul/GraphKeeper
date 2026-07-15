import * as path from "node:path";
import type { CallsQueryResult, CoChangeQueryResult, GraphKeeperStore, GraphifyNode } from "./types.js";

/** Normalizes a user-supplied file argument to the repo-relative form GraphKeeper stores paths in. */
export function normalizeFileArg(store: GraphKeeperStore, file: string): string {
  let normalized = file;
  if (path.isAbsolute(normalized)) {
    const rel = path.relative(store.repoPath, normalized);
    if (!rel.startsWith("..")) {
      normalized = rel;
    }
  }
  normalized = normalized.replace(/^\.\//, "");
  return normalized.split(path.sep).join("/");
}

/**
 * Finds files that historically changed alongside `file`, ranked by
 * co-change frequency (how many commits touched both).
 */
export function queryCoChange(store: GraphKeeperStore, file: string, options: { limit?: number } = {}): CoChangeQueryResult {
  const target = normalizeFileArg(store, file);
  const results: Array<{ file: string; count: number }> = [];
  for (const edge of store.coChange) {
    if (edge.a === target) {
      results.push({ file: edge.b, count: edge.count });
    } else if (edge.b === target) {
      results.push({ file: edge.a, count: edge.count });
    }
  }
  results.sort((x, y) => y.count - x.count);
  const limited = options.limit && options.limit > 0 ? results.slice(0, options.limit) : results;
  return { file: target, results: limited };
}

function normalizeSymbol(s: string): string {
  return s.trim().replace(/\(\)\s*$/, "").toLowerCase();
}

/** Finds a graphify node whose label best matches `symbol` (exact match preferred, then case-insensitive). */
export function findGraphifyNode(nodes: GraphifyNode[], symbol: string): GraphifyNode | null {
  const exact = nodes.find((n) => n.label === symbol || n.label === `${symbol}()`);
  if (exact) return exact;
  const target = normalizeSymbol(symbol);
  const ci = nodes.find((n) => normalizeSymbol(n.label) === target);
  if (ci) return ci;
  const byId = nodes.find((n) => n.id === symbol || n.id.endsWith(`_${symbol}`));
  return byId ?? null;
}

/**
 * Finds callers/callees of `symbol` using graphify's `calls` edges. Only
 * meaningful when the build included graphify enrichment; otherwise reports
 * why (never a silent empty result or a crash).
 */
export function queryCalls(store: GraphKeeperStore, symbol: string): CallsQueryResult {
  if (!store.graphify.enriched) {
    return {
      symbol,
      available: false,
      unavailableReason:
        store.graphify.skippedReason ??
        "This build did not include graphify enrichment, so call-graph queries aren't available. " +
          "Install graphify (`uv tool install graphifyy`) and re-run `graphkeeper build` to enable them.",
      node: null,
      calls: [],
      calledBy: [],
    };
  }

  const nodesById = new Map(store.graphify.nodes.map((n) => [n.id, n]));
  const node = findGraphifyNode(store.graphify.nodes, symbol);

  if (!node) {
    return {
      symbol,
      available: true,
      unavailableReason: null,
      node: null,
      calls: [],
      calledBy: [],
    };
  }

  const calls = store.graphify.edges
    .filter((e) => e.relation === "calls" && e.source === node.id)
    .map((edge) => ({ node: nodesById.get(edge.target) ?? null, edge }));
  const calledBy = store.graphify.edges
    .filter((e) => e.relation === "calls" && e.target === node.id)
    .map((edge) => ({ node: nodesById.get(edge.source) ?? null, edge }));

  return { symbol, available: true, unavailableReason: null, node, calls, calledBy };
}
