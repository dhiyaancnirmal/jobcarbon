import type { Metadata } from "next"
import Image from "next/image"
import Link from "next/link"
import { Logo } from "@/components/logo"

export const metadata: Metadata = {
  title: "Chrome Extension",
  description:
    "Install the How Old Is This Job? Chrome extension to badge ATS job links and scan supported job pages.",
}

const STEPS = [
  "Open chrome://extensions.",
  "Enable Developer Mode.",
  'Click "Load unpacked".',
  "Select /Users/dhiyaan/Code/howoldisthisjob/extension.",
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
          <p className="max-w-2xl text-sm leading-relaxed text-neutral-600 sm:text-[15px] dark:text-neutral-300">
            Badge job ages on supported ATS pages and scan visible job links from the browser.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href="/"
              className="gel-btn gel-btn--sm gel-btn--save no-underline"
            >
              Check a job URL
            </Link>
            <Link
              href="/about"
              className="gel-btn gel-btn--sm gel-btn--neutral no-underline"
            >
              Supported platforms
            </Link>
          </div>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
            Extension in Chrome
          </h2>
          <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-950">
            <Image
              src="/extension-screenshots/ashby-openai-popup-scanned.png"
              alt="How Old Is This Job? Chrome extension showing scanned job ages on an Ashby job board."
              width={1920}
              height={1200}
              priority
              className="h-auto w-full"
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
