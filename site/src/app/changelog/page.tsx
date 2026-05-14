import type { Metadata } from "next"
export const metadata: Metadata = {
  title: "Changelog",
  description: "Version history for How Old Is This Job?",
}

const ENTRIES = [
  {
    version: "v0.1.3",
    date: "May 2026",
    changes: [
      "Published the `howoldisthisjob` CLI on npm.",
      "Added the CLI site page with install, run, and API commands.",
      "Smoothed page transitions, footer navigation, result cards, and page layouts.",
    ],
  },
  {
    version: "v0.1.2",
    date: "April 2026",
    changes: [
      "Added PageUp support to the live platform set.",
      "Added a local Chrome extension page and install flow.",
      "Added browser-side aggregator assist for LinkedIn, Indeed, and Google Careers when source ATS links are exposed locally.",
    ],
  },
  {
    version: "v0.1.1",
    date: "April 2026",
    changes: [
      "Added `?url=` homepage deep-link auto-run support.",
      "Added day/night theme toggle and dark mode across the site.",
      "Reduced unnecessary ATS fallback work on faster success paths.",
    ],
  },
  {
    version: "v0.1.0",
    date: "April 2026",
    changes: [
      "Initial launch",
    ],
  },
]

export default function Changelog() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col px-6 py-10">
      <div className="mx-auto flex w-full max-w-[42rem] flex-col gap-8">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">
          Changelog
        </h1>
        <div className="flex flex-col gap-8">
          {ENTRIES.map((entry) => (
            <section
              key={entry.version}
              className="flex flex-col gap-2"
            >
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                  {entry.version}
                </span>
                <span className="text-xs text-neutral-400 dark:text-neutral-500">
                  {entry.date}
                </span>
              </div>
              <ul className="flex list-disc flex-col gap-1 pl-5">
                {entry.changes.map((change) => (
                  <li key={change} className="text-sm text-neutral-600 dark:text-neutral-300">
                    {change}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </main>
  )
}
