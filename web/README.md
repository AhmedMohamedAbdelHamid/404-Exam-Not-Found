# Exam Not Found — Web

The premium client is a standalone Next.js application. It communicates only with the FastAPI bridge; Gemini credentials and answer keys never enter the browser bundle.

```powershell
Copy-Item .env.example .env.local
npm install
npm run dev
```

The default API base URL is `http://localhost:8000`. Only browser-safe configuration belongs in `.env.local`.

Quality checks:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```
