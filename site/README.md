# jobcarbon site

Next.js frontend for `howoldisthisjob.com`.

## Local development

```bash
npm install
npm run dev
```

The app runs on `http://localhost:3000` by default.

API base:

- `NEXT_PUBLIC_JOBCARBON_API` when set
- otherwise `https://api.howoldisthisjob.com`

## Production

- Frontend: Vercel
- API: Railway / `api.howoldisthisjob.com`
