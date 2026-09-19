# Exam Not Found — Premium web application

The Next.js App Router client provides the student assessment, results report, and protected live Teacher Dashboard. Student assessment requests go to FastAPI; teacher requests pass through authenticated same-origin Next.js server routes.

## Install and configure

```powershell
cd web
npm ci
Copy-Item .env.example .env.local
```

`web/.env.local` needs one variable:

- `NEXT_PUBLIC_API_BASE_URL`: the URL of the FastAPI backend (the browser calls it directly).

Never commit `.env.local`.

## Run

Start FastAPI on port 8000 first, then:

```powershell
npm run dev
```

- Student application: <http://localhost:3000/>
- Teacher Dashboard: <http://localhost:3000/teacher>

The teacher dashboard has no login: `/teacher` loads `GET /api/teacher/live` from the FastAPI backend directly, so anyone with the URL can view it.

## Quality and production commands

```powershell
npm test -- --run
npm run typecheck
npm run lint
npm run build
npm run start
```

Stop `npm run dev` before running a production build because both commands use the `.next` output directory. Production secrets must be supplied securely by the deployment environment.
