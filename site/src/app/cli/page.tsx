import type { Metadata } from "next"
import { CopyCommandButton } from "@/components/copy-command-button"
import { Logo } from "@/components/logo"

export const metadata: Metadata = {
  title: "CLI",
  description:
    "Use the How Old Is This Job? CLI from npm to check job posting ages from your terminal or local scripts.",
}

const COMMANDS = [
  {
    label: "Run once",
    command:
      "npx howoldisthisjob https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694",
  },
  {
    label: "Install globally",
    command: "npm install -g howoldisthisjob",
  },
  {
    label: "Start the local API",
    command:
      "npx --package howoldisthisjob howoldisthisjob-api --host 127.0.0.1 --port 8000",
  },
]

const OUTPUT_FIELDS = [
  "likely_posted_date",
  "likely_age_days",
  "confidence",
  "reposted_likely",
  "chosen_source",
  "all_dates",
  "warnings",
]

export default function CliPage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col px-6 py-10">
      <div className="mx-auto flex w-full max-w-[42rem] flex-col gap-10">
        <section className="flex flex-col gap-4">
          <Logo size={40} />
          <div className="flex flex-col gap-3">
            <h1 className="text-[2rem] font-semibold tracking-tight text-neutral-900 sm:text-[2.3rem] dark:text-neutral-50">
              CLI
            </h1>
            <p className="max-w-2xl text-sm leading-relaxed text-neutral-600 dark:text-neutral-300">
              Run the same detector from your terminal, shell scripts, or local
              automation. The npm package ships the CLI wrapper and bundled
              Python detector.
            </p>
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
            Install and run
          </h2>
          <div className="flex flex-col divide-y divide-neutral-100 overflow-hidden rounded-xl border border-neutral-200 bg-white dark:divide-neutral-900 dark:border-neutral-800 dark:bg-neutral-950">
            {COMMANDS.map((item) => (
              <div key={item.label} className="flex flex-col gap-2 px-4 py-3.5">
                <span className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
                  {item.label}
                </span>
                <div className="flex items-center gap-2">
                  <code className="scrollbar-none min-w-0 flex-1 overflow-x-auto whitespace-nowrap rounded-md bg-neutral-100 px-3 py-2 font-mono text-[12px] leading-relaxed text-neutral-900 dark:bg-neutral-900 dark:text-neutral-100">
                    {item.command}
                  </code>
                  <CopyCommandButton command={item.command} />
                </div>
              </div>
            ))}
          </div>
          <p className="text-xs leading-relaxed text-neutral-500 dark:text-neutral-400">
            Requires Node.js for the npm entrypoint and Python 3.11 or newer for
            the detector runtime.
          </p>
        </section>

        <section className="grid gap-4 sm:grid-cols-[1fr_1fr]">
          <div className="flex flex-col gap-3 rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-950">
            <h2 className="text-sm font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
              Output
            </h2>
            <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-300">
              Results are printed as JSON so they can be piped into tools like
              `jq`, saved in CI logs, or consumed by another script.
            </p>
            <div className="flex flex-wrap gap-2">
              {OUTPUT_FIELDS.map((field) => (
                <code
                  key={field}
                  className="rounded-md border border-neutral-200 px-2 py-1 font-mono text-[11px] text-neutral-600 dark:border-neutral-800 dark:text-neutral-300"
                >
                  {field}
                </code>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-3 rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-950">
            <h2 className="text-sm font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
              Package
            </h2>
            <p className="text-sm leading-relaxed text-neutral-600 dark:text-neutral-300">
              Published on npm as `howoldisthisjob`. It exposes two commands:
              `howoldisthisjob` for one-off checks and `howoldisthisjob-api`
              for a local HTTP server.
            </p>
            <a
              href="https://www.npmjs.com/package/howoldisthisjob"
              className="text-sm font-medium text-neutral-900 underline decoration-neutral-300 underline-offset-4 hover:text-neutral-700 dark:text-neutral-100 dark:decoration-neutral-700 dark:hover:text-neutral-300"
            >
              View npm package
            </a>
          </div>
        </section>
      </div>
    </main>
  )
}
