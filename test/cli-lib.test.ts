import { describe, expect, it } from "vitest";
import {
  parsePositiveInt,
  formatBuildText,
  formatBuildJson,
  formatCoChangeText,
  formatCoChangeJson,
  formatCallsText,
  formatCallsJson,
} from "../src/cli-lib.js";
import type { BuildResult, CallsQueryResult, CoChangeQueryResult, GraphKeeperStore } from "../src/types.js";

describe("parsePositiveInt", () => {
  it("parses a valid positive integer", () => {
    expect(parsePositiveInt("42", "--limit")).toBe(42);
  });

  it("throws for zero", () => {
    expect(() => parsePositiveInt("0", "--limit")).toThrow(/Invalid --limit/);
  });

  it("throws for a negative number", () => {
    expect(() => parsePositiveInt("-5", "--limit")).toThrow(/Invalid --limit/);
  });

  it("throws for non-numeric input", () => {
    expect(() => parsePositiveInt("abc", "--limit")).toThrow(/Invalid --limit/);
  });
});

function makeStore(overrides: Partial<GraphKeeperStore> = {}): GraphKeeperStore {
  return {
    version: 1,
    generatedAt: "2026-01-01T00:00:00.000Z",
    repoPath: "/repo",
    commitsAnalyzed: 10,
    commitsSkipped: 0,
    coChange: [{ a: "a.ts", b: "b.ts", count: 3 }],
    fileCommitCounts: { "a.ts": 3 },
    graphify: { enriched: false, version: null, skippedReason: "graphify not installed", nodes: [], edges: [] },
    ...overrides,
  };
}

describe("formatBuildText / formatBuildJson", () => {
  it("mentions co-change stats and the skip reason when graphify wasn't enriched", () => {
    const result: BuildResult = { store: makeStore(), outputPath: "/repo/.graphkeeper/graph.json" };
    const text = formatBuildText(result);
    expect(text).toMatch(/10 commit/);
    expect(text).toMatch(/graphify enrichment: skipped/);
    expect(text).toMatch(/graphify not installed/);
  });

  it("reports enriched node/edge counts when graphify succeeded", () => {
    const result: BuildResult = {
      store: makeStore({
        graphify: {
          enriched: true,
          version: "0.9.16",
          skippedReason: null,
          nodes: [{ id: "n1", label: "a.ts" }],
          edges: [],
        },
      }),
      outputPath: "/repo/.graphkeeper/graph.json",
    };
    const text = formatBuildText(result);
    expect(text).toMatch(/graphify enrichment: included \(v0\.9\.16\)/);
    expect(text).toMatch(/1 node/);
  });

  it("emits valid, parseable JSON", () => {
    const result: BuildResult = { store: makeStore(), outputPath: "/repo/.graphkeeper/graph.json" };
    const parsed = JSON.parse(formatBuildJson(result));
    expect(parsed.commitsAnalyzed).toBe(10);
    expect(parsed.graphify.enriched).toBe(false);
  });
});

describe("formatCoChangeText / formatCoChangeJson", () => {
  it("lists ranked results", () => {
    const result: CoChangeQueryResult = { file: "a.ts", results: [{ file: "b.ts", count: 4 }] };
    expect(formatCoChangeText(result)).toMatch(/b\.ts/);
  });

  it("explains an empty result clearly instead of printing nothing", () => {
    const result: CoChangeQueryResult = { file: "a.ts", results: [] };
    expect(formatCoChangeText(result)).toMatch(/no co-change data found/);
  });

  it("emits valid JSON", () => {
    const result: CoChangeQueryResult = { file: "a.ts", results: [{ file: "b.ts", count: 4 }] };
    expect(JSON.parse(formatCoChangeJson(result))).toEqual(result);
  });
});

describe("formatCallsText / formatCallsJson", () => {
  it("explains unavailability instead of a silent empty result", () => {
    const result: CallsQueryResult = {
      symbol: "add",
      available: false,
      unavailableReason: "graphify enrichment is required for this query type.",
      node: null,
      calls: [],
      calledBy: [],
    };
    const text = formatCallsText(result);
    expect(text).toMatch(/not available/);
    expect(text).toMatch(/graphify enrichment is required/);
  });

  it("reports no match found when the symbol doesn't exist", () => {
    const result: CallsQueryResult = {
      symbol: "ghost",
      available: true,
      unavailableReason: null,
      node: null,
      calls: [],
      calledBy: [],
    };
    expect(formatCallsText(result)).toMatch(/No symbol matching "ghost"/);
  });

  it("lists callers and callees when found", () => {
    const result: CallsQueryResult = {
      symbol: "add",
      available: true,
      unavailableReason: null,
      node: { id: "src_a_add", label: "add()", source_file: "src/a.ts" },
      calls: [{ node: { id: "src_a_helper", label: "helper()" }, edge: { source: "src_a_add", target: "src_a_helper", relation: "calls" } }],
      calledBy: [{ node: { id: "src_b_sum3", label: "sum3()" }, edge: { source: "src_b_sum3", target: "src_a_add", relation: "calls" } }],
    };
    const text = formatCallsText(result);
    expect(text).toMatch(/add\(\)/);
    expect(text).toMatch(/--> helper\(\)/);
    expect(text).toMatch(/<-- sum3\(\)/);
  });

  it("falls back to the raw edge target/source when a node couldn't be resolved", () => {
    const result: CallsQueryResult = {
      symbol: "add",
      available: true,
      unavailableReason: null,
      node: { id: "src_a_add", label: "add()" },
      calls: [{ node: null, edge: { source: "src_a_add", target: "src_unresolved", relation: "calls" } }],
      calledBy: [],
    };
    const text = formatCallsText(result);
    expect(text).toMatch(/--> src_unresolved/);
  });

  it("emits valid JSON", () => {
    const result: CallsQueryResult = {
      symbol: "add",
      available: true,
      unavailableReason: null,
      node: null,
      calls: [],
      calledBy: [],
    };
    expect(JSON.parse(formatCallsJson(result))).toEqual(result);
  });
});
