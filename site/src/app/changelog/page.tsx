import type { Metadata } from "next"
export const metadata: Metadata = {
  title: "Changelog",
  description: "Version history for How Old Is This Job?",
}

const ENTRIES = [
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
      <div className="mx-auto flex w-full max-w-[42rem] flex-col gap-6">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">
          Changelog
        </h1>
        <div className="flex flex-col gap-6">
          {ENTRIES.map((entry) => (
            <section
              key={entry.version}
              className="flex flex-col gap-2 rounded-xl border border-neutral-200 bg-white px-4 py-4 dark:border-neutral-800 dark:bg-neutral-950"
            >
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                  {entry.version}
                </span>
                <span className="text-xs text-neutral-400 dark:text-neutral-500">
                  {entry.date}
                </span>
              </div>
              <ul className="flex flex-col gap-1">
                {entry.changes.map((change) => (
                  <li key={change} className="text-sm text-neutral-500 dark:text-neutral-300">
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
