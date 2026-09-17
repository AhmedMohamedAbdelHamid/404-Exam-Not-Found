import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { TeacherAccess } from "./teacher-access";

describe("TeacherAccess", () => {
  it("provides an accessible credential form without prefilling or browser storage", async () => {
    const user = userEvent.setup();
    const unlock = vi.fn().mockResolvedValue(undefined);
    render(<TeacherAccess onUnlock={unlock} error={null} loading={false} />);
    const input = screen.getByLabelText("Access credential");
    expect(input).toHaveAttribute("type", "password");
    expect(input).toHaveValue("");
    await user.type(input, "teacher-secret");
    await user.click(screen.getByRole("button", { name: "Show credential" }));
    expect(input).toHaveAttribute("type", "text");
    await user.click(screen.getByRole("button", { name: "Unlock dashboard" }));
    expect(unlock).toHaveBeenCalledWith("teacher-secret");
  });

  it("announces a generic authentication error", () => {
    render(<TeacherAccess onUnlock={vi.fn()} error="The teacher credential is invalid." loading={false} />);
    expect(screen.getByRole("alert")).toHaveTextContent("The teacher credential is invalid.");
  });
});
