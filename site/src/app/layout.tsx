import type { Metadata } from "next"
import { Inter, JetBrains_Mono } from "next/font/google"
import Script from "next/script"
import { Analytics } from "@vercel/analytics/next"
import { FooterNav } from "@/components/footer-nav"
import { PageTransition } from "@/components/page-transition"
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
  "Paste any job posting URL and find out when it was really posted. Detect ghost jobs, reposts, and stale listings across Greenhouse, Lever, Ashby, Workday, and 23+ more ATS platforms."

const themeInitScript = `
  try {
    var storedTheme = window.localStorage.getItem("howoldisthisjob-theme");
    var theme = storedTheme === "dark" || storedTheme === "light"
      ? storedTheme
      : (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
  } catch {}
`

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
      suppressHydrationWarning
      className={`${inter.variable} ${mono.variable} h-full antialiased`}
    >
      <body
        suppressHydrationWarning
        className="flex min-h-svh flex-col bg-white text-neutral-950 transition-colors dark:bg-black dark:text-neutral-50"
      >
        <Script id="theme-init" strategy="beforeInteractive">
          {themeInitScript}
        </Script>
        <PageTransition>{children}</PageTransition>
        <FooterNav />
        <Analytics />
      </body>
    </html>
  )
}
