import type { Metadata } from "next"
import { Inter, JetBrains_Mono } from "next/font/google"
import Link from "next/link"
import "./globals.css"

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
})

const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
})

const SITE_URL = "https://howoldisthisjob.com"
const SITE_TITLE = "How Old Is This Job? - Find the real posting date"
const SITE_DESCRIPTION =
  "Paste any job posting URL and find out when it was really posted. Detect ghost jobs, reposts, and stale listings across Greenhouse, Lever, Ashby, Workday, and 20+ more platforms."

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TITLE,
    template: "%s · How Old Is This Job?",
  },
  description: SITE_DESCRIPTION,
  keywords: [
    "job posting date",
    "ghost job detector",
    "reposted job",
    "job age",
    "greenhouse",
    "lever",
    "ashby",
    "workday",
    "hiring platform",
    "when was this job posted",
  ],
  openGraph: {
    type: "website",
    url: SITE_URL,
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    siteName: "How Old Is This Job?",
  },
  twitter: {
    card: "summary",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
  },
  robots: { index: true, follow: true },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${mono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="flex min-h-svh flex-col bg-white">
        <script dangerouslySetInnerHTML={{ __html: `try{var h=localStorage.getItem('jobcarbon-history');if(h&&JSON.parse(h).length>0)document.documentElement.setAttribute('data-has-history','')}catch(e){}` }} />
        {children}
        <footer className="mt-auto mx-auto w-full max-w-xl px-6 pb-5 pt-2 text-[11px] text-neutral-500">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link
                href="/"
                className="transition-colors hover:text-neutral-800"
              >
                Home
              </Link>
              <span className="text-neutral-400">·</span>
              <Link
                href="/about"
                className="transition-colors hover:text-neutral-800"
              >
                About
              </Link>
            </div>
            <Link
              href="/changelog"
              className="transition-colors hover:text-neutral-800"
            >
              v0.1.0
            </Link>
          </div>
        </footer>
      </body>
    </html>
  )
}
