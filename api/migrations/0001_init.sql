-- 404: Exam Not Found -- initial Supabase schema
-- Replaces: assessment_analytics.db (attempts, answers) and
-- student_state.db (student_state), both previously local SQLite files.

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('en', 'ar')),
    initial_difficulty INTEGER NOT NULL CHECK (initial_difficulty BETWEEN 1 AND 5),
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed')),
    created_at TEXT NOT NULL,
    completed_at TEXT NULL,
    final_difficulty INTEGER NULL CHECK (final_difficulty BETWEEN 1 AND 5),
    CHECK (
        (status = 'in_progress' AND completed_at IS NULL AND final_difficulty IS NULL)
        OR
        (status = 'completed' AND completed_at IS NOT NULL AND final_difficulty IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS answers (
    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id) ON DELETE RESTRICT,
    question_id TEXT NOT NULL,
    question_number INTEGER NOT NULL CHECK (question_number >= 1),
    language TEXT NOT NULL CHECK (language IN ('en', 'ar')),
    topic TEXT NOT NULL,
    question_text TEXT NOT NULL,
    selected_option_index INTEGER NOT NULL CHECK (selected_option_index >= 0),
    selected_answer_text TEXT NOT NULL,
    correct_answer_text TEXT NOT NULL,
    correct BOOLEAN NOT NULL,
    misconception TEXT NULL,
    difficulty_score INTEGER NOT NULL CHECK (difficulty_score BETWEEN 1 AND 5),
    requested_difficulty INTEGER NOT NULL CHECK (requested_difficulty BETWEEN 1 AND 5),
    adaptive_level_before INTEGER NOT NULL CHECK (adaptive_level_before BETWEEN 1 AND 5),
    adaptive_level_after INTEGER NULL CHECK (adaptive_level_after BETWEEN 1 AND 5),
    source_reference TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'failed')),
    created_at TEXT NOT NULL,
    confirmed_at TEXT NULL,
    PRIMARY KEY (attempt_id, question_id),
    CHECK (
        (status = 'confirmed' AND confirmed_at IS NOT NULL AND adaptive_level_after IS NOT NULL)
        OR
        (status IN ('pending', 'failed') AND confirmed_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_attempts_created ON attempts(created_at, attempt_id);
CREATE INDEX IF NOT EXISTS idx_answers_status_order ON answers(status, attempt_id, question_number, question_id);

CREATE TABLE IF NOT EXISTS student_state (
    student_id TEXT PRIMARY KEY,
    language TEXT NOT NULL,
    current_difficulty INTEGER NOT NULL,
    topic_index INTEGER NOT NULL DEFAULT 0,
    questions_answered INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0
);
