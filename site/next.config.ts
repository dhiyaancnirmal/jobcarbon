import { withSentryConfig } from "@sentry/nextjs"
import type { NextConfig } from "next"
import { dirname } from "node:path"
import { fileURLToPath } from "node:url"

const SITE_ROOT = dirname(fileURLToPath(import.meta.url))

const SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), browsing-topics=()",
  },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
]

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  turbopack: {
    root: SITE_ROOT,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: SECURITY_HEADERS,
      },
    ]
  },
}

const hasSentryReleaseAuth = Boolean(process.env.SENTRY_AUTH_TOKEN)

const sentryWrappedConfig = withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG ?? "dhiyaan",
  project: process.env.SENTRY_PROJECT ?? "howoldisthisjob",
  authToken: process.env.SENTRY_AUTH_TOKEN,
  silent: !process.env.CI,
  widenClientFileUpload: true,
  tunnelRoute: "/monitoring",
  sourcemaps: {
    disable: !hasSentryReleaseAuth,
  },
  webpack: {
    automaticVercelMonitors: true,
    treeshake: {
      removeDebugLogging: true,
    },
  },
})

export default hasSentryReleaseAuth ? sentryWrappedConfig : nextConfig
