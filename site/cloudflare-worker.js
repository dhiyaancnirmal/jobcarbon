const SECURITY_HEADERS = {
  "Content-Security-Policy": "frame-ancestors 'none'",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=(), browsing-topics=()",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
}

const APP_ROUTES = new Set(["/", "/about", "/changelog", "/cli", "/extension"])

function appRoutePathname(pathname) {
  return pathname === "/" ? pathname : pathname.replace(/\/+$/, "")
}

function withSecurityHeaders(response) {
  const secured = new Response(response.body, response)

  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    secured.headers.set(name, value)
  }

  return secured
}

const worker = {
  async fetch(request, env) {
    const url = new URL(request.url)
    const appPath = appRoutePathname(url.pathname)

    if ((request.method === "GET" || request.method === "HEAD") && APP_ROUTES.has(appPath)) {
      const canonicalPath = appPath === "/" ? "/" : `${appPath}/`
      if (url.pathname !== canonicalPath) {
        url.pathname = canonicalPath
        return withSecurityHeaders(Response.redirect(url, 308))
      }

      const indexUrl = new URL("/index.html", request.url)
      return withSecurityHeaders(await env.ASSETS.fetch(new Request(indexUrl, request)))
    }

    return withSecurityHeaders(await env.ASSETS.fetch(request))
  },
}

export default worker
