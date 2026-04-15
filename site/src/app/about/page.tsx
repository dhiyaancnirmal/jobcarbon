import type { Metadata } from "next"
import Link from "next/link"
import { Logo } from "@/components/logo"

export const metadata: Metadata = {
  title: "About",
  description:
    "How Old Is This Job? explains how the detector uses platform records, page metadata, and archive signals to estimate when a job was really posted.",
}

const PLATFORMS = [
  { name: "SmartRecruiters", gelClass: "gel-btn--smartrecruiters", href: "https://www.smartrecruiters.com" },
  { name: "Lever", gelClass: "gel-btn--lever", href: "https://www.lever.co" },
  { name: "BambooHR", gelClass: "gel-btn--bamboohr", href: "https://www.bamboohr.com" },
  { name: "iCIMS", gelClass: "gel-btn--icims", href: "https://www.icims.com" },
  { name: "Dover", gelClass: "gel-btn--dover", href: "https://www.dover.io" },
  { name: "Greenhouse", gelClass: "gel-btn--greenhouse", href: "https://www.greenhouse.io" },
  { name: "Ashby", gelClass: "gel-btn--ashby", href: "https://www.ashbyhq.com" },
  { name: "Workday", gelClass: "gel-btn--workday", href: "https://www.workday.com" },
  { name: "JazzHR", gelClass: "gel-btn--jazzhr", href: "https://www.jazzhr.com" },
  { name: "Gem", gelClass: "gel-btn--gem", href: "https://www.gem.com" },
  { name: "SuccessFactors", gelClass: "gel-btn--successfactors", href: "https://www.successfactors.com" },
  { name: "Workable", gelClass: "gel-btn--workable", href: "https://www.workable.com" },
  { name: "Rippling", gelClass: "gel-btn--rippling", href: "https://www.rippling.com" },
  { name: "ADP", gelClass: "gel-btn--adp", href: "https://www.adp.com" },
  { name: "Paycor", gelClass: "gel-btn--paycor", href: "https://www.paycor.com" },
  { name: "Oracle HCM", gelClass: "gel-btn--oracle-hcm", href: "https://www.oracle.com/human-capital-management" },
  { name: "Jobvite", gelClass: "gel-btn--jobvite", href: "https://www.jobvite.com" },
  { name: "Avature", gelClass: "gel-btn--avature", href: "https://www.avature.net" },
  { name: "Teamtailor", gelClass: "gel-btn--teamtailor", href: "https://www.teamtailor.com" },
  { name: "Brassring", gelClass: "gel-btn--brassring", href: "https://www.ibm.com/products/brassring" },
  { name: "Recruitee", gelClass: "gel-btn--recruitee", href: "https://www.recruitee.com" },
  { name: "Personio", gelClass: "gel-btn--personio", href: "https://www.personio.com" },
  { name: "Breezy HR", gelClass: "gel-btn--breezy", href: "https://breezy.hr" },
]

const FAQ = [
  {
    q: "What counts as a ghost job?",
    a: "Usually a listing that still looks active but has been sitting around far longer than the employer wants you to notice. Old URLs, repost loops, and stale entries all show up here.",
  },
  {
    q: "How do you flag reposts?",
    a: "The detector compares multiple timestamps. If a page looks fresh but the same URL has existed much longer, it should be treated as a refresh rather than a new opening.",
  },
  {
    q: "Why are Indeed and LinkedIn blocked?",
    a: "Because those public job pages do not reliably expose the direct data needed for this kind of check. If a listing links to the employer's careers page, use that source URL instead.",
  },
  {
    q: "How accurate are the dates?",
    a: "Direct platform fields are strongest. Page metadata is weaker because employers can edit it. Archive dates are useful ceilings, not perfect proof of the original posting moment.",
  },
  {
    q: "What happens if no date is found?",
    a: "The result still returns whatever evidence is available, including title, company, platform, and weaker timing hints. Some pages simply do not publish enough information to recover a durable posting date.",
  },
]

export default function About() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-col gap-6 px-6 py-10">
      <section className="flex flex-col gap-3">
        <div className="flex items-center gap-3">
          <Logo size={40} />
          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
            About How Old Is This Job?
          </h1>
        </div>
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-neutral-500">
          <p>
            This site estimates when a job was actually posted. It was built for a
            narrow problem: many listings are designed to look fresh even when the
            underlying opening is old, reposted, or quietly sitting in a platform.
          </p>
          <p>
            The detector checks direct platform data first, then falls back to structured
            page metadata, rendered content, sitemap dates, and archive history. The
            goal is not to invent certainty where none exists — just to show the
            strongest date signal available and make stale listings easier to spot.
          </p>
        </div>
        <Link href="/" className="gel-btn gel-btn--save w-fit">
          Check a posting
        </Link>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-neutral-900">Supported platforms</h2>
        <div className="flex flex-wrap gap-2">
          {PLATFORMS.map((p) => (
            <a key={p.name} href={p.href} target="_blank" rel="noopener noreferrer" className={`gel-btn gel-btn--sm ${p.gelClass}`}>
              {p.name}
            </a>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-neutral-900">FAQ</h2>
        <div className="flex flex-col rounded-xl border border-neutral-200 bg-white overflow-hidden">
          {FAQ.map((item, i) => (
            <details key={item.q} className={i > 0 ? "border-t border-neutral-100" : ""}>
              <summary className="cursor-pointer px-4 py-3 text-xs font-medium text-neutral-800 transition-colors hover:bg-neutral-50">
                {item.q}
              </summary>
              <p className="px-4 pb-3 text-xs text-neutral-500 leading-relaxed">{item.a}</p>
            </details>
          ))}
        </div>
      </section>
    </main>
  )
}
