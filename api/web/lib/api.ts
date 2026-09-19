import { z } from "zod";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const languageSchema = z.enum(["en", "ar"]);
const progressSchema = z.object({
  answered: z.number(),
  total: z.number(),
  percent: z.number(),
});
const runtimeSchema = z.object({
  pipeline: z.enum(["configured", "degraded"]),
  chroma_configured: z.boolean(),
  collection_available: z.boolean(),
  gemini_configured: z.boolean(),
  fallback_available: z.boolean(),
  message: z.string(),
});
export const questionSchema = z.object({
  question_id: z.string(),
  question_number: z.number(),
  question: z.string(),
  topic: z.string(),
  language: languageSchema,
  source: z.enum(["live", "fallback"]),
  options: z.array(z.object({ id: z.string(), label: z.string(), text: z.string() })),
});
export const answerSchema = z.object({
  question_id: z.string(),
  selected_option_id: z.string(),
  correct_option_id: z.string(),
  selected_answer: z.string(),
  correct_answer: z.string(),
  correct: z.boolean(),
  misconception: z.string().nullable(),
  current_adaptive_difficulty: z.number(),
  progress: progressSchema,
  can_continue: z.boolean(),
  answer_state: z.literal("saved"),
});
export const attemptSchema = z.object({
  attempt_id: z.string(),
  student_id: z.string(),
  language: languageSchema,
  current_adaptive_difficulty: z.number(),
  progress: progressSchema,
  runtime: runtimeSchema,
  current_question: questionSchema.nullable(),
  current_answer: answerSchema.nullable(),
  answer_state: z.enum(["open", "saving", "saved", "definitely_failed", "ambiguous"]).nullable(),
  can_request_next: z.boolean(),
  complete: z.boolean(),
  created_at: z.string(),
});
const nextQuestionSchema = z.object({
  status: z.enum(["question", "complete"]),
  question: questionSchema.nullable(),
  current_adaptive_difficulty: z.number(),
  progress: progressSchema,
  complete: z.boolean(),
});
const resultsSchema = z.object({
  attempt_id: z.string(),
  student_id: z.string(),
  language: languageSchema,
  complete: z.boolean(),
  summary: z.object({
    score: z.number(), attempted: z.number(), accuracy: z.number(), correct: z.number(),
    incorrect: z.number(), final_adaptive_difficulty: z.number(), average_question_difficulty: z.number(),
  }),
  topics: z.array(z.object({
    topic: z.string(), attempted: z.number(), correct: z.number(), incorrect: z.number(), accuracy: z.number(),
  })),
  strongest_topic: z.string().nullable(),
  needs_attention_topic: z.string().nullable(),
  misconceptions: z.array(z.object({ misconception: z.string(), occurrences: z.number(), topics: z.array(z.string()) })),
  question_review: z.array(z.object({
    question_id: z.string(), question_number: z.number(), question: z.string(), topic: z.string(),
    language: languageSchema, difficulty: z.number(), selected_answer: z.string(), correct_answer: z.string(),
    correct: z.boolean(), misconception: z.string().nullable(),
  })),
  adaptive_journey: z.array(z.object({ step: z.number(), difficulty: z.number() })),
});
const healthSchema = z.object({
  api_available: z.boolean(), chroma_configured: z.boolean(), english_collection_available: z.boolean(),
  arabic_collection_available: z.boolean(), gemini_configured: z.boolean(), fallback_available: z.boolean(),
  status: z.enum(["configured", "degraded", "fallback_available"]),
});
const teacherSchema = z.object({
  label: z.literal("DEMO CLASS DATA · NOT LIVE"),
  summary: z.record(z.string(), z.unknown()),
  score_distribution: z.array(z.record(z.string(), z.unknown())),
  misconceptions: z.array(z.record(z.string(), z.unknown())),
  topics: z.array(z.record(z.string(), z.unknown())),
  difficulty: z.array(z.record(z.string(), z.unknown())),
  students: z.array(z.record(z.string(), z.unknown())),
  insights: z.array(z.string()),
});

