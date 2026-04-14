import { JobChecker } from "@/components/job-checker"
import { PlatformCarousel } from "@/components/platform-carousel"

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col justify-center gap-12 px-6 py-20">
        <header className="flex flex-col gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
            How old is this job?
          </h1>
          <p className="text-[15px] leading-relaxed text-neutral-500">
            Paste a job posting URL. We check structured data and ATS APIs to
            estimate when it was really posted.
          </p>
        </header>

        <JobChecker />

        <div className="flex flex-col gap-4 -mx-6">
          <p className="px-6 text-xs text-neutral-400">Supported platforms</p>
          <PlatformCarousel withLogos={false} />
        </div>
      </main>
    </div>
  )
}
