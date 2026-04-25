import { JobChecker } from "@/components/job-checker"
import { Logo } from "@/components/logo"
import Link from "next/link"

export default function Home() {
  return (
    <main className="mx-auto flex min-h-[calc(100svh-56px)] w-full max-w-4xl flex-col justify-center px-6 py-12">
      <div className="mx-auto flex w-full max-w-[42rem] flex-col gap-6">
        <header className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Logo size={48} />
            <h1 className="text-[1.625rem] font-semibold leading-snug tracking-tight text-neutral-900 md:text-[1.6875rem] dark:text-neutral-50">
              How Old Is This Job?
            </h1>
          </div>
          <p className="max-w-2xl text-base leading-relaxed text-neutral-600 dark:text-neutral-300">
            Paste a job posting URL and we&apos;ll tell you when it was really posted.
          </p>
          <p className="max-w-2xl text-sm leading-relaxed text-neutral-500 dark:text-neutral-400">
            For LinkedIn, Indeed, and Google Careers pages, use the{" "}
            <Link href="/extension" className="underline decoration-neutral-300 underline-offset-4 hover:text-neutral-700 dark:decoration-neutral-700 dark:hover:text-neutral-200">
              Chrome extension
            </Link>{" "}
            to recover the original employer ATS link when it&apos;s available.
          </p>
        </header>

        <JobChecker />
      </div>
    </main>
  )
}
