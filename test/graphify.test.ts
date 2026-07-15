import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { mkdtempSync, writeFileSync, mkdirSync, symlinkSync, realpathSync } from "node:fs";
import { tmpdir } from "node:os";
import * as path from "node:path";
import { cleanup } from "./test-helpers.js";

const spawnSyncMock = vi.fn();
vi.mock("node:child_process", () => ({
  spawnSync: (...args: unknown[]) => spawnSyncMock(...args),
}));

// Imported after the mock so graphify.ts picks up the mocked spawnSync.
const { detectGraphify, runGraphifyEnrichment } = await import("../src/graphify.js");

const dirs: string[] = [];
function tempRepo(): string {
  const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "gk-graphify-test-")));
  dirs.push(dir);
  return dir;
}

beforeEach(() => {
  spawnSyncMock.mockReset();
});
afterEach(() => {
  while (dirs.length) cleanup(dirs.pop() as string);
});

describe("detectGraphify", () => {
  it("reports installed with a parsed version when graphify --version succeeds", () => {
    spawnSyncMock.mockReturnValue({ status: 0, stdout: "graphify 0.9.16\n", stderr: "", error: undefined });
    const result = detectGraphify();
    expect(result).toEqual({ installed: true, version: "0.9.16" });
  });

  it("reports not installed when the binary is missing (ENOENT)", () => {
    spawnSyncMock.mockReturnValue({ status: null, stdout: "", stderr: "", error: { code: "ENOENT" } });
    const result = detectGraphify();
    expect(result).toEqual({ installed: false, version: null });
  });

  it("reports not installed when the command exits non-zero", () => {
    spawnSyncMock.mockReturnValue({ status: 1, stdout: "", stderr: "boom", error: undefined });
    const result = detectGraphify();
    expect(result.installed).toBe(false);
  });
});

