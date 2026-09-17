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

The API exposes health, attempt creation/state, next-question, answer submission, results, the explicit demo teacher endpoint, and the authenticated live teacher endpoint. Interactive documentation is available at `/api/docs`.

## Configuration

Python/FastAPI values are documented in the root `.env.example`:

- `GEMINI_API_KEY`: optional for fallback-only operation; required for live Gemini generation.
- `ASSESSMENT_ANALYTICS_DB_PATH`: optional durable analytics path; defaults to `assessment_analytics.db`.
- `TEACHER_DASHBOARD_TOKEN`: required as `Authorization: Bearer ...` for `GET /api/teacher/live`.
- `WEB_ORIGINS`: comma-separated credentialed CORS origins; defaults to `http://localhost:3000`.
- `LIVE_GENERATION_COOLDOWN_SECONDS`: provider cooldown after structured transient failures; defaults to 120 seconds.

The token configured for FastAPI must match the server-only `TEACHER_DASHBOARD_TOKEN` used by the Next.js proxy. Never expose it through a `NEXT_PUBLIC_*` variable.

## Runtime behavior and persistence

Live generation uses the existing Chroma/Gemini pipeline when its dependencies are configured. Known operational generation failures fall back to the verified question pool; failures do not advance the staircase.

Adaptive state persists in `student_state.db`. Confirmed attempt analytics persist separately in `assessment_analytics.db`, including after API restart. The in-memory `AttemptStore` is intentionally process-local: active questions, frozen option mappings, response caches, locks, and ChunkSampler history are not restored after restart.

## Tests

The API tests inject generation behavior and do not call Gemini:

```powershell
.\.venv\Scripts\python.exe -m pytest api\tests -q
```
