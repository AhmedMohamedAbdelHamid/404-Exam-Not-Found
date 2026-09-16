# Exam Not Found — API bridge

The FastAPI bridge consumes the existing assessment backend without changing its contracts. Attempts are process-local; adaptive progress remains in the backend SQLite store.

```powershell
.\.venv\Scripts\python.exe -m pip install -r api\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
```

Development CORS defaults to `http://localhost:3000`. Override it with a comma-separated `WEB_ORIGINS` value. The existing root `.env` remains the only location for `GEMINI_API_KEY`.
