"use client"

const PLATFORMS = [
  { name: "Lever", gelClass: "gel-btn--lever", href: "https://www.lever.co" },
  { name: "Greenhouse", gelClass: "gel-btn--greenhouse", href: "https://www.greenhouse.io" },
  { name: "Ashby", gelClass: "gel-btn--ashby", href: "https://www.ashbyhq.com" },
  { name: "SmartRecruiters", gelClass: "gel-btn--smartrecruiters", href: "https://www.smartrecruiters.com" },
  { name: "Workable", gelClass: "gel-btn--workable", href: "https://www.workable.com" },
  { name: "Workday", gelClass: "gel-btn--workday", href: "https://www.workday.com" },
  { name: "BambooHR", gelClass: "gel-btn--bamboohr", href: "https://www.bamboohr.com" },
  { name: "Rippling", gelClass: "gel-btn--rippling", href: "https://www.rippling.com" },
  { name: "iCIMS", gelClass: "gel-btn--icims", href: "https://www.icims.com" },
  { name: "Oracle HCM", gelClass: "gel-btn--oracle-hcm", href: "https://www.oracle.com/human-capital-management" },
  { name: "Jobvite", gelClass: "gel-btn--jobvite", href: "https://www.jobvite.com" },
  { name: "Brassring", gelClass: "gel-btn--brassring", href: "https://www.ibm.com/products/brassring" },
  { name: "SuccessFactors", gelClass: "gel-btn--successfactors", href: "https://www.successfactors.com" },
  { name: "Avature", gelClass: "gel-btn--avature", href: "https://www.avature.net" },
  { name: "Gem", gelClass: "gel-btn--gem", href: "https://www.gem.com" },
  { name: "Teamtailor", gelClass: "gel-btn--teamtailor", href: "https://www.teamtailor.com" },
  { name: "Recruitee", gelClass: "gel-btn--recruitee", href: "https://www.recruitee.com" },
  { name: "Personio", gelClass: "gel-btn--personio", href: "https://www.personio.com" },
  { name: "Breezy HR", gelClass: "gel-btn--breezy", href: "https://breezy.hr" },
  { name: "JazzHR", gelClass: "gel-btn--jazzhr", href: "https://www.jazzhr.com" },
  { name: "Dover", gelClass: "gel-btn--dover", href: "https://www.dover.io" },
  { name: "ADP", gelClass: "gel-btn--adp", href: "https://www.adp.com" },
  { name: "Paycor", gelClass: "gel-btn--paycor", href: "https://www.paycor.com" },
]

function makeButtons(prefix: string) {
  return PLATFORMS.map((p, i) => (
    <a key={`${prefix}-${i}`} href={p.href} target="_blank" rel="noopener noreferrer" className={`gel-btn gel-btn--sm ${p.gelClass}`}>
      {p.name}
    </a>
  ))
}

export function PlatformCarousel() {
  return (
    <div className="carousel-wrapper">
      <div className="carousel-track carousel-track--animate">
        {makeButtons("a")}
        {makeButtons("b")}
      </div>
    </div>
  )
}
