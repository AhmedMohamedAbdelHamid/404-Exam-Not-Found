# Exam Not Found — FastAPI bridge

The API consumes the existing retrieval, generation, validation, fallback, and staircase contracts. It adds safe HTTP DTOs, server-side option randomization, idempotent answer handling, durable analytics, and protected teacher aggregation.

## Install

Create and activate the root virtual environment, then install **both** dependency files from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r api\requirements.txt
```

The root requirements provide generation/RAG and legacy dependencies imported by the API. The API requirements provide FastAPI, Uvicorn, and test dependencies. Installing only `api/requirements.txt` is insufficient.

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
```

The API exposes health, attempt creation/state, next-question, answer submission, results, the explicit demo teacher endpoint, and the live teacher endpoint (no authentication). Interactive documentation is available at `/api/docs`.

## Configuration

Python/FastAPI values are documented in the root `.env.example`:

- `GEMINI_API_KEY`: optional for fallback-only operation; required for live Gemini generation.
- `DATABASE_URL`: Supabase Postgres connection string (required on Vercel, see above).
- `ALLOW_EPHEMERAL_STORAGE=1`: demo-only override that permits per-instance SQLite on Vercel.
- `LIVE_GENERATION_COOLDOWN_SECONDS`: provider cooldown after structured transient failures; defaults to 120 seconds.

CORS is open to any origin, and `GET /api/teacher/live` requires no token.

## Runtime behavior and persistence

Live generation uses the Gemini pipeline over textbook chunks stored in the `chunks` table. Known operational generation failures fall back to the verified question pool (5 hand-authored questions per topic and language, chosen at random among the closest in difficulty); failures do not advance the staircase. Every fallback is logged with its reason (Vercel -> Logs, look for "Serving verified fallback question").

**All state lives in Postgres (Supabase)** -- attempts, per-attempt session context (`attempt_contexts`), adaptive state, analytics and chunks -- because Vercel runs requests on separate, short-lived instances that share no memory or disk. `DATABASE_URL` must therefore be a real `postgresql://` connection string. On Vercel the API refuses to run without one (HTTP 503 `STORAGE_NOT_CONFIGURED`) rather than silently keeping state in a per-instance SQLite file, which loses attempts mid-quiz. Tables and chunks are created/seeded automatically on first use; `migrations/*.sql` and `seed_chunks.py` remain available for manual setup.

Locally, with `DATABASE_URL` unset, a temporary SQLite file is used (development only).

## Diagnostics

`GET /api/diagnostics` reports storage mode/reachability, chunk counts, whether a Gemini key is set, and a plain-language `verdict`. `GET /api/diagnostics?probe=1` also runs the real question pipeline once (2 Gemini calls, rate limited to one probe per 30 s per instance) and shows the stage where it fails (`gemini_generate`, `validation_stage1`, `validation_stage2`). No secrets are returned.

## Tests

The API tests inject generation behavior and do not call Gemini:

```powershell
$env:PYTHONPATH="api"; .\.venv\Scripts\python.exe -m pytest api\tests\test_deployment_fixes.py -q
```

(The older test files in `api/tests` target the previous SQLite/Chroma implementation and no longer import.)
