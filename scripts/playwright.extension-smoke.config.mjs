import { defineConfig } from "playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "extension-smoke.spec.mjs",
  fullyParallel: false,
  workers: 1,
  timeout: 8 * 60 * 1000,
  reporter: "list",
  use: {
    trace: "off",
    screenshot: "only-on-failure",
    video: "off",
  },
});
