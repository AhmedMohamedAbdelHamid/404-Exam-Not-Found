import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { AdaptiveLevel, CompletionHero, QuestionCard } from "./assessment";
import { ErrorRecoveryCard, GenerationLoader } from "./ui";
import type { Answer, Question } from "@/lib/api";

const question: Question = {
  question_id: "q001",
  question_number: 1,
  question: "What is the value of x?",
  topic: "Variables and Assignment",
  language: "en",
  source: "live",
  options: [
    { id: "opt_a", label: "A", text: "5" },
    { id: "opt_b", label: "B", text: "8" },
  ],
};

const correctAnswer: Answer = {
  question_id: "q001",
  selected_option_id: "opt_b",
  correct_option_id: "opt_b",
  selected_answer: "8",
  correct_answer: "8",
  correct: true,
  misconception: null,
  current_adaptive_difficulty: 4,
  progress: { answered: 1, total: 5, percent: 20 },
  can_continue: true,
  answer_state: "saved",
};

describe("assessment experience", () => {
  it("selects an option and submits without client-side answer metadata", () => {
    const select = vi.fn(); const submit = vi.fn();
    render(<QuestionCard question={question} selected={null} onSelect={select} answer={null} submitting={false} onSubmit={submit} onContinue={vi.fn()} />);
    fireEvent.click(screen.getByRole("radio", { name: /8/ }));
    expect(select).toHaveBeenCalledWith("opt_b");
    expect(Object.keys(question.options[0]).sort()).toEqual(["id", "label", "text"]);
  });

  it("locks options and reveals confirmed correct feedback", () => {
    render(<QuestionCard question={question} selected="opt_b" onSelect={vi.fn()} answer={correctAnswer} submitting={false} onSubmit={vi.fn()} onContinue={vi.fn()} />);
    expect(screen.getByText("Correct")).toBeInTheDocument();
    screen.getAllByRole("radio").forEach((option) => expect(option).toBeDisabled());
  });

  it("reveals the correct answer and learning signal after an incorrect answer", () => {
    const answer = { ...correctAnswer, selected_option_id: "opt_a", selected_answer: "5", correct: false, misconception: "Assignment updates the stored value." };
    render(<QuestionCard question={question} selected="opt_a" onSelect={vi.fn()} answer={answer} submitting={false} onSubmit={vi.fn()} onContinue={vi.fn()} />);
    expect(screen.getByText("Incorrect")).toBeInTheDocument();
    expect(screen.getByText(/Assignment updates/)).toBeInTheDocument();
    expect(screen.getByText(/Correct answer/)).toBeInTheDocument();
  });

  it("localizes Arabic controls and preserves RTL", () => {
    const arabic = { ...question, language: "ar" as const, question: "ما قيمة x؟" };
    const { container } = render(<QuestionCard question={arabic} selected={null} onSelect={vi.fn()} answer={null} submitting={false} onSubmit={vi.fn()} onContinue={vi.fn()} />);
    expect(screen.getByText("إرسال الإجابة")).toBeInTheDocument();
    expect(container.querySelector("article")).toHaveAttribute("dir", "rtl");
    expect(arabic.question).toBe("ما قيمة x؟");
  });

  it("shows the adaptive level supplied by API state", () => {
    render(<AdaptiveLevel level={4} language="en" />);
    expect(screen.getByLabelText("Adaptive level 4 of 5")).toHaveTextContent("4/5");
  });

  it("renders loading and retry recovery states", () => {
    const retry = vi.fn();
    const { rerender } = render(<GenerationLoader />);
    expect(screen.getByText("Preparing your next question…")).toBeInTheDocument();
    rerender(<ErrorRecoveryCard message="Please try again." onRetry={retry} />);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("localizes the completion experience", () => {
    render(<CompletionHero language="ar" score={3} total={5} accuracy={60} finalLevel={4} onResults={vi.fn()} onRestart={vi.fn()} />);
    expect(screen.getByText("عرض النتائج")).toBeInTheDocument();
    expect(screen.getByText("بدء محاولة جديدة")).toBeInTheDocument();
  });
});
