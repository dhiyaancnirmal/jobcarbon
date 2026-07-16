import { defineConfig } from "vitest/config";
import { cloudflareTest } from "@cloudflare/vitest-pool-workers";

// In `@cloudflare/vitest-pool-workers@0.18.x` the `defineWorkersConfig` helper
// was removed in favor of a `cloudflareTest(...)` Vite plugin. See:
// https://github.com/cloudflare/workers-sdk/tree/main/packages/vitest-pool-workers
export default defineConfig({
  plugins: [
    cloudflareTest({
      // Dedicated test config: declares only the D1 binding + CORS vars.
      // It deliberately omits the `containers` / `durable_objects` /
      // `migrations` keys so miniflare never tries to spin up the real
      // container-backed `ApiBackend` Durable Object. Proxy routing is
      // exercised by injecting a stub `API_BACKEND` binding per-test and
      // invoking `worker.fetch` directly (see test/index.spec.ts).
      wrangler: {
        configPath: "./wrangler.test.jsonc",
      },
    }),
  ],
  test: {
    include: ["test/**/*.spec.ts"],
  },
});
