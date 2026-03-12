import { defineConfig, devices } from "@playwright/test";

const backendUrl = "http://127.0.0.1:8082";
const frontendUrl = "http://127.0.0.1:4173";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: frontendUrl,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
    {
      name: "iphone-13",
      use: {
        ...devices["iPhone 13"],
      },
    },
  ],
  webServer: [
    {
      command: "go run . serve",
      cwd: "../api",
      url: `${backendUrl}/api/readyz`,
      timeout: 120000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        KILTER_TOGETHER_ALLOWED_ORIGINS: frontendUrl,
        KILTER_TOGETHER_APP_DB_PATH: "/tmp/kilter-together-playwright-app.db",
        KILTER_TOGETHER_APP_SECRET: "playwright-secret",
        KILTER_TOGETHER_ENABLE_TEST_PROVIDER: "true",
        KILTER_TOGETHER_ENCRYPTION_KEY: "BQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU=",
        KILTER_TOGETHER_PORT: "8082",
        KILTER_TOGETHER_SECURE_COOKIES: "false",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4173",
      cwd: ".",
      url: frontendUrl,
      timeout: 120000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        VITE_API_BASE_URL: "/api",
        VITE_ENABLE_TEST_PROVIDER: "true",
      },
    },
  ],
});
