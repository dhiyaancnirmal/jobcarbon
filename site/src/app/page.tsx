import { JobChecker } from "@/components/job-checker"
import { Logo } from "@/components/logo"

export default function Home() {
  return (
    <main className="mx-auto flex min-h-[calc(100svh-56px)] w-full max-w-xl flex-col justify-center gap-6 px-6 py-6 md:py-8">
        <div className="flex flex-col gap-6 will-change-transform transition-transform duration-220 ease-[cubic-bezier(0.22,1,0.36,1)] has-[[data-has-history]]:max-md:-translate-y-[12vh] has-[[data-has-history]]:md:-translate-y-[14vh]">
        <header className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Logo size={48} />
            <h1 className="text-[1.625rem] font-semibold leading-snug tracking-tight text-neutral-900 md:text-[1.6875rem]">
              How Old Is This Job?
            </h1>
          </div>
          <p className="text-base leading-relaxed text-neutral-500">
            Paste a job posting URL and we&apos;ll tell you when it was really posted.
          </p>
        </header>

        <JobChecker />
        </div>
    </main>
  )
}
