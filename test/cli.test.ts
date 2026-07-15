import { describe, expect, it, afterEach } from "vitest";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { makeTempGitRepo, writeFile, commitAll, cleanup } from "./test-helpers.js";

const CLI = resolve(__dirname, "..", "dist", "cli.js");

function runCli(args: string[], cwd?: string): { stdout: string; stderr: string; status: number } {
  try {
    const stdout = execFileSync("node", [CLI, ...args], { encoding: "utf-8", cwd });
    return { stdout, stderr: "", status: 0 };
  } catch (err) {
    const e = err as { stdout?: string; stderr?: string; status?: number };
    return { stdout: e.stdout ?? "", stderr: e.stderr ?? "", status: e.status ?? 2 };
  }
}

const dirs: string[] = [];
function tempRepo(): string {
  const dir = makeTempGitRepo();
  dirs.push(dir);
  return dir;
}
afterEach(() => {
  while (dirs.length) cleanup(dirs.pop() as string);
});

describe("CLI", () => {
  it("prints help output listing the build and query subcommands", () => {
    const { stdout, status } = runCli(["--help"]);
    expect(status).toBe(0);
    expect(stdout).toMatch(/build/);
    expect(stdout).toMatch(/query/);
    expect(stdout).toMatch(/graphkeeper/);
  });

  it("prints the version", () => {
    const { stdout, status } = runCli(["--version"]);
    expect(status).toBe(0);
    expect(stdout.trim()).toBe("0.1.0");
  });

  it("exits 2 with a clear error on a nonexistent path", () => {
    const { stdout, stderr, status } = runCli(["build", "/definitely/not/a/real/path/xyz"]);
    expect(status).toBe(2);
    expect(stdout).toBe("");
    expect(stderr).toMatch(/does not exist/);
  });

  it("exits 2 with a clear error when the target is not a git repo", () => {
    const dir = tempRepo();
    cleanup(dir);
    dirs.pop();
    // Recreate as a plain (non-git) directory.
    mkdirSync(dir, { recursive: true });
    dirs.push(dir);
    const { status, stderr } = runCli(["build", dir]);
    expect(status).toBe(2);
    expect(stderr).toMatch(/not a git repository/);
  });

  it("builds a real repo end-to-end and reports co-change + skipped graphify enrichment", () => {
    const repo = tempRepo();
    writeFile(repo, "a.ts", "1");
    writeFile(repo, "b.ts", "1");
    commitAll(repo, "add a and b");

    const { stdout, status } = runCli(["build", repo, "--no-graphify", "--json"], repo);
    expect(status).toBe(0);
    const parsed = JSON.parse(stdout);
    expect(parsed.commitsAnalyzed).toBeGreaterThan(0);
    expect(parsed.graphify.enriched).toBe(false);
  });

  it("queries co-change after a build and exits 0 with results", () => {
    const repo = tempRepo();
    writeFile(repo, "a.ts", "1");
    writeFile(repo, "b.ts", "1");
    commitAll(repo, "add a and b");
    runCli(["build", repo, "--no-graphify"], repo);

    const { stdout, status } = runCli(["query", "co-change", "a.ts", "--json"], repo);
    expect(status).toBe(0);
    const parsed = JSON.parse(stdout);
    expect(parsed.results[0].file).toBe("b.ts");
  });

  it("queries calls without enrichment and exits 1 with a clear explanation, not a crash", () => {
    const repo = tempRepo();
    writeFile(repo, "a.ts", "1");
    commitAll(repo, "add a");
    runCli(["build", repo, "--no-graphify"], repo);

    const { stdout, status } = runCli(["query", "calls", "someSymbol", "--json"], repo);
    expect(status).toBe(1);
    const parsed = JSON.parse(stdout);
    expect(parsed.available).toBe(false);
    expect(parsed.unavailableReason).toBeTruthy();
  });

  it("exits 2 with a clear error when no graph exists yet", () => {
    const repo = tempRepo();
    const { status, stderr } = runCli(["query", "co-change", "a.ts"], repo);
    expect(status).toBe(2);
    expect(stderr).toMatch(/Run "graphkeeper build" first/);
  });
});
