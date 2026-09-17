import { StrictMode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import type { Attempt, Question } from "@/lib/api";
import { ApiError } from "@/lib/api";
import AssessmentPage from "./page";

const mocks = vi.hoisted(() => ({
  getAttempt: vi.fn(),
  getNextQuestion: vi.fn(),
  getResults: vi.fn(),
  submitAnswer: vi.fn(),
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ attemptId: "attempt-1" }),
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      getAttempt: mocks.getAttempt,
      getNextQuestion: mocks.getNextQuestion,
      getResults: mocks.getResults,
      submitAnswer: mocks.submitAnswer,
    },
  };
});

const question: Question = {
  question_id: "q001",
  question_number: 1,
  question: "Which value is assigned to x?",
  topic: "variables and assignment",
  language: "en",
  source: "fallback",
  options: [
    { id: "opt_1", label: "A", text: "3" },
    { id: "opt_2", label: "B", text: "5" },
  ],
};

function attempt(currentQuestion: Question | null): Attempt {
  return {
    attempt_id: "attempt-1",
    student_id: "qa_student",
    language: "en",
    current_adaptive_difficulty: 3,
    progress: { answered: 0, total: 5, percent: 0 },
    runtime: {
      pipeline: "configured",
      chroma_configured: true,
      collection_available: true,
      gemini_configured: true,
      fallback_available: true,
      message: "Configured",
    },
    current_question: currentQuestion,
    current_answer: null,
    answer_state: currentQuestion ? "open" : null,
    can_request_next: currentQuestion === null,
    complete: false,
    created_at: "2026-09-16T00:00:00Z",
  };
}

describe("assessment route question initialization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("makes one automatic next request under Strict Mode and never refetches on rerender", async () => {
    let delivered = false;
    mocks.getAttempt.mockImplementation(async () => attempt(delivered ? question : null));
    mocks.getNextQuestion.mockImplementation(async () => {
      delivered = true;
      return {
        status: "question",
        question,
        current_adaptive_difficulty: 3,
        progress: { answered: 0, total: 5, percent: 0 },
        complete: false,
      };
    });

    const view = render(<StrictMode><AssessmentPage /></StrictMode>);
    expect(await screen.findByText("Which value is assigned to x?")).toBeInTheDocument();
    expect(mocks.getNextQuestion).toHaveBeenCalledTimes(1);

    view.rerender(<StrictMode><AssessmentPage /></StrictMode>);
    await waitFor(() => expect(mocks.getNextQuestion).toHaveBeenCalledTimes(1));
  });

  it("does not automatically retry a failed fetch and retries once on explicit action", async () => {
    mocks.getAttempt.mockResolvedValue(attempt(null));
    mocks.getNextQuestion.mockRejectedValue(
      new ApiError(
        "GENERATION_UNAVAILABLE",
        "We couldn't prepare the next question right now.",
        true,
        503,
      ),
    );

    render(<StrictMode><AssessmentPage /></StrictMode>);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't prepare the next question right now.",
    );
    expect(mocks.getNextQuestion).toHaveBeenCalledTimes(1);

    await new Promise((resolve) => window.setTimeout(resolve, 20));
    expect(mocks.getNextQuestion).toHaveBeenCalledTimes(1);

    const retry = screen.getByRole("button", { name: "Retry" });
    expect(retry).toBeVisible();
    fireEvent.click(retry);
    await waitFor(() => expect(mocks.getNextQuestion).toHaveBeenCalledTimes(2));
  });
});
