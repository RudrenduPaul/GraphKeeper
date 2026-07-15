import { spawnSync } from "node:child_process";
import type { CoChangeEdge } from "./types.js";

/** Marker used to split `git log` output into per-commit chunks. Chosen to be
 * extremely unlikely to appear in a commit message or file path. */
const COMMIT_MARKER = "@@GK-COMMIT@@";

const DEFAULT_MAX_FILES_PER_COMMIT = 100;
/** 200 MiB is generous headroom for even very large monorepo histories. */
const MAX_BUFFER_BYTES = 200 * 1024 * 1024;

export class GitError extends Error {}

/**
 * Runs `git` with an argv array (never a shell string), so untrusted repo
 * paths or file contents can never be interpreted as shell syntax.
 */
function runGit(repoPath: string, args: string[]): { stdout: string; status: number | null; stderr: string } {
  const result = spawnSync("git", ["-C", repoPath, ...args], {
    encoding: "utf-8",
    maxBuffer: MAX_BUFFER_BYTES,
  });
  if (result.error) {
    if ((result.error as NodeJS.ErrnoException).code === "ENOENT") {
      throw new GitError("git is not installed or not on PATH.");
    }
    throw new GitError(`Failed to run git: ${result.error.message}`);
  }
  return { stdout: result.stdout ?? "", status: result.status, stderr: result.stderr ?? "" };
}

/** Throws GitError if `repoPath` is not inside a git working tree. */
export function assertIsGitRepo(repoPath: string): void {
  const { status, stderr } = runGit(repoPath, ["rev-parse", "--is-inside-work-tree"]);
  if (status !== 0) {
    throw new GitError(`"${repoPath}" is not a git repository. ${stderr.trim()}`.trim());
  }
}

/**
 * Unquotes a git `--name-only` path entry. Git C-quotes paths containing
 * unusual bytes (non-ASCII when core.quotePath is on, quotes, backslashes,
 * control characters) by wrapping them in double quotes with backslash/octal
 * escapes. Plain paths are returned unchanged.
 */
export function unquoteGitPath(raw: string): string {
  if (raw.length < 2 || raw[0] !== '"' || raw[raw.length - 1] !== '"') {
    return raw;
  }
  const inner = raw.slice(1, -1);
  // Octal escapes are individual *bytes* of a (possibly multi-byte UTF-8)
  // sequence, so this must accumulate raw bytes and UTF-8-decode once at the
  // end -- decoding each escaped byte with String.fromCharCode individually
  // would mangle any non-ASCII character spanning more than one byte.
  const bytes: number[] = [];
  for (let i = 0; i < inner.length; i++) {
    const ch = inner[i] as string;
    if (ch !== "\\") {
      // core.quotePath=true escapes every byte >= 0x80, so an unescaped
      // character here is always plain ASCII (single byte, no surrogate
      // pairs to worry about).
      bytes.push(ch.charCodeAt(0));
      continue;
    }
    const next = inner[i + 1];
    if (next === undefined) {
      bytes.push(ch.charCodeAt(0));
      continue;
    }
    if (next >= "0" && next <= "7") {
      const octal = inner.slice(i + 1, i + 4);
      const code = Number.parseInt(octal, 8);
      bytes.push(Number.isFinite(code) ? code : next.charCodeAt(0));
      i += 3;
      continue;
    }
    switch (next) {
      case "n":
        bytes.push(0x0a);
        break;
      case "t":
        bytes.push(0x09);
        break;
      case "\\":
        bytes.push(0x5c);
        break;
      case '"':
        bytes.push(0x22);
        break;
      default:
        bytes.push(next.charCodeAt(0));
    }
    i += 1;
  }
  return Buffer.from(bytes).toString("utf-8");
}

/** True if every character code in `p` is non-zero (i.e. no embedded NUL bytes). */
function hasNoNulByte(p: string): boolean {
  for (let i = 0; i < p.length; i++) {
    if (p.charCodeAt(i) === 0) return false;
  }
  return true;
}

/** Rejects path entries that could escape the repo tree or aren't real tracked files. */
function isSafeTrackedPath(p: string): boolean {
  if (!p) return false;
  if (!hasNoNulByte(p)) return false;
  if (p.startsWith("/") || p.startsWith("~")) return false;
  const segments = p.split("/");
  if (segments.some((s) => s === "..")) return false;
  return true;
}

export interface CoChangeMiningResult {
  coChange: CoChangeEdge[];
  fileCommitCounts: Record<string, number>;
  commitsAnalyzed: number;
  commitsSkipped: number;
}

/**
 * Mines `git log` history for file-level co-change: pairs of files that were
 * modified together in the same commit. This is GraphKeeper's own signal,
 * distinct from (and complementary to) symbol/call-graph extraction.
 */
export function mineCoChange(repoPath: string, options: { maxFilesPerCommit?: number } = {}): CoChangeMiningResult {
  const maxFilesPerCommit = options.maxFilesPerCommit ?? DEFAULT_MAX_FILES_PER_COMMIT;
  assertIsGitRepo(repoPath);

  const { stdout, status, stderr } = runGit(repoPath, [
    "-c",
    "core.quotePath=true",
    "log",
    "--no-merges",
    `--pretty=format:${COMMIT_MARKER}%H`,
    "--name-only",
  ]);
  if (status !== 0) {
    throw new GitError(`git log failed: ${stderr.trim()}`);
  }

  // Keyed by JSON.stringify([a, b]) so the key is unambiguous regardless of
  // what characters the file paths themselves contain.
  const pairCounts = new Map<string, { a: string; b: string; count: number }>();
  const fileCommitCounts = new Map<string, number>();
  let commitsAnalyzed = 0;
  let commitsSkipped = 0;

  if (stdout.trim().length === 0) {
    return { coChange: [], fileCommitCounts: {}, commitsAnalyzed: 0, commitsSkipped: 0 };
  }

  const chunks = stdout.split(COMMIT_MARKER).slice(1);
  for (const chunk of chunks) {
    const newlineIndex = chunk.indexOf("\n");
    const filesRaw = newlineIndex === -1 ? "" : chunk.slice(newlineIndex + 1);
    const files = Array.from(
      new Set(
        filesRaw
          .split("\n")
          .map((line) => line.trim())
          .filter((line) => line.length > 0)
          .map(unquoteGitPath)
          .filter(isSafeTrackedPath),
      ),
    ).sort();

    if (files.length === 0) {
      continue;
    }
    if (files.length > maxFilesPerCommit) {
      commitsSkipped += 1;
      continue;
    }

    commitsAnalyzed += 1;
    for (const f of files) {
      fileCommitCounts.set(f, (fileCommitCounts.get(f) ?? 0) + 1);
    }
    for (let i = 0; i < files.length; i++) {
      for (let j = i + 1; j < files.length; j++) {
        const a = files[i] as string;
        const b = files[j] as string;
        const key = JSON.stringify([a, b]);
        const existing = pairCounts.get(key);
        if (existing) {
          existing.count += 1;
        } else {
          pairCounts.set(key, { a, b, count: 1 });
        }
      }
    }
  }

  const coChange: CoChangeEdge[] = Array.from(pairCounts.values(), ({ a, b, count }) => ({ a, b, count }));
  coChange.sort((x, y) => y.count - x.count);

  return {
    coChange,
    fileCommitCounts: Object.fromEntries(fileCommitCounts),
    commitsAnalyzed,
    commitsSkipped,
  };
}
