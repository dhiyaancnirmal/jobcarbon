import type { Metadata } from "next"
import Link from "next/link"
import { Logo } from "@/components/logo"
import { SUPPORTED_PLATFORMS } from "@/lib/supported-platforms"

export const metadata: Metadata = {
  title: 'About "How Old Is This Job?"',
  description:
    "How Old Is This Job? finds the real posting date of a job listing using platform records, page metadata, and archive signals.",
}

const SIGNALS = [
  {
    label: "Platform API data",
    note: "ATS-native posted and updated timestamps",
  },
  {
    label: "Structured metadata",
    note: "JSON-LD, OpenGraph, and schema.org datePosted",
  },
  {
    label: "Rendered page clues",
    note: "Visible dates and relative timestamps in the HTML",
  },
  {
    label: "Sitemaps and feeds",
    note: "XML sitemap lastmod and job feed publication dates",
  },
  {
    label: "Archive traces",
    note: "Wayback Machine captures used as ceiling dates",
  },
]

type PlatformStatus = "supported" | "blocked" | "unsupported"

type PlatformRow = { name: string; status: PlatformStatus }

const EXTRA_PLATFORMS: PlatformRow[] = [
  { name: "Indeed", status: "blocked" },
  { name: "LinkedIn", status: "blocked" },
  { name: "Google Careers", status: "unsupported" },
  { name: "ClearCompany / HRMDirect", status: "unsupported" },
]

const PLATFORM_ROWS: PlatformRow[] = [
  ...SUPPORTED_PLATFORMS.map((p) => ({
    name: p.displayName,
    status: "supported" as const,
  })),
  ...EXTRA_PLATFORMS,
].sort((a, b) => a.name.localeCompare(b.name))

const STATUS_LABEL: Record<PlatformStatus, string> = {
  supported: "Supported",
  blocked: "Blocked",
  unsupported: "No dates",
}

const STATUS_PILL: Record<PlatformStatus, string> = {
  supported: "gel-pill--high",
  blocked: "gel-pill--low",
  unsupported: "gel-pill--unknown",
}

const FAQ = [
  {
    q: "What counts as a ghost job?",
    a: "A listing that still looks active but has been up far longer than the employer advertises. Old URLs, repost loops, and stale entries all qualify.",
  },
  {
    q: "How are reposts flagged?",
    a: "The detector compares multiple timestamps. If a page looks fresh but the URL has existed much longer, it is treated as a refresh.",
  },
  {
    q: "Why are LinkedIn and Indeed blocked?",
    a: "Those aggregator pages do not reliably expose the posting signals needed. Use the employer's direct careers URL instead.",
  },
  {
    q: "How accurate are the dates?",
    a: "Direct platform fields are strongest. Page metadata is weaker since employers can edit it. Archive dates are ceilings, not proof.",
  },
  {
    q: "What if no date is found?",
    a: "The result still returns title, company, platform, and any weaker evidence — just without a confident posted date.",
  },
  {
    q: "Do you store any data?",
    a: "No accounts and no third-party tracking pixels. One HttpOnly cookie holds a hashed session token so your search history follows you back, and Sentry receives anonymized error and performance traces. That's it.",
  },
]

export default function About() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col px-6 py-10">
      <div className="mx-auto flex w-full max-w-[42rem] flex-col gap-12">
        <section className="flex flex-col gap-4">
          <Logo size={40} />
          <h1 className="text-[2rem] font-semibold tracking-tight text-neutral-900 sm:text-[2.3rem]">
            About &ldquo;How Old Is This Job?&rdquo;
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-neutral-600 sm:text-[15px]">
            A tool for finding the real posting date of a job listing. Best on direct employer ATS pages — Greenhouse, Lever, Ashby, Workday, and 20+ more.
          </p>
          <div>
            <Link
              href="/"
              className="gel-btn gel-btn--sm gel-btn--save no-underline"
            >
              Check a job posting
            </Link>
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold tracking-tight text-neutral-900">
            How it works
          </h2>
          <ol className="flex flex-col divide-y divide-neutral-100 overflow-hidden rounded-xl border border-neutral-200 bg-white">
            {SIGNALS.map((s, i) => (
              <li
                key={s.label}
                className="flex items-baseline gap-4 px-4 py-3"
              >
                <span className="font-mono text-[11px] tabular-nums text-neutral-400">
                  0{i + 1}
                </span>
                <div className="flex flex-1 flex-col gap-0.5">
                  <span className="text-sm font-medium text-neutral-900">
                    {s.label}
                  </span>
                  <span className="text-xs text-neutral-500">{s.note}</span>
                </div>
              </li>
            ))}
          </ol>
          <p className="text-xs text-neutral-500">
            Sources are ranked by reliability. When they disagree, the chosen source wins and the rest show up as evidence.
          </p>
        </section>

        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold tracking-tight text-neutral-900">
            Supported platforms
          </h2>
          <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200 bg-neutral-50 text-[10px] uppercase tracking-[0.12em] text-neutral-500">
                  <th className="px-4 py-2.5 text-left font-medium">
                    Platform
                  </th>
                  <th className="px-4 py-2.5 text-right font-medium">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {PLATFORM_ROWS.map((row) => (
                  <tr key={row.name}>
                    <td className="px-4 py-2.5 text-sm text-neutral-900">
                      {row.name}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <span className={`gel-pill ${STATUS_PILL[row.status]}`}>
                        {STATUS_LABEL[row.status]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold tracking-tight text-neutral-900">
            FAQ
          </h2>
          <div className="flex flex-col divide-y divide-neutral-200 overflow-hidden rounded-xl border border-neutral-200 bg-white">
            {FAQ.map((item) => (
              <details key={item.q} className="group">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3.5 text-sm font-medium text-neutral-900 marker:hidden">
                  <span>{item.q}</span>
                  <svg
                    aria-hidden
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="shrink-0 text-neutral-400 transition-transform group-open:rotate-180"
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </summary>
                <p className="px-4 pb-4 text-sm leading-relaxed text-neutral-600">
                  {item.a}
                </p>
              </details>
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}
