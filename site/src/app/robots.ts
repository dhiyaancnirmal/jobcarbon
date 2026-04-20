import type { MetadataRoute } from "next"

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/monitoring", "/api/"],
    },
    sitemap: "https://howoldisthisjob.com/sitemap.xml",
    host: "https://howoldisthisjob.com",
  }
}
