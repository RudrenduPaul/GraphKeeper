import { mkdtempSync, writeFileSync, mkdirSync, rmSync, realpathSync } from "node:fs";
import { tmpdir } from "node:os";
import * as path from "node:path";
import { spawnSync } from "node:child_process";

/** Creates a throwaway git repo with an initial commit, for tests. Caller must clean up.
 *
 * Returns the *realpath* of the temp dir: on macOS, `os.tmpdir()` lives under
 * `/var`, which is itself a symlink to `/private/var`. GraphKeeper's own
 * `resolveRepoRoot` follows symlinks (by design, for path-traversal safety),
 * so tests must compare against the same realpath'd form or every equality
 * assertion on a returned repo path spuriously fails on macOS.
 */
export function makeTempGitRepo(): string {
  const dir = realpathSync(mkdtempSync(path.join(tmpdir(), "graphkeeper-test-")));
  run(dir, ["init", "-q"]);
  run(dir, ["-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "--allow-empty", "-q", "-m", "init"]);
  return dir;
}

export function run(repoDir: string, args: string[]): void {
  const result = spawnSync("git", ["-C", repoDir, ...args], { encoding: "utf-8" });
  if (result.status !== 0) {
    throw new Error(`git ${args.join(" ")} failed: ${result.stderr}`);
  }
}

export function writeFile(repoDir: string, relPath: string, content: string): void {
  const full = path.join(repoDir, relPath);
  mkdirSync(path.dirname(full), { recursive: true });
  writeFileSync(full, content, "utf-8");
}

export function commitAll(repoDir: string, message: string): void {
  run(repoDir, ["add", "-A"]);
  run(repoDir, ["-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-q", "-m", message]);
}

export function cleanup(dir: string): void {
  rmSync(dir, { recursive: true, force: true });
}
