# jobcarbon

`jobcarbon` estimates how old a job posting really is by checking structured data and ATS APIs.

## CLI

```bash
python3 jobcarbon.py https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694
```

Or install the console script locally:

```bash
pip install -e .
jobcarbon https://jobs.lever.co/skio/bbdd5a7b-652a-43ad-b92e-58f4e970c694
```

## HTTP API

Run the local API server:

```bash
python3 jobcarbon_api.py --host 127.0.0.1 --port 8000
```

Or via the console script after editable install:

```bash
jobcarbon-api --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /healthz`
- `GET /api/v1/estimate?url=<job-url>`
- `POST /api/v1/estimate` with JSON body `{"url": "<job-url>"}`

## Railway

This repo is set up for Railway with config-as-code in `railway.json`.

Deployment shape:

- Railway starts the API with `python3 jobcarbon_api.py`
- Railway provides `PORT`
- The API automatically binds to `0.0.0.0` when `PORT` is present
- Railway healthchecks use `GET /healthz`

Expected production topology:

- Website: `https://howoldisthisjob.com`
- API: `https://api.howoldisthisjob.com`

Suggested Railway flow:

1. Create a new Railway project from this repo.
2. Deploy the service as-is.
3. Add a custom domain for the API service, ideally `api.howoldisthisjob.com`.
4. Keep the website on its own service later, calling this API.

## Testing

```bash
python3 -m unittest discover -s tests -v
```
