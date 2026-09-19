import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import TeacherPage from "./page";
import { ApiError, teacherApi } from "@/lib/api";
import { liveTeacherData } from "@/test/teacher-fixture";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null, CartesianGrid: () => null, Tooltip: () => null, XAxis: () => null, YAxis: () => null,
}));

describe("TeacherPage live flow", () => {
  afterEach(() => vi.restoreAllMocks());

  it("loads live class data directly, with no access prompt", async () => {
    const getLive = vi.spyOn(teacherApi, "getLive").mockResolvedValue(liveTeacherData);
    render(<TeacherPage />);
    expect(await screen.findByText("LIVE CLASS DATA")).toBeInTheDocument();
    expect(screen.queryByLabelText("Access credential")).not.toBeInTheDocument();
    expect(screen.queryByText(/DEMO CLASS DATA/i)).not.toBeInTheDocument();
    expect(getLive).toHaveBeenCalledOnce();
  });

  it("renders a recoverable live error without silently substituting demo data", async () => {
    vi.spyOn(teacherApi, "getLive").mockRejectedValue(new ApiError("TEACHER_ANALYTICS_UNAVAILABLE", "Live teacher analytics is temporarily unavailable.", true, 503));
    render(<TeacherPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Live teacher analytics is temporarily unavailable.");
    expect(screen.queryByText(/DEMO CLASS DATA/i)).not.toBeInTheDocument();
    await waitFor(() => expect(teacherApi.getLive).toHaveBeenCalledTimes(1));
  });

  it("retries and recovers after a failed load", async () => {
    const user = userEvent.setup();
    vi.spyOn(teacherApi, "getLive")
      .mockRejectedValueOnce(new ApiError("TEACHER_ANALYTICS_UNAVAILABLE", "Live teacher analytics is temporarily unavailable.", true, 503))
      .mockResolvedValueOnce(liveTeacherData);
    render(<TeacherPage />);
    await user.click(await screen.findByRole("button", { name: /retry/i }));
    expect(await screen.findByText("LIVE CLASS DATA")).toBeInTheDocument();
  });
});
