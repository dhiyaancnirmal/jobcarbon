const SECURITY_HEADERS = {
  "Content-Security-Policy": "frame-ancestors 'none'",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=(), browsing-topics=()",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
}

const worker = {
  async fetch(request, env) {
    const response = await env.ASSETS.fetch(request)
    const secured = new Response(response.body, response)

    for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
      secured.headers.set(name, value)
    }

    return secured
  },
}

export default worker
