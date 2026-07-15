import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    testTimeout: 20000,
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.ts"],
      // cli.ts is a thin process.exit()-driven entry point exercised via the
      // subprocess-based integration tests in test/cli.test.ts, not unit
      // coverage; its actual logic lives in cli-lib.ts, which is covered.
      exclude: ["src/cli.ts"],
      thresholds: {
        lines: 80,
        statements: 80,
        functions: 80,
        branches: 75,
      },
    },
  },
});
