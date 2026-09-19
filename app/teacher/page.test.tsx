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

  it("starts locked, unlocks into live data, and logs out", async () => {
    const user = userEvent.setup();
    vi.spyOn(teacherApi, "getLive")
      .mockRejectedValueOnce(new ApiError("TEACHER_SESSION_REQUIRED", "Teacher access is required.", false, 401))
      .mockResolvedValueOnce(liveTeacherData);
    const unlock = vi.spyOn(teacherApi, "unlock").mockResolvedValue({ authenticated: true });
    const logout = vi.spyOn(teacherApi, "logout").mockResolvedValue({ authenticated: false });
    render(<TeacherPage />);
    const credential = await screen.findByLabelText("Access credential");
    await user.type(credential, "temporary-ui-token");
    await user.click(screen.getByRole("button", { name: "Unlock dashboard" }));
    expect(await screen.findByText("LIVE CLASS DATA")).toBeInTheDocument();
    expect(unlock).toHaveBeenCalledWith("temporary-ui-token");
    expect(screen.queryByText(/DEMO CLASS DATA/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Log out" }));
    expect(logout).toHaveBeenCalledOnce();
    expect(await screen.findByLabelText("Access credential")).toBeInTheDocument();
  });

  it("shows a generic wrong-credential error and never asks for demo data", async () => {
    const user = userEvent.setup();
    vi.spyOn(teacherApi, "getLive").mockRejectedValue(new ApiError("TEACHER_SESSION_REQUIRED", "Teacher access is required.", false, 401));
    vi.spyOn(teacherApi, "unlock").mockRejectedValue(new ApiError("TEACHER_ACCESS_DENIED", "The teacher credential is invalid.", false, 401));
    render(<TeacherPage />);
    await user.type(await screen.findByLabelText("Access credential"), "wrong");
    await user.click(screen.getByRole("button", { name: "Unlock dashboard" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The teacher credential is invalid.");
    expect(screen.queryByText(/DEMO/i)).not.toBeInTheDocument();
  });

  it("renders a recoverable live error without silently substituting demo data", async () => {
    vi.spyOn(teacherApi, "getLive").mockRejectedValue(new ApiError("TEACHER_SERVICE_UNAVAILABLE", "Live teacher analytics is temporarily unavailable.", true, 503));
    render(<TeacherPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Live teacher analytics is temporarily unavailable.");
    expect(screen.queryByText(/DEMO CLASS DATA/i)).not.toBeInTheDocument();
    await waitFor(() => expect(teacherApi.getLive).toHaveBeenCalledTimes(1));
  });
});
