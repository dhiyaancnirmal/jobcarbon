import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Changelog",
  description: "Version history for How Old Is This Job?",
}

const ENTRIES = [
  {
    version: "v0.1.0",
    date: "April 2025",
    changes: [
      "Launch — detect real posting dates across 23 platforms",
      "Ghost job and repost detection",
      "Anonymous session-based search history",
      "About page with FAQ",
    ],
  },
]

export default function Changelog() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-col gap-6 px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
        Changelog
      </h1>
      <div className="flex flex-col gap-6">
        {ENTRIES.map((entry) => (
          <section key={entry.version} className="flex flex-col gap-2">
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-semibold text-neutral-900">{entry.version}</span>
              <span className="text-xs text-neutral-400">{entry.date}</span>
            </div>
            <ul className="flex flex-col gap-1">
              {entry.changes.map((change) => (
                <li key={change} className="text-sm text-neutral-500">
                  {change}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </main>
  )
}
