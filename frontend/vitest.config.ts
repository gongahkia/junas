import { defineConfig } from "vitest/config";

export default defineConfig({
  oxc: {
    jsx: {
      runtime: "automatic",
      importSource: "react",
    },
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.tsx", "app/**/*.test.tsx"],
  },
});
