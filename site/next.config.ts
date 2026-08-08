import { withSentryConfig } from "@sentry/nextjs"
import type { NextConfig } from "next"
import { dirname } from "node:path"
import { fileURLToPath } from "node:url"

const SITE_ROOT = dirname(fileURLToPath(import.meta.url))

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  turbopack: {
    root: SITE_ROOT,
  },
}

const hasSentryReleaseAuth = Boolean(process.env.SENTRY_AUTH_TOKEN)

const sentryWrappedConfig = withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG ?? "dhiyaan",
  project: process.env.SENTRY_PROJECT ?? "howoldisthisjob",
  authToken: process.env.SENTRY_AUTH_TOKEN,
  silent: !process.env.CI,
  widenClientFileUpload: true,
  sourcemaps: {
    disable: !hasSentryReleaseAuth,
  },
  webpack: {
    treeshake: {
      removeDebugLogging: true,
    },
  },
})

export default hasSentryReleaseAuth ? sentryWrappedConfig : nextConfig
