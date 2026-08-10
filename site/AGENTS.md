# Static Vite frontend

This site is a Vite and React browser application. Keep it portable: static assets are served by `cloudflare-worker.js`, while `api.howoldisthisjob.com` owns the separate API Worker, container, and D1 data path. Do not add server-side rendering or frontend API routes.
