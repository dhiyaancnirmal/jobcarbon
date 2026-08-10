# howoldisthisjob site

Vite and React frontend for `howoldisthisjob.com`.

## Local development

```bash
npm install
npm run dev
```

The app runs on `http://localhost:5173` by default.

API base:

- `VITE_HOWOLDISTHISJOB_API` when set at build time
- otherwise `https://api.howoldisthisjob.com`

## Production

- Frontend: Cloudflare Worker static assets / `howoldisthisjob-site`
- API: Cloudflare Worker + container / `api.howoldisthisjob.com`