describe("runGraphifyEnrichment", () => {
  it("skips gracefully with a clear reason when graphify is not installed", () => {
    spawnSyncMock.mockReturnValue({ status: null, stdout: "", stderr: "", error: { code: "ENOENT" } });
    const repo = tempRepo();
    const result = runGraphifyEnrichment(repo);
    expect(result.enriched).toBe(false);
    expect(result.skippedReason).toMatch(/not found on PATH/);
    expect(result.nodes).toEqual([]);
  });

  it("skips gracefully when graphify extract exits non-zero", () => {
    const repo = tempRepo();
    spawnSyncMock.mockImplementation((cmd: string, args: string[]) => {
      if (args[0] === "--version") {
        return { status: 0, stdout: "graphify 0.9.16\n", stderr: "", error: undefined };
      }
      return { status: 1, stdout: "", stderr: "error: path not found\n", error: undefined };
    });
    const result = runGraphifyEnrichment(repo);
    expect(result.enriched).toBe(false);
    expect(result.skippedReason).toMatch(/exited with status 1/);
  });

  it("merges nodes/edges when extraction succeeds and writes a valid graph.json", () => {
    const repo = tempRepo();
    spawnSyncMock.mockImplementation((cmd: string, args: string[]) => {
      if (args[0] === "--version") {
        return { status: 0, stdout: "graphify 0.9.16\n", stderr: "", error: undefined };
      }
      // args: ["extract", repoRoot, "--code-only", "--no-cluster", "--out", rawDir]
      const outIdx = args.indexOf("--out");
      const rawDir = args[outIdx + 1] as string;
      const graphOutDir = path.join(rawDir, "graphify-out");
      mkdirSync(graphOutDir, { recursive: true });
      writeFileSync(
        path.join(graphOutDir, "graph.json"),
        JSON.stringify({
          nodes: [{ id: "src_a", label: "a.ts", file_type: "code" }],
          edges: [{ source: "src_a", target: "src_a", relation: "contains", confidence: "EXTRACTED" }],
        }),
      );
      return { status: 0, stdout: "wrote graph.json", stderr: "", error: undefined };
    });

    const result = runGraphifyEnrichment(repo);
    expect(result.enriched).toBe(true);
    expect(result.version).toBe("0.9.16");
    expect(result.nodes).toHaveLength(1);
    expect(result.edges).toHaveLength(1);
  });

  it("rewrites source_file from relative-to-output-dir to relative-to-repo-root", () => {
    const repo = tempRepo();
    spawnSyncMock.mockImplementation((cmd: string, args: string[]) => {
      if (args[0] === "--version") {
        return { status: 0, stdout: "graphify 0.9.16\n", stderr: "", error: undefined };
      }
      const outIdx = args.indexOf("--out");
      const rawDir = args[outIdx + 1] as string;
      const graphOutDir = path.join(rawDir, "graphify-out");
      mkdirSync(graphOutDir, { recursive: true });
      // graphify reports source_file relative to its own --out dir, which
      // here is nested two levels inside the repo (.graphkeeper/graphify-raw).
      writeFileSync(
        path.join(graphOutDir, "graph.json"),
        JSON.stringify({
          nodes: [{ id: "src_a", label: "a.ts", source_file: "../../src/a.ts" }],
          edges: [{ source: "src_a", target: "src_a", relation: "contains", source_file: "../../src/a.ts" }],
        }),
      );
      return { status: 0, stdout: "", stderr: "", error: undefined };
    });

    const result = runGraphifyEnrichment(repo);
    expect(result.nodes[0]?.source_file).toBe("src/a.ts");
    expect(result.edges[0]?.source_file).toBe("src/a.ts");
  });

  it("skips gracefully when graph.json is malformed JSON", () => {
    const repo = tempRepo();
    spawnSyncMock.mockImplementation((cmd: string, args: string[]) => {
      if (args[0] === "--version") {
        return { status: 0, stdout: "graphify 0.9.16\n", stderr: "", error: undefined };
      }
      const outIdx = args.indexOf("--out");
      const rawDir = args[outIdx + 1] as string;
      const graphOutDir = path.join(rawDir, "graphify-out");
      mkdirSync(graphOutDir, { recursive: true });
      writeFileSync(path.join(graphOutDir, "graph.json"), "{ not valid json");
      return { status: 0, stdout: "", stderr: "", error: undefined };
    });

    const result = runGraphifyEnrichment(repo);
    expect(result.enriched).toBe(false);
    expect(result.skippedReason).toMatch(/Could not parse/);
  });

  it("skips gracefully when spawning `graphify extract` itself errors (e.g. ENOENT mid-run)", () => {
    const repo = tempRepo();
    spawnSyncMock.mockImplementation((cmd: string, args: string[]) => {
      if (args[0] === "--version") {
        return { status: 0, stdout: "graphify 0.9.16\n", stderr: "", error: undefined };
      }
      return { status: null, stdout: "", stderr: "", error: new Error("spawn graphify ENOENT") };
    });

    const result = runGraphifyEnrichment(repo);
    expect(result.enriched).toBe(false);
    expect(result.skippedReason).toMatch(/graphify extract failed to run/);
  });

  it("skips gracefully when graphify extract succeeds but writes no graph.json", () => {
    const repo = tempRepo();
    spawnSyncMock.mockImplementation((cmd: string, args: string[]) => {
      if (args[0] === "--version") {
        return { status: 0, stdout: "graphify 0.9.16\n", stderr: "", error: undefined };
      }
      // Reports success but (unrealistically) writes nothing.
      return { status: 0, stdout: "", stderr: "", error: undefined };
    });

    const result = runGraphifyEnrichment(repo);
    expect(result.enriched).toBe(false);
    expect(result.skippedReason).toMatch(/did not produce a graph\.json/);
  });

  it("skips gracefully when graph.json has an unexpected shape", () => {
    const repo = tempRepo();
    spawnSyncMock.mockImplementation((cmd: string, args: string[]) => {
      if (args[0] === "--version") {
        return { status: 0, stdout: "graphify 0.9.16\n", stderr: "", error: undefined };
      }
      const outIdx = args.indexOf("--out");
      const rawDir = args[outIdx + 1] as string;
      const graphOutDir = path.join(rawDir, "graphify-out");
      mkdirSync(graphOutDir, { recursive: true });
      writeFileSync(path.join(graphOutDir, "graph.json"), JSON.stringify({ nodes: "not-an-array" }));
      return { status: 0, stdout: "", stderr: "", error: undefined };
    });

    const result = runGraphifyEnrichment(repo);
    expect(result.enriched).toBe(false);
    expect(result.skippedReason).toMatch(/did not have the expected/);
  });

  it("skips gracefully when .graphkeeper is a pre-existing symlink escaping the repo", () => {
    const repo = tempRepo();
    const outside = tempRepo();
    symlinkSync(outside, path.join(repo, ".graphkeeper"));
    spawnSyncMock.mockReturnValue({ status: 0, stdout: "graphify 0.9.16\n", stderr: "", error: undefined });

    const result = runGraphifyEnrichment(repo);
    expect(result.enriched).toBe(false);
    expect(result.skippedReason).toMatch(/Could not prepare a safe output directory/);
  });
});
