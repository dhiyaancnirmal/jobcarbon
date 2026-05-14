"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ThemeToggle } from "@/components/theme-toggle"
import { cn } from "@/lib/utils"

const links = [
  { href: "/", label: "Home" },
  { href: "/about", label: "About" },
  { href: "/extension", label: "Extension" },
  { href: "/cli", label: "CLI" },
]

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/"
  return pathname === href || pathname.startsWith(`${href}/`)
}

export function FooterNav() {
  const pathname = usePathname()

  return (
    <footer className="site-footer-nav mx-auto mt-auto w-full max-w-4xl px-6 pb-5 pt-2 text-[11px] text-neutral-600 transition-colors dark:text-neutral-400">
      <div className="mx-auto flex w-full max-w-[42rem] flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          {links.map((link, index) => (
            <span key={link.href} className="contents">
              {index > 0 && (
                <span className="text-neutral-400 dark:text-neutral-600">·</span>
              )}
              <Link
                href={link.href}
                aria-current={isActive(pathname, link.href) ? "page" : undefined}
                className={cn(
                  "footer-link transition-colors hover:text-neutral-800 dark:hover:text-neutral-200",
                  isActive(pathname, link.href) && "footer-link--active",
                )}
              >
                {link.label}
              </Link>
            </span>
          ))}
          <span className="text-neutral-400 dark:text-neutral-600">·</span>
          <ThemeToggle />
        </div>
        <Link
          href="/changelog"
          aria-current={isActive(pathname, "/changelog") ? "page" : undefined}
          className={cn(
            "footer-link transition-colors hover:text-neutral-800 dark:hover:text-neutral-200",
            isActive(pathname, "/changelog") && "footer-link--active",
          )}
        >
          v0.1.3
        </Link>
      </div>
    </footer>
  )
}
