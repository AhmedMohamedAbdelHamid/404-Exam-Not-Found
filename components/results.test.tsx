import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { ResultsDashboard } from "./results";
import type { Results } from "@/lib/api";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: () => null, CartesianGrid: () => null, Tooltip: () => null, XAxis: () => null, YAxis: () => null,
}));

const report: Results = {
  attempt_id: "a1", student_id: "qa_student", language: "en", complete: true,
  summary: { score: 3, attempted: 5, accuracy: 60, correct: 3, incorrect: 2, final_adaptive_difficulty: 4, average_question_difficulty: 3 },
  topics: [
    { topic: "variables and assignment", attempted: 2, correct: 1, incorrect: 1, accuracy: 50 },
    { topic: "loops and conditionals", attempted: 2, correct: 1, incorrect: 1, accuracy: 50 },
  ],
  strongest_topic: "loops and conditionals", needs_attention_topic: "loops and conditionals",
  misconceptions: [{ misconception: "Assignment replaces a value.", occurrences: 1, topics: ["variables and assignment"] }],
  question_review: [{ question_id: "q1", question_number: 1, question: "What does the code print? x = 5 print(x)", topic: "variables and assignment", language: "en", difficulty: 3, selected_answer: "5", correct_answer: "8", correct: false, misconception: "Assignment replaces a value." }],
  adaptive_journey: [{ step: 0, difficulty: 3 }, { step: 1, difficulty: 4 }],
};

describe("ResultsDashboard", () => {
  it("renders dynamic metrics and incorrect-answer misconceptions", () => {
    const { container } = render(<ResultsDashboard results={report} />);
    expect(screen.getAllByText("60%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("3 / 5").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Assignment replaces a value.").length).toBeGreaterThan(0);
    expect(screen.getByText("Question review")).toBeInTheDocument();
    expect(screen.getAllByText("Variables and Assignment").length).toBeGreaterThan(0);
    expect(screen.getByText("One of your strongest topics")).toBeInTheDocument();
    expect(screen.getByText("Lowest-performing topic · tie resolved alphabetically")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Question 1, Incorrect" }));
    expect(container.querySelector(".review-question code")).toBeInTheDocument();
  });

  it("uses Arabic report labels without changing analytics", () => {
    render(<ResultsDashboard results={{ ...report, language: "ar" }} />);
    expect(screen.getByText("اكتمل التقييم")).toBeInTheDocument();
    expect(screen.getByText("الأداء حسب الموضوع")).toBeInTheDocument();
    expect(screen.getAllByText("60%").length).toBeGreaterThan(0);
  });
});
