import { useEffect } from "react"
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom"
import About from "@/pages/about"
import Changelog from "@/pages/changelog"
import CliPage from "@/pages/cli"
import ExtensionPage from "@/pages/extension"
import Home from "@/pages/home"
import { FooterNav } from "@/components/footer-nav"
import { PageTransition } from "@/components/page-transition"

const PAGE_METADATA = {
  "/": {
    title: "How Old Is This Job? - Find the real posting date",
    description:
      "Paste any job posting URL and find out when it was really posted. Detect ghost jobs, reposts, and stale listings across Greenhouse, Lever, Ashby, Workday, and 23+ more ATS platforms.",
  },
  "/about": {
    title: 'About "How Old Is This Job?" · How Old Is This Job?',
    description:
      "How Old Is This Job? finds the real posting date of a job listing using platform records, page metadata, and archive signals.",
  },
  "/changelog": {
    title: "Changelog · How Old Is This Job?",
    description: "Version history for How Old Is This Job?",
  },
  "/cli": {
    title: "CLI · How Old Is This Job?",
    description:
      "Use the How Old Is This Job? CLI from npm to check job posting ages from your terminal or local scripts.",
  },
  "/extension": {
    title: "Chrome Extension · How Old Is This Job?",
    description:
      "Install the How Old Is This Job? Chrome extension to badge ATS job links and scan supported job pages.",
  },
} as const

function DocumentMetadata() {
  const { pathname } = useLocation()

  useEffect(() => {
    const path = pathname === "/" ? pathname : pathname.replace(/\/+$/, "")
    const metadata = PAGE_METADATA[path as keyof typeof PAGE_METADATA] ?? PAGE_METADATA["/"]
    document.title = metadata.title
    document.querySelector('meta[name="description"]')?.setAttribute("content", metadata.description)
  }, [pathname])

  return null
}

function NotFound() {
  return (
    <main className="mx-auto flex min-h-[calc(100svh-56px)] w-full max-w-4xl flex-col justify-center px-6 py-12">
      <div className="mx-auto flex w-full max-w-[42rem] flex-col gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">Page not found</h1>
        <a className="gel-btn gel-btn--sm gel-btn--save w-fit no-underline" href="/">
          Back home
        </a>
      </div>
    </main>
  )
}

function RoutedApp() {
  return (
    <>
      <DocumentMetadata />
      <PageTransition>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<About />} />
          <Route path="/changelog" element={<Changelog />} />
          <Route path="/cli" element={<CliPage />} />
          <Route path="/extension" element={<ExtensionPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </PageTransition>
      <FooterNav />
    </>
  )
}

export function App() {
  return (
    <BrowserRouter>
      <RoutedApp />
    </BrowserRouter>
  )
}
