import type { MetadataRoute } from "next"

const BASE = "https://howoldisthisjob.com"

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date()
  return [
    { url: `${BASE}/`, lastModified, changeFrequency: "weekly", priority: 1 },
    { url: `${BASE}/about`, lastModified, changeFrequency: "monthly", priority: 0.8 },
    { url: `${BASE}/changelog`, lastModified, changeFrequency: "weekly", priority: 0.5 },
  ]
}
