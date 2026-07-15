import { describe, expect, it } from "vitest";
import { queryCoChange, queryCalls, findGraphifyNode, normalizeFileArg } from "../src/query.js";
import type { GraphKeeperStore, GraphifyNode } from "../src/types.js";

function makeStore(overrides: Partial<GraphKeeperStore> = {}): GraphKeeperStore {
  return {
    version: 1,
    generatedAt: new Date().toISOString(),
    repoPath: "/repo",
    commitsAnalyzed: 3,
    commitsSkipped: 0,
    coChange: [
      { a: "src/a.ts", b: "src/b.ts", count: 5 },
      { a: "src/a.ts", b: "src/c.ts", count: 2 },
      { a: "src/x.ts", b: "src/y.ts", count: 9 },
    ],
    fileCommitCounts: { "src/a.ts": 5, "src/b.ts": 5, "src/c.ts": 2 },
    graphify: { enriched: false, version: null, skippedReason: null, nodes: [], edges: [] },
    ...overrides,
  };
}

describe("normalizeFileArg", () => {
  it("strips a leading ./", () => {
    expect(normalizeFileArg(makeStore(), "./src/a.ts")).toBe("src/a.ts");
  });

  it("relativizes an absolute path under repoPath", () => {
    expect(normalizeFileArg(makeStore({ repoPath: "/repo" }), "/repo/src/a.ts")).toBe("src/a.ts");
  });

  it("leaves an absolute path outside repoPath unchanged", () => {
    expect(normalizeFileArg(makeStore({ repoPath: "/repo" }), "/other/src/a.ts")).toBe("/other/src/a.ts");
  });
});

describe("queryCoChange", () => {
  it("finds co-change partners ranked by count", () => {
    const result = queryCoChange(makeStore(), "src/a.ts");
    expect(result.results).toEqual([
      { file: "src/b.ts", count: 5 },
      { file: "src/c.ts", count: 2 },
    ]);
  });

  it("matches the edge regardless of which side the file is stored on", () => {
    const result = queryCoChange(makeStore(), "src/y.ts");
    expect(result.results).toEqual([{ file: "src/x.ts", count: 9 }]);
  });

  it("returns an empty result for a file with no co-change history", () => {
    const result = queryCoChange(makeStore(), "src/never-changed.ts");
    expect(result.results).toEqual([]);
  });

  it("respects the limit option", () => {
    const result = queryCoChange(makeStore(), "src/a.ts", { limit: 1 });
    expect(result.results).toHaveLength(1);
    expect(result.results[0]?.file).toBe("src/b.ts");
  });
});

const nodes: GraphifyNode[] = [
  { id: "src_a_add", label: "add()", file_type: "code", source_file: "src/a.ts" },
  { id: "src_b_sum3", label: "sum3()", file_type: "code", source_file: "src/b.ts" },
  { id: "src_a", label: "a.ts", file_type: "code", source_file: "src/a.ts" },
];

describe("findGraphifyNode", () => {
  it("matches an exact label with parens", () => {
    expect(findGraphifyNode(nodes, "add()")?.id).toBe("src_a_add");
  });

  it("matches a bare symbol name without parens", () => {
    expect(findGraphifyNode(nodes, "add")?.id).toBe("src_a_add");
  });

  it("matches case-insensitively", () => {
    expect(findGraphifyNode(nodes, "ADD")?.id).toBe("src_a_add");
  });

  it("returns null when nothing matches", () => {
    expect(findGraphifyNode(nodes, "doesNotExist")).toBeNull();
  });
});

describe("queryCalls", () => {
  it("reports unavailable with the build's skip reason when graphify wasn't enriched", () => {
    const store = makeStore({
      graphify: { enriched: false, version: null, skippedReason: "graphify not installed", nodes: [], edges: [] },
    });
    const result = queryCalls(store, "add");
    expect(result.available).toBe(false);
    expect(result.unavailableReason).toBe("graphify not installed");
    expect(result.calls).toEqual([]);
  });

  it("returns node:null (not an error) when the symbol isn't found in an enriched build", () => {
    const store = makeStore({
      graphify: { enriched: true, version: "0.9.16", skippedReason: null, nodes, edges: [] },
    });
    const result = queryCalls(store, "nonexistentSymbol");
    expect(result.available).toBe(true);
    expect(result.node).toBeNull();
  });

  it("returns callers and callees for a found symbol", () => {
    const store = makeStore({
      graphify: {
        enriched: true,
        version: "0.9.16",
        skippedReason: null,
        nodes,
        edges: [
          { source: "src_b_sum3", target: "src_a_add", relation: "calls", confidence: "EXTRACTED" },
          { source: "src_a", target: "src_a_add", relation: "contains", confidence: "EXTRACTED" },
        ],
      },
    });
    const result = queryCalls(store, "add");
    expect(result.available).toBe(true);
    expect(result.node?.id).toBe("src_a_add");
    expect(result.calls).toEqual([]);
    expect(result.calledBy).toHaveLength(1);
    expect(result.calledBy[0]?.node?.id).toBe("src_b_sum3");
  });

  it("returns callees (calls) with a null node when the target isn't in the node set", () => {
    const store = makeStore({
      graphify: {
        enriched: true,
        version: "0.9.16",
        skippedReason: null,
        nodes,
        edges: [{ source: "src_a_add", target: "src_unresolved_helper", relation: "calls", confidence: "INFERRED" }],
      },
    });
    const result = queryCalls(store, "add");
    expect(result.calls).toHaveLength(1);
    expect(result.calls[0]?.node).toBeNull();
    expect(result.calls[0]?.edge.target).toBe("src_unresolved_helper");
  });
});
