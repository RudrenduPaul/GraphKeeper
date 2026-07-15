import type { BuildResult, CallsQueryResult, CoChangeQueryResult } from "./types.js";

export function parsePositiveInt(raw: string, flagName: string): number {
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n) || n <= 0 || String(n) !== raw.trim()) {
    throw new Error(`Invalid ${flagName} value "${raw}". Expected a positive integer.`);
  }
  return n;
}

export function formatBuildText(result: BuildResult): string {
  const { store, outputPath } = result;
  const lines: string[] = [];
  lines.push(`GraphKeeper build complete: ${store.repoPath}`);
  lines.push("");
  lines.push(
    `Co-change graph: ${store.commitsAnalyzed} commit(s) analyzed, ${store.coChange.length} file pair(s) found` +
      (store.commitsSkipped > 0 ? ` (${store.commitsSkipped} commit(s) skipped: too many files changed)` : ""),
  );
  if (store.graphify.enriched) {
    lines.push(
      `graphify enrichment: included (v${store.graphify.version ?? "unknown"}) -- ` +
        `${store.graphify.nodes.length} node(s), ${store.graphify.edges.length} edge(s)`,
    );
  } else {
    lines.push(`graphify enrichment: skipped -- ${store.graphify.skippedReason ?? "unknown reason"}`);
  }
  lines.push("");
  lines.push(`Wrote ${outputPath}`);
  return lines.join("\n");
}

export function formatBuildJson(result: BuildResult): string {
  const { store, outputPath } = result;
  return JSON.stringify(
    {
      repoPath: store.repoPath,
      outputPath,
      generatedAt: store.generatedAt,
      commitsAnalyzed: store.commitsAnalyzed,
      commitsSkipped: store.commitsSkipped,
      coChangePairs: store.coChange.length,
      graphify: {
        enriched: store.graphify.enriched,
        version: store.graphify.version,
        skippedReason: store.graphify.skippedReason,
        nodes: store.graphify.nodes.length,
        edges: store.graphify.edges.length,
      },
    },
    null,
    2,
  );
}

export function formatCoChangeText(result: CoChangeQueryResult): string {
  const lines: string[] = [`Files that historically change alongside "${result.file}":`, ""];
  if (result.results.length === 0) {
    lines.push("  (no co-change data found for this file -- check the path, or run `graphkeeper build` first)");
  } else {
    for (const r of result.results) {
      lines.push(`  ${String(r.count).padStart(4)}  ${r.file}`);
    }
  }
  return lines.join("\n");
}

export function formatCoChangeJson(result: CoChangeQueryResult): string {
  return JSON.stringify(result, null, 2);
}

export function formatCallsText(result: CallsQueryResult): string {
  if (!result.available) {
    return [
      `Call-graph query for "${result.symbol}" is not available.`,
      "",
      result.unavailableReason ?? "graphify enrichment is required for this query type.",
    ].join("\n");
  }
  if (!result.node) {
    return `No symbol matching "${result.symbol}" was found in the graphify graph.`;
  }
  const lines: string[] = [`${result.node.label} (${result.node.source_file ?? "unknown location"})`, ""];
  lines.push(`Calls (${result.calls.length}):`);
  for (const c of result.calls) {
    lines.push(`  --> ${c.node?.label ?? c.edge.target}`);
  }
  lines.push("");
  lines.push(`Called by (${result.calledBy.length}):`);
  for (const c of result.calledBy) {
    lines.push(`  <-- ${c.node?.label ?? c.edge.source}`);
  }
  return lines.join("\n");
}

export function formatCallsJson(result: CallsQueryResult): string {
  return JSON.stringify(result, null, 2);
}
