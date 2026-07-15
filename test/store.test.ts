import { describe, expect, it, afterEach } from "vitest";
import { mkdtempSync, symlinkSync, existsSync, writeFileSync, realpathSync } from "node:fs";
import { tmpdir } from "node:os";
import * as path from "node:path";
import {
  resolveRepoRoot,
  assertPathInside,
  ensureGraphKeeperSubdir,
  writeStore,
  readStore,
  graphFilePath,
  PathSafetyError,
} from "../src/store.js";
import { cleanup } from "./test-helpers.js";
import type { GraphKeeperStore } from "../src/types.js";

const dirs: string[] = [];
function tempDir(): string {
  // realpath'd so comparisons match resolveRepoRoot's own realpath resolution
  // (macOS's os.tmpdir() lives under a /var -> /private/var symlink).
  const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "gk-store-test-")));
  dirs.push(dir);
  return dir;
}
afterEach(() => {
  while (dirs.length) cleanup(dirs.pop() as string);
});

function makeStore(repoPath: string): GraphKeeperStore {
  return {
    version: 1,
    generatedAt: new Date().toISOString(),
    repoPath,
    commitsAnalyzed: 1,
    commitsSkipped: 0,
    coChange: [{ a: "a.ts", b: "b.ts", count: 1 }],
    fileCommitCounts: { "a.ts": 1, "b.ts": 1 },
    graphify: { enriched: false, version: null, skippedReason: "test", nodes: [], edges: [] },
  };
}

describe("resolveRepoRoot", () => {
  it("resolves a valid directory to its real path", () => {
    const dir = tempDir();
    expect(resolveRepoRoot(dir)).toBe(dir);
  });

  it("throws PathSafetyError for a nonexistent path", () => {
    expect(() => resolveRepoRoot("/definitely/does/not/exist/xyz")).toThrow(PathSafetyError);
  });

  it("throws PathSafetyError when the path is a file, not a directory", () => {
    const dir = tempDir();
    const filePath = path.join(dir, "file.txt");
    writeFileSync(filePath, "hi");
    expect(() => resolveRepoRoot(filePath)).toThrow(PathSafetyError);
  });
});

describe("assertPathInside", () => {
  it("passes for a path nested under the parent", () => {
    const dir = tempDir();
    const child = path.join(dir, "sub", "deep");
    expect(() => assertPathInside(child, dir)).not.toThrow();
  });

  it("passes when child equals parent", () => {
    const dir = tempDir();
    expect(() => assertPathInside(dir, dir)).not.toThrow();
  });

  it("throws when a symlink escapes the parent directory", () => {
    const parent = tempDir();
    const outside = tempDir();
    const link = path.join(parent, "escape");
    symlinkSync(outside, link);
    expect(() => assertPathInside(link, parent)).toThrow(PathSafetyError);
  });
});

describe("ensureGraphKeeperSubdir", () => {
  it("creates .graphkeeper and nested subdirectories", () => {
    const repo = tempDir();
    const dir = ensureGraphKeeperSubdir(repo, "graphify-raw");
    expect(existsSync(dir)).toBe(true);
    expect(dir).toBe(path.join(repo, ".graphkeeper", "graphify-raw"));
  });

  it("refuses to use a pre-existing malicious .graphkeeper symlink", () => {
    const repo = tempDir();
    const outside = tempDir();
    symlinkSync(outside, path.join(repo, ".graphkeeper"));
    expect(() => ensureGraphKeeperSubdir(repo)).toThrow(PathSafetyError);
  });
});

describe("writeStore / readStore", () => {
  it("round-trips a store through disk", () => {
    const repo = tempDir();
    const store = makeStore(repo);
    const written = writeStore(repo, store);
    expect(written).toBe(graphFilePath(repo));
    const readBack = readStore(repo);
    expect(readBack.coChange).toEqual(store.coChange);
    expect(readBack.repoPath).toBe(repo);
  });

  it("readStore respects an explicit override path", () => {
    const repo = tempDir();
    const store = makeStore(repo);
    const customPath = path.join(repo, "custom.json");
    writeFileSync(customPath, JSON.stringify(store));
    const readBack = readStore(repo, customPath);
    expect(readBack.commitsAnalyzed).toBe(1);
  });

  it("throws PathSafetyError when no store exists yet", () => {
    const repo = tempDir();
    expect(() => readStore(repo)).toThrow(PathSafetyError);
  });
});
