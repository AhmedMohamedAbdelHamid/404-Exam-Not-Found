# Exam Not Found — Premium web application

The Next.js App Router client provides the student assessment, results report, and protected live Teacher Dashboard. Student assessment requests go to FastAPI; teacher requests pass through authenticated same-origin Next.js server routes.

## Install and configure

```powershell
cd web
npm ci
Copy-Item .env.example .env.local
```

`web/.env.local` supports both browser-exposed and server-only Next.js configuration:

- Browser-exposed: `NEXT_PUBLIC_API_BASE_URL`
- Server-only: `API_INTERNAL_BASE_URL`
- Server-only: `TEACHER_DASHBOARD_TOKEN`
- Server-only: `TEACHER_UI_ACCESS_TOKEN`

Only variables prefixed with `NEXT_PUBLIC_` enter the browser bundle. The teacher variables must never use that prefix. `TEACHER_DASHBOARD_TOKEN` must match the token configured for FastAPI; `TEACHER_UI_ACCESS_TOKEN` is a separate credential for the teacher access screen. Never commit `.env.local`.

## Run

Start FastAPI on port 8000 first, then:

```powershell
npm run dev
```

- Student application: <http://localhost:3000/>
- Teacher Dashboard: <http://localhost:3000/teacher>

The teacher credential is validated by `POST /api/teacher/session`, which sets a signed HttpOnly session cookie. Authenticated browser requests use the Next.js `GET /api/teacher/live` proxy; only that server route attaches the FastAPI Bearer token.

## Quality and production commands

```powershell
npm test -- --run
npm run typecheck
npm run lint
npm run build
npm run start
```

Stop `npm run dev` before running a production build because both commands use the `.next` output directory. Production secrets must be supplied securely by the deployment environment.
