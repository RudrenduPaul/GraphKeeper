import { describe, expect, it, afterEach } from "vitest";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import * as path from "node:path";
import { mineCoChange, unquoteGitPath, assertIsGitRepo, GitError } from "../src/git.js";
import { makeTempGitRepo, writeFile, commitAll, cleanup, run } from "./test-helpers.js";

const dirs: string[] = [];
function tempRepo(): string {
  const dir = makeTempGitRepo();
  dirs.push(dir);
  return dir;
}
afterEach(() => {
  while (dirs.length) cleanup(dirs.pop() as string);
});

describe("assertIsGitRepo", () => {
  it("does not throw for a real git repo", () => {
    const repo = tempRepo();
    expect(() => assertIsGitRepo(repo)).not.toThrow();
  });

  it("throws GitError for a non-repo directory", () => {
    const plain = mkdtempSync(path.join(tmpdir(), "gk-plain-"));
    dirs.push(plain);
    expect(() => assertIsGitRepo(plain)).toThrow(GitError);
  });
});

describe("unquoteGitPath", () => {
  it("returns plain paths unchanged", () => {
    expect(unquoteGitPath("src/index.ts")).toBe("src/index.ts");
  });

  it("unquotes a C-quoted path with an escaped quote", () => {
    expect(unquoteGitPath('"weird\\"file.ts"')).toBe('weird"file.ts');
  });

  it("unquotes octal escapes", () => {
    // \303\251 is UTF-8 for "é" when git quotes bytes individually.
    expect(unquoteGitPath('"caf\\303\\251.ts"')).toBe("café.ts");
  });

  it("unquotes \\n and \\t control-character escapes", () => {
    expect(unquoteGitPath('"line\\nbreak.ts"')).toBe("line\nbreak.ts");
    expect(unquoteGitPath('"tab\\tstop.ts"')).toBe("tab\tstop.ts");
  });

  it("passes an unrecognized escape's literal character through unchanged", () => {
    expect(unquoteGitPath('"weird\\qfile.ts"')).toBe("weirdqfile.ts");
  });

  it("keeps a trailing backslash with nothing after it", () => {
    expect(unquoteGitPath('"trailing\\"')).toBe("trailing\\");
  });
});

describe("mineCoChange error handling", () => {
  it("throws GitError when git log fails (e.g. repo has no commits yet)", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "gk-unborn-"));
    dirs.push(dir);
    run(dir, ["init", "-q"]);
    expect(() => mineCoChange(dir)).toThrow(GitError);
  });
});

describe("mineCoChange", () => {
  it("returns no data for a repo with a single empty commit", () => {
    const repo = tempRepo();
    const result = mineCoChange(repo);
    expect(result.coChange).toEqual([]);
    expect(result.commitsAnalyzed).toBe(0);
  });

  it("counts a pair of files that change together across multiple commits", () => {
    const repo = tempRepo();
    writeFile(repo, "a.ts", "1");
    writeFile(repo, "b.ts", "1");
    commitAll(repo, "add a and b");
    writeFile(repo, "a.ts", "2");
    writeFile(repo, "b.ts", "2");
    commitAll(repo, "touch a and b again");
    writeFile(repo, "c.ts", "1");
    commitAll(repo, "add c alone");

    const result = mineCoChange(repo);
    expect(result.commitsAnalyzed).toBe(3);
    const pair = result.coChange.find((e) => (e.a === "a.ts" && e.b === "b.ts") || (e.a === "b.ts" && e.b === "a.ts"));
    expect(pair?.count).toBe(2);
    // c.ts never co-occurred with anything.
    expect(result.coChange.some((e) => e.a === "c.ts" || e.b === "c.ts")).toBe(false);
    expect(result.fileCommitCounts["a.ts"]).toBe(2);
    expect(result.fileCommitCounts["c.ts"]).toBe(1);
  });

  it("skips commits touching more files than maxFilesPerCommit", () => {
    const repo = tempRepo();
    for (let i = 0; i < 5; i++) {
      writeFile(repo, `f${i}.ts`, "1");
    }
    commitAll(repo, "touch 5 files");

    const result = mineCoChange(repo, { maxFilesPerCommit: 3 });
    expect(result.commitsAnalyzed).toBe(0);
    expect(result.commitsSkipped).toBe(1);
    expect(result.coChange).toEqual([]);
  });

  it("excludes merge commits", () => {
    const repo = tempRepo();
    writeFile(repo, "main.ts", "1");
    commitAll(repo, "base");
    run(repo, ["checkout", "-q", "-b", "feature"]);
    writeFile(repo, "feature.ts", "1");
    commitAll(repo, "feature work");
    run(repo, ["checkout", "-q", "-"]);
    writeFile(repo, "other.ts", "1");
    commitAll(repo, "unrelated work on main");
    run(repo, ["merge", "-q", "--no-ff", "-m", "merge feature", "feature"]);

    const result = mineCoChange(repo);
    // 3 real commits (base, feature work, unrelated), merge commit excluded.
    expect(result.commitsAnalyzed).toBe(3);
  });

  it("sorts results by descending co-change count", () => {
    const repo = tempRepo();
    writeFile(repo, "x.ts", "1");
    writeFile(repo, "y.ts", "1");
    commitAll(repo, "x+y once");
    writeFile(repo, "x.ts", "2");
    writeFile(repo, "z.ts", "1");
    commitAll(repo, "x+z once");
    writeFile(repo, "x.ts", "3");
    writeFile(repo, "z.ts", "2");
    commitAll(repo, "x+z twice");

    const result = mineCoChange(repo);
    expect(result.coChange[0]?.count).toBeGreaterThanOrEqual(result.coChange[1]?.count ?? 0);
  });
});
