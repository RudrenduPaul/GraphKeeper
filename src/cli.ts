#!/usr/bin/env node
import { Command } from "commander";
import { build } from "./build.js";
import { queryCoChange, queryCalls } from "./query.js";
import { readStore, resolveRepoRoot, PathSafetyError } from "./store.js";
import { GitError } from "./git.js";
import {
  formatBuildText,
  formatBuildJson,
  formatCoChangeText,
  formatCoChangeJson,
  formatCallsText,
  formatCallsJson,
  parsePositiveInt,
} from "./cli-lib.js";

const VERSION = "0.1.0";

const program = new Command();

program
  .name("graphkeeper")
  .description(
    "Local-only CLI that mines git history for file-level co-change patterns and builds a queryable " +
      "knowledge graph for AI coding agents, with optional enrichment from graphify's symbol/call-graph " +
      "output when it is installed.",
  )
  .version(VERSION);

program
  .command("build")
  .description("Mine git history for co-change and (if available) merge in graphify's symbol/call graph")
  .argument("[path]", "path to the target repo", ".")
  .option("--json", "emit machine-readable JSON instead of human-readable text")
  .option("--max-files-per-commit <n>", "skip commits touching more than this many files (default: 100)")
  .option("--no-graphify", "skip graphify enrichment even if graphify is installed")
  .action((targetPath: string, opts: { json?: boolean; maxFilesPerCommit?: string; graphify: boolean }) => {
    try {
      const maxFilesPerCommit = opts.maxFilesPerCommit
        ? parsePositiveInt(opts.maxFilesPerCommit, "--max-files-per-commit")
        : undefined;
      const result = build(targetPath, {
        ...(maxFilesPerCommit !== undefined ? { maxFilesPerCommit } : {}),
        skipGraphify: opts.graphify === false,
      });
      console.log(opts.json ? formatBuildJson(result) : formatBuildText(result));
      process.exit(0);
    } catch (err) {
      reportError(err, Boolean(opts.json));
    }
  });

const query = program.command("query").description("Query the GraphKeeper store built by `graphkeeper build`");

query
  .command("co-change")
  .description("List files that historically change alongside <file>, ranked by co-change frequency")
  .argument("<file>", "repo-relative file path, e.g. src/index.ts")
  .option("--json", "emit machine-readable JSON instead of human-readable text")
  .option("--limit <n>", "cap the number of results")
  .option("--graph <path>", "path to a specific graph.json (default: <cwd>/.graphkeeper/graph.json)")
  .action((file: string, opts: { json?: boolean; limit?: string; graph?: string }) => {
    try {
      const limit = opts.limit ? parsePositiveInt(opts.limit, "--limit") : undefined;
      const repoRoot = resolveRepoRoot(process.cwd());
      const store = readStore(repoRoot, opts.graph);
      const result = queryCoChange(store, file, limit !== undefined ? { limit } : {});
      console.log(opts.json ? formatCoChangeJson(result) : formatCoChangeText(result));
      process.exit(result.results.length > 0 ? 0 : 1);
    } catch (err) {
      reportError(err, Boolean(opts.json));
    }
  });

query
  .command("calls")
  .description("Show callers/callees of <symbol> (requires graphify enrichment from `graphkeeper build`)")
  .argument("<symbol>", "symbol name, e.g. parseConfig")
  .option("--json", "emit machine-readable JSON instead of human-readable text")
  .option("--graph <path>", "path to a specific graph.json (default: <cwd>/.graphkeeper/graph.json)")
  .action((symbol: string, opts: { json?: boolean; graph?: string }) => {
    try {
      const repoRoot = resolveRepoRoot(process.cwd());
      const store = readStore(repoRoot, opts.graph);
      const result = queryCalls(store, symbol);
      console.log(opts.json ? formatCallsJson(result) : formatCallsText(result));
      process.exit(result.available && result.node ? 0 : 1);
    } catch (err) {
      reportError(err, Boolean(opts.json));
    }
  });

function reportError(err: unknown, json: boolean): never {
  const message = err instanceof GitError || err instanceof PathSafetyError || err instanceof Error ? err.message : String(err);
  if (json) {
    console.error(JSON.stringify({ error: message }, null, 2));
  } else {
    console.error(`Error: ${message}`);
  }
  process.exit(2);
}

program.parseAsync(process.argv);
