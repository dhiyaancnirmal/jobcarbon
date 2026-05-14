import type { Metadata } from "next"
import { Logo } from "@/components/logo"

export const metadata: Metadata = {
  title: "Chrome Extension",
  description:
    "Install the How Old Is This Job? Chrome extension to badge ATS job links and scan supported job pages.",
}

const STEPS = [
  "Download and unzip the extension.",
  "Open chrome://extensions.",
  "Enable Developer Mode.",
  'Click "Load unpacked".',
  "Select the unzipped extension folder.",
]

export default function ExtensionPage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col px-6 py-10">
      <div className="mx-auto flex w-full max-w-[42rem] flex-col gap-8">
        <section className="flex flex-col gap-4">
          <Logo size={40} />
          <h1 className="text-[2rem] font-semibold tracking-tight text-neutral-900 sm:text-[2.3rem] dark:text-neutral-50">
            Chrome Extension
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href="/downloads/how-old-is-this-job-extension.zip"
              download
              className="gel-btn gel-btn--sm gel-btn--save no-underline"
            >
              Download extension
            </a>
          </div>
        </section>

        <section className="flex flex-col gap-3">
          <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-950">
            <video
              className="h-auto w-full bg-white dark:bg-black"
              src="/extension-demo/job-checker-extension-demo.mp4"
              poster="/extension-demo/job-checker-extension-demo-poster.jpg"
              autoPlay
              muted
              loop
              playsInline
              controls
              preload="metadata"
              aria-label="Demo of the How Old Is This Job Chrome extension badging job ages on an Ashby job board."
            />
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
            Install locally
          </h2>
          <ol className="flex flex-col divide-y divide-neutral-100 overflow-hidden rounded-xl border border-neutral-200 bg-white dark:divide-neutral-900 dark:border-neutral-800 dark:bg-neutral-950">
            {STEPS.map((step, index) => (
              <li key={step} className="flex items-baseline gap-4 px-4 py-3">
                <span className="font-mono text-[11px] tabular-nums text-neutral-400">
                  0{index + 1}
                </span>
                <span className="text-sm text-neutral-700 dark:text-neutral-200">{step}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </main>
  )
}
