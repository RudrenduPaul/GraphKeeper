import { spawnSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import type { GraphifyEnrichment, GraphifyRawGraph } from "./types.js";
import { assertPathInside, ensureGraphKeeperSubdir, GRAPHIFY_RAW_DIR_NAME } from "./store.js";

const DEFAULT_TIMEOUT_MS = 5 * 60 * 1000;
const MAX_BUFFER_BYTES = 200 * 1024 * 1024;

/**
 * Detects whether graphify (https://github.com/Graphify-Labs/graphify, PyPI
 * package `graphifyy`) is installed and on PATH, by running `graphify
 * --version`. Uses an argv array (never a shell string) so this is safe even
 * on a system with an unusual PATH.
 */
export function detectGraphify(): { installed: boolean; version: string | null } {
  const result = spawnSync("graphify", ["--version"], { encoding: "utf-8", timeout: 10_000 });
  if (result.error || result.status !== 0) {
    return { installed: false, version: null };
  }
  const match = /graphify\s+([\w.-]+)/i.exec(result.stdout ?? "");
  return { installed: true, version: match ? (match[1] as string) : (result.stdout ?? "").trim() || "unknown" };
}

/**
 * Runs `graphify extract <repoRoot> --code-only --no-cluster --out <dir>`
 * (graphify's own headless, no-LLM, no-API-key CLI path for local AST-based
 * symbol/import/call-graph extraction) and merges its `graph.json` output
 * into a GraphifyEnrichment. Never throws: any failure is reported back via
 * `skippedReason` so `build` can proceed in co-change-only mode.
 *
 * `--out` is pointed at a directory inside the caller-managed `.graphkeeper/`
 * tree, so graphify's own output never lands outside it.
 */
export function runGraphifyEnrichment(repoRoot: string): GraphifyEnrichment {
  const detected = detectGraphify();
  if (!detected.installed) {
    return {
      enriched: false,
      version: null,
      skippedReason:
        "graphify was not found on PATH. Install it with `uv tool install graphifyy` (or `pipx install graphifyy`) " +
        "for symbol/call-graph enrichment; GraphKeeper works fine without it, in co-change-only mode.",
      nodes: [],
      edges: [],
    };
  }

  let rawDir: string;
  try {
    rawDir = ensureGraphKeeperSubdir(repoRoot, GRAPHIFY_RAW_DIR_NAME);
  } catch (err) {
    return {
      enriched: false,
      version: detected.version,
      skippedReason: `Could not prepare a safe output directory for graphify: ${(err as Error).message}`,
      nodes: [],
      edges: [],
    };
  }

  const extractResult = spawnSync(
    "graphify",
    ["extract", repoRoot, "--code-only", "--no-cluster", "--out", rawDir],
    {
      cwd: repoRoot,
      encoding: "utf-8",
      timeout: DEFAULT_TIMEOUT_MS,
      maxBuffer: MAX_BUFFER_BYTES,
    },
  );

  if (extractResult.error) {
    return {
      enriched: false,
      version: detected.version,
      skippedReason: `graphify extract failed to run: ${extractResult.error.message}`,
      nodes: [],
      edges: [],
    };
  }
  if (extractResult.status !== 0) {
    const stderrTail = (extractResult.stderr ?? "").trim().split("\n").slice(-3).join(" ");
    return {
      enriched: false,
      version: detected.version,
      skippedReason: `graphify extract exited with status ${extractResult.status}${stderrTail ? `: ${stderrTail}` : ""}`,
      nodes: [],
      edges: [],
    };
  }

  const graphJsonPath = path.join(rawDir, "graphify-out", "graph.json");
  try {
    assertPathInside(graphJsonPath, repoRoot);
  } catch (err) {
    return {
      enriched: false,
      version: detected.version,
      skippedReason: `graphify's output path failed a safety check: ${(err as Error).message}`,
      nodes: [],
      edges: [],
    };
  }

  if (!fs.existsSync(graphJsonPath)) {
    return {
      enriched: false,
      version: detected.version,
      skippedReason: `graphify extract completed but did not produce a graph.json at "${graphJsonPath}".`,
      nodes: [],
      edges: [],
    };
  }

  let parsed: GraphifyRawGraph;
  try {
    const raw = fs.readFileSync(graphJsonPath, "utf-8");
    parsed = JSON.parse(raw) as GraphifyRawGraph;
  } catch (err) {
    return {
      enriched: false,
      version: detected.version,
      skippedReason: `Could not parse graphify's graph.json: ${(err as Error).message}`,
      nodes: [],
      edges: [],
    };
  }

  if (!Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) {
    return {
      enriched: false,
      version: detected.version,
      skippedReason: `graphify's graph.json did not have the expected {nodes, edges} shape.`,
      nodes: [],
      edges: [],
    };
  }

  // graphify reports `source_file` relative to its own --out directory, not
  // the scanned target. Because that --out directory lives nested inside
  // .graphkeeper/ (so graphify's own output never escapes it, per this
  // project's path-safety guard), those paths come back as "../../src/a.ts"
  // instead of "src/a.ts". Rewrite them relative to repoRoot so they line up
  // with the co-change paths GraphKeeper mines from git log.
  function rewriteSourceFile<T extends { source_file?: string }>(item: T): T {
    if (!item.source_file) return item;
    const rewritten = path.relative(repoRoot, path.resolve(rawDir, item.source_file)).split(path.sep).join("/");
    return { ...item, source_file: rewritten };
  }

  return {
    enriched: true,
    version: detected.version,
    skippedReason: null,
    nodes: parsed.nodes.map(rewriteSourceFile),
    edges: parsed.edges.map(rewriteSourceFile),
  };
}
