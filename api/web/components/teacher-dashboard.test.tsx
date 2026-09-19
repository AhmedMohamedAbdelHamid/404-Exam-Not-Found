import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { TeacherDashboard } from "./teacher-dashboard";
import type { TeacherLive } from "@/lib/api";
import { liveTeacherData } from "@/test/teacher-fixture";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null, CartesianGrid: () => null, Tooltip: () => null, XAxis: () => null, YAxis: () => null,
}));

describe("TeacherDashboard", () => {
  it("renders durable live metrics without a demo label", () => {
    render(<TeacherDashboard data={liveTeacherData} />);
    expect(screen.getByText("LIVE CLASS DATA")).toBeInTheDocument();
    expect(screen.queryByText(/DEMO CLASS DATA/i)).not.toBeInTheDocument();
    expect(screen.getByText("57.1%")).toBeInTheDocument();
    expect(screen.getByText("Variables and Assignment")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("In progress")).toBeInTheDocument();
  });

  it("renders Arabic values, all difficulty levels, and separate attempt rows", () => {
    render(<TeacherDashboard data={liveTeacherData} />);
    expect(screen.getAllByText("طالب ١").length).toBeGreaterThan(0);
    expect(screen.getAllByText("الحلقات").length).toBeGreaterThan(0);
    expect(screen.getAllByText("يخلط بين قيمة المتغير والنص").length).toBeGreaterThan(0);
    expect(screen.getByText("Level 1")).toBeInTheDocument();
    expect(screen.getByText("Level 5")).toBeInTheDocument();
    expect(screen.getByText(/11111111/)).toBeInTheDocument();
    expect(screen.getByText(/22222222/)).toBeInTheDocument();
  });

  it("shows an honest live empty state without fabricated metrics", () => {
    const empty: TeacherLive = {
      ...liveTeacherData,
      data_status: "empty",
      summary: { total_students: 0, total_attempts: 0, completed_attempts: 0, in_progress_attempts: 0, completion_rate: 0, confirmed_answers: 0, correct_answers: 0, incorrect_answers: 0, overall_accuracy: 0, average_score: 0, average_difficulty: 0, misconception_count: 0 },
      topics: [], misconceptions: [], students: [],
      score_distribution: liveTeacherData.score_distribution.map((row) => ({ ...row, attempts: 0 })),
      difficulty: liveTeacherData.difficulty.map((row) => ({ ...row, count: 0 })),
    };
    render(<TeacherDashboard data={empty} />);
    expect(screen.getByText("Your class analytics will appear here.")).toBeInTheDocument();
    expect(screen.getByText(/no persisted student attempts yet/i)).toBeInTheDocument();
    expect(screen.queryByText("Overall accuracy")).not.toBeInTheDocument();
    expect(screen.queryByText(/DEMO/i)).not.toBeInTheDocument();
  });
});
