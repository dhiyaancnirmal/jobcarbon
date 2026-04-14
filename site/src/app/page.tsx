import { JobChecker } from "@/components/job-checker"
import { Logo } from "@/components/logo"
import { PlatformCarousel } from "@/components/platform-carousel"

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col justify-center gap-12 px-6 py-20">
        <header className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Logo size={40} />
            <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
              How old is this job?
            </h1>
          </div>
          <p className="text-[15px] leading-relaxed text-neutral-500">
            Paste a job posting URL and we&apos;ll tell you when it was really posted.
          </p>
        </header>

        <JobChecker />

        <div className="flex flex-col gap-4 -mx-6">
          <p className="px-6 text-xs text-neutral-400">23+ platforms supported</p>
          <PlatformCarousel />
        </div>
      </main>
    </div>
  )
}
