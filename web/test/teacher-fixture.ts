import type { TeacherLive } from "@/lib/api";

export const liveTeacherData: TeacherLive = {
  data_source: "live",
  data_status: "available",
  summary: {
    total_students: 2, total_attempts: 3, completed_attempts: 2, in_progress_attempts: 1,
    completion_rate: 66.7, confirmed_answers: 7, correct_answers: 4, incorrect_answers: 3,
    overall_accuracy: 57.1, average_score: 2, average_difficulty: 3.1, misconception_count: 2,
  },
  score_distribution: [
    { band: "0–20%", attempts: 0 }, { band: "21–40%", attempts: 1 }, { band: "41–60%", attempts: 1 },
    { band: "61–80%", attempts: 0 }, { band: "81–100%", attempts: 0 },
  ],
  misconceptions: [{ misconception: "يخلط بين قيمة المتغير والنص", count: 2 }],
  topics: [{ topic: "variables and assignment", attempted: 4, correct: 2, incorrect: 2, accuracy: 50 }, { topic: "الحلقات", attempted: 3, correct: 2, incorrect: 1, accuracy: 66.7 }],
  difficulty: [1, 2, 3, 4, 5].map((difficulty) => ({ difficulty, count: difficulty === 3 ? 7 : 0 })),
  students: [
    { attempt_id: "11111111-1111-4111-8111-111111111111", student_id: "طالب ١", language: "ar", status: "completed", answered: 5, correct: 3, incorrect: 2, accuracy: 60, initial_difficulty: 3, final_difficulty: 4, created_at: "2026-09-17T10:00:00Z", completed_at: "2026-09-17T10:20:00Z" },
    { attempt_id: "22222222-2222-4222-8222-222222222222", student_id: "student-2", language: "en", status: "in_progress", answered: 2, correct: 1, incorrect: 1, accuracy: 50, initial_difficulty: 3, final_difficulty: null, created_at: "2026-09-17T11:00:00Z", completed_at: null },
  ],
};
