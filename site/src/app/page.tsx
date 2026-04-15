import { JobChecker } from "@/components/job-checker"
import { Logo } from "@/components/logo"

export default function Home() {
  return (
    <main className="mx-auto flex min-h-[calc(100svh-56px)] w-full max-w-xl flex-col justify-center gap-6 px-6 py-6">
        <header className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Logo size={40} />
            <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
              How Old Is This Job?
            </h1>
          </div>
          <p className="text-[15px] leading-relaxed text-neutral-500">
            Paste a job posting URL and we&apos;ll tell you when it was really posted.
          </p>
        </header>

        <JobChecker />
    </main>
  )
}
