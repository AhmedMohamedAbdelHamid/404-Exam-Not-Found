# 404 — Exam Not Found

Exam Not Found is a textbook-grounded adaptive MCQ platform for English and Arabic programming assessments. It combines local Chroma retrieval with Gemini question generation when available, validated fallback questions when live services are unavailable, and a 1–5 adaptive difficulty staircase.

The primary experience is a premium Next.js application backed by FastAPI. Submitted assessment analytics are stored durably for a protected live Teacher Dashboard. The completed Streamlit application remains available as a compatibility frontend.

## Architecture

```text
Browser / Next.js
        |
        v
FastAPI bridge
        |
        +-- textbook retrieval + question generation
        +-- adaptive staircase (student_state.db)
        +-- durable assessment analytics (assessment_analytics.db)
        +-- Chroma textbook index (chroma_db/)

Teacher browser
        -> authenticated Next.js server route
        -> protected FastAPI teacher endpoint
        -> assessment_analytics.db
```

Answer keys remain on the Python server until an answer is submitted. The browser receives randomized, sanitized question options.

## Prerequisites

- Windows PowerShell (the documented and tested command environment)
- Python 3.11 recommended
- Node.js 20.9 or newer
- npm

## Fresh install

From the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r api\requirements.txt

cd web
npm ci
cd ..
```

Both Python requirement files are required. The root file supplies the generation, retrieval, Chroma, Gemini, and Streamlit dependencies; `api/requirements.txt` supplies FastAPI, its server, and API test dependencies.

## Environment setup

Create local environment files from the safe templates:

```powershell
Copy-Item .env.example .env
Copy-Item web\.env.example web\.env.local
```

Never commit `.env` or `web/.env.local`. `GEMINI_API_KEY` is optional: without it, the assessment uses verified fallback questions. Live teacher analytics require `TEACHER_DASHBOARD_TOKEN` in both files with the same value. `TEACHER_UI_ACCESS_TOKEN` belongs only in `web/.env.local` and protects the teacher access screen.

## Chroma and textbook retrieval

The source chunk JSON files are committed, but the Chroma index is generated locally and ignored by Git. From the repository root, build both English and Arabic collections with:

```powershell
.\.venv\Scripts\python.exe embed_to_chroma.py
```

This may download embedding models on first use. Live textbook retrieval requires `chroma_db/` with the `chunks_en` and `chunks_ar` collections. If retrieval, Gemini, or validation is unavailable, the application attempts its pre-verified backup pool rather than presenting an ungrounded answer as live generation.

## Run the premium application

Terminal 1, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
```

Terminal 2:

```powershell
cd web
npm run dev
```

- Student application: <http://localhost:3000>
- Teacher Dashboard: <http://localhost:3000/teacher>
- FastAPI documentation: <http://localhost:8000/api/docs>

## Production web build

Stop any running Next.js development server before building:

```powershell
cd web
npm run build
npm run start
```

Supply production environment variables through the deployment platform. Do not embed teacher or Gemini secrets in `NEXT_PUBLIC_*` variables.

## Legacy Streamlit frontend

The Streamlit implementation is retained for compatibility and regression testing. It is not the primary premium interface.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Persistence

- `student_state.db` stores adaptive language, topic, difficulty, and answer counters. It is local SQLite data and survives backend restarts.
- `assessment_analytics.db` stores durable premium attempts and confirmed answer analytics. It is local SQLite data and survives backend restarts.
- `chroma_db/` is the generated local textbook retrieval index.
- Active premium `AttemptStore` state is process-local. Current questions, option mappings, ChunkSampler history, and other in-progress browser-attempt state are not restored after a FastAPI restart. Durable analytics already written remain available.

All local databases and the Chroma directory are ignored by Git.

## Tests without Gemini

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest api\tests -q
.\.venv\Scripts\python.exe -m pytest tests\test_c5_frontend.py -q

cd web
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

These suites use mocks for generation and do not require Gemini calls.

## Security and deployment notes

- Gemini and teacher secrets are server-only. Only `NEXT_PUBLIC_API_BASE_URL` is browser-visible.
- The Teacher Dashboard requires a backend Bearer token and a separate Next.js teacher-access token.
- Configure `WEB_ORIGINS` for the deployed web origin; do not use an unrestricted credentialed CORS policy.
- Use HTTPS in production so the teacher session cookie is transmitted securely.
- Teacher access uses a shared-token MVP authentication model. Replace it with institutional identity and authorization before a broader production rollout.
- Do not commit environment files, databases, Chroma data, logs, or build artifacts.
