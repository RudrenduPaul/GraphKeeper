import { describe, expect, it, afterEach } from "vitest";
import { existsSync } from "node:fs";
import { build } from "../src/build.js";
import { graphFilePath, readStore } from "../src/store.js";
import { makeTempGitRepo, writeFile, commitAll, cleanup } from "./test-helpers.js";

const dirs: string[] = [];
function tempRepo(): string {
  const dir = makeTempGitRepo();
  dirs.push(dir);
  return dir;
}
afterEach(() => {
  while (dirs.length) cleanup(dirs.pop() as string);
});

describe("build", () => {
  it("mines co-change and writes a store to .graphkeeper/graph.json", () => {
    const repo = tempRepo();
    writeFile(repo, "a.ts", "1");
    writeFile(repo, "b.ts", "1");
    commitAll(repo, "add a and b together");

    const result = build(repo, { skipGraphify: true });

    expect(result.outputPath).toBe(graphFilePath(repo));
    expect(existsSync(result.outputPath)).toBe(true);
    expect(result.store.commitsAnalyzed).toBeGreaterThan(0);
    expect(result.store.coChange.some((e) => (e.a === "a.ts" && e.b === "b.ts") || (e.a === "b.ts" && e.b === "a.ts"))).toBe(
      true,
    );
    expect(result.store.graphify.enriched).toBe(false);
    expect(result.store.graphify.skippedReason).toMatch(/--no-graphify/);
  });

  it("persists a store that can be read back with readStore", () => {
    const repo = tempRepo();
    writeFile(repo, "x.ts", "1");
    commitAll(repo, "add x");
    build(repo, { skipGraphify: true });

    const readBack = readStore(repo);
    expect(readBack.version).toBe(1);
    expect(readBack.repoPath).toBe(repo);
  });

  it("honors maxFilesPerCommit", () => {
    const repo = tempRepo();
    for (let i = 0; i < 10; i++) {
      writeFile(repo, `f${i}.ts`, "1");
    }
    commitAll(repo, "touch 10 files");

    const result = build(repo, { skipGraphify: true, maxFilesPerCommit: 5 });
    expect(result.store.commitsSkipped).toBe(1);
    expect(result.store.coChange).toEqual([]);
  });
});