export const teacherLiveSchema = z.object({
  data_source: z.literal("live"),
  data_status: z.enum(["empty", "available"]),
  summary: z.object({
    total_students: z.number().int().nonnegative(),
    total_attempts: z.number().int().nonnegative(),
    completed_attempts: z.number().int().nonnegative(),
    in_progress_attempts: z.number().int().nonnegative(),
    completion_rate: z.number().min(0).max(100),
    confirmed_answers: z.number().int().nonnegative(),
    correct_answers: z.number().int().nonnegative(),
    incorrect_answers: z.number().int().nonnegative(),
    overall_accuracy: z.number().min(0).max(100),
    average_score: z.number().nonnegative(),
    average_difficulty: z.number().min(0).max(5),
    misconception_count: z.number().int().nonnegative(),
  }).strict(),
  topics: z.array(z.object({
    topic: z.string(),
    attempted: z.number().int().nonnegative(),
    correct: z.number().int().nonnegative(),
    incorrect: z.number().int().nonnegative(),
    accuracy: z.number().min(0).max(100),
  }).strict()),
  misconceptions: z.array(z.object({
    misconception: z.string(),
    count: z.number().int().nonnegative(),
  }).strict()),
  difficulty: z.array(z.object({
    difficulty: z.number().int().min(1).max(5),
    count: z.number().int().nonnegative(),
  }).strict()),
  score_distribution: z.array(z.object({
    band: z.string(),
    attempts: z.number().int().nonnegative(),
  }).strict()),
  students: z.array(z.object({
    attempt_id: z.string(),
    student_id: z.string(),
    language: languageSchema,
    status: z.enum(["in_progress", "completed"]),
    answered: z.number().int().nonnegative(),
    correct: z.number().int().nonnegative(),
    incorrect: z.number().int().nonnegative(),
    accuracy: z.number().min(0).max(100),
    initial_difficulty: z.number().int().min(1).max(5),
    final_difficulty: z.number().int().min(1).max(5).nullable(),
    created_at: z.string(),
    completed_at: z.string().nullable(),
  }).strict()),
}).strict();

export type Language = z.infer<typeof languageSchema>;
export type Question = z.infer<typeof questionSchema>;
export type Answer = z.infer<typeof answerSchema>;
export type Attempt = z.infer<typeof attemptSchema>;
export type Results = z.infer<typeof resultsSchema>;
export type Health = z.infer<typeof healthSchema>;
export type TeacherDemo = z.infer<typeof teacherSchema>;
export type TeacherLive = z.infer<typeof teacherLiveSchema>;

export class ApiError extends Error {
  constructor(public code: string, message: string, public retryable: boolean, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("NETWORK_UNAVAILABLE", "The assessment service is unavailable. Please retry.", true, 0);
  }
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    const parsed = z.object({ error: z.object({ code: z.string(), message: z.string(), retryable: z.boolean() }) }).safeParse(payload);
    if (parsed.success) {
      throw new ApiError(parsed.data.error.code, parsed.data.error.message, parsed.data.error.retryable, response.status);
    }
    throw new ApiError("REQUEST_FAILED", "We couldn't complete that request. Please retry.", response.status >= 500, response.status);
  }
  return schema.parse(payload);
}

export const api = {
  getHealth: () => request("/api/health", healthSchema),
  startAttempt: (studentId: string, language: Language) => request("/api/attempts", attemptSchema, {
    method: "POST", body: JSON.stringify({ student_id: studentId, language }),
  }),
  getAttempt: (attemptId: string) => request(`/api/attempts/${attemptId}`, attemptSchema),
  getNextQuestion: (attemptId: string) => request(`/api/attempts/${attemptId}/next`, nextQuestionSchema, { method: "POST" }),
  submitAnswer: (attemptId: string, questionId: string, selectedOptionId: string) => request(
    `/api/attempts/${attemptId}/answers`, answerSchema,
    { method: "POST", body: JSON.stringify({ question_id: questionId, selected_option_id: selectedOptionId }) },
  ),
  getResults: (attemptId: string) => request(`/api/attempts/${attemptId}/results`, resultsSchema),
  getTeacherDemo: () => request("/api/demo/teacher", teacherSchema),
};

export const teacherApi = {
  getLive: () => request("/api/teacher/live", teacherLiveSchema),
};
