import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { TeacherDashboard } from "./teacher-dashboard";
import type { TeacherDemo } from "@/lib/api";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null, CartesianGrid: () => null, Tooltip: () => null, XAxis: () => null, YAxis: () => null,
}));

const demo: TeacherDemo = {
  label: "DEMO CLASS DATA · NOT LIVE",
  summary: { students: 10, completion_rate: 80, completed_assessments: 8, average_accuracy: 72, average_correct: 3.6, average_total: 5, distinct_misconceptions: 4, average_difficulty: 3.1 },
  score_distribution: [{ band: "61–80%", students: 4 }],
  misconceptions: [{ label: "Treats the range stop boundary as inclusive even when Python excludes the final value", occurrences: 3 }],
  topics: [{ topic: "variables and assignment", error_rate: 45 }],
  difficulty: [{ difficulty: 3, count: 12 }],
  students: [{ student_id: "demo-01", student: "Amina Hassan", completed: true, score: "4 / 5", accuracy: 80, correct: 4, incorrect: 1, main_weak_topic: "variables and assignment" }],
  insights: [],
};

describe("TeacherDashboard", () => {
  it("clearly labels deterministic demo data and renders its student table", () => {
    render(<TeacherDashboard data={demo} />);
    expect(screen.getByText("DEMO CLASS DATA · NOT LIVE")).toBeInTheDocument();
    expect(screen.getByText("Amina Hassan")).toBeInTheDocument();
    expect(screen.getByText("Misconception signals")).toBeInTheDocument();
    expect(screen.getAllByText("Variables and Assignment").length).toBeGreaterThan(0);
    expect(screen.getByText("Full signal descriptions")).toBeInTheDocument();
    expect(screen.getByText("Level 5")).toBeInTheDocument();
  });
});
