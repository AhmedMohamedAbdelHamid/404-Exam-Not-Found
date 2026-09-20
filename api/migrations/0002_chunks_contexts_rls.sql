-- 404: Exam Not Found -- Supabase schema, part 2.
-- Adds the two tables the Postgres-backed code needs beyond 0001_init.sql,
-- and turns on Row Level Security everywhere.
--
--   attempt_contexts  per-attempt session state (replaces the in-memory dict,
--                     which cannot be shared between Vercel function instances)
--   chunks            textbook chunks used for RAG retrieval (replaces the local
--                     Chroma index); loaded by `python api/seed_chunks.py`
--
-- RLS: the FastAPI backend connects with the direct Postgres role, which
-- bypasses RLS. Enabling RLS with no policies means nobody can read or write
-- these tables through Supabase's public REST/GraphQL API with the anon key.

CREATE TABLE IF NOT EXISTS attempt_contexts (
    attempt_id TEXT PRIMARY KEY,
    context JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('en', 'ar')),
    chunk_type TEXT,
    text TEXT NOT NULL,
    source_pages INTEGER[]
);

CREATE INDEX IF NOT EXISTS idx_chunks_topic_language ON chunks(topic, language);

ALTER TABLE attempts         ENABLE ROW LEVEL SECURITY;
ALTER TABLE answers          ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_state    ENABLE ROW LEVEL SECURITY;
ALTER TABLE attempt_contexts ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks           ENABLE ROW LEVEL SECURITY;
