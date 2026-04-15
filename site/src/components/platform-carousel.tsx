"use client"

const PLATFORMS = [
  { name: "Lever", gelClass: "gel-btn--lever" },
  { name: "Greenhouse", gelClass: "gel-btn--greenhouse" },
  { name: "Ashby", gelClass: "gel-btn--ashby" },
  { name: "SmartRecruiters", gelClass: "gel-btn--smartrecruiters" },
  { name: "Workable", gelClass: "gel-btn--workable" },
  { name: "Workday", gelClass: "gel-btn--workday" },
  { name: "BambooHR", gelClass: "gel-btn--bamboohr" },
  { name: "Rippling", gelClass: "gel-btn--rippling" },
  { name: "iCIMS", gelClass: "gel-btn--icims" },
  { name: "Oracle HCM", gelClass: "gel-btn--oracle-hcm" },
  { name: "Jobvite", gelClass: "gel-btn--jobvite" },
  { name: "Brassring", gelClass: "gel-btn--brassring" },
  { name: "SuccessFactors", gelClass: "gel-btn--successfactors" },
  { name: "Avature", gelClass: "gel-btn--avature" },
  { name: "Gem", gelClass: "gel-btn--gem" },
  { name: "Teamtailor", gelClass: "gel-btn--teamtailor" },
  { name: "Recruitee", gelClass: "gel-btn--recruitee" },
  { name: "Personio", gelClass: "gel-btn--personio" },
  { name: "Breezy HR", gelClass: "gel-btn--breezy" },
  { name: "JazzHR", gelClass: "gel-btn--jazzhr" },
  { name: "Dover", gelClass: "gel-btn--dover" },
  { name: "ADP", gelClass: "gel-btn--adp" },
  { name: "Paycor", gelClass: "gel-btn--paycor" },
]

function makeButtons(prefix: string) {
  return PLATFORMS.map((p, i) => (
    <span key={`${prefix}-${i}`} className={`gel-btn gel-btn--sm ${p.gelClass}`}>
      {p.name}
    </span>
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
