import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { AssessmentStart } from "./assessment-start";

const { push, getHealth, startAttempt } = vi.hoisted(() => ({
  push: vi.fn(),
  getHealth: vi.fn().mockResolvedValue({
    api_available: true, chroma_configured: true, english_collection_available: true,
    arabic_collection_available: true, gemini_configured: true, fallback_available: true, status: "configured",
  }),
  startAttempt: vi.fn().mockResolvedValue({ attempt_id: "attempt-1" }),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: { ...original.api, getHealth, startAttempt } };
});

describe("AssessmentStart", () => {
  beforeEach(() => { push.mockClear(); startAttempt.mockClear(); sessionStorage.clear(); });

  it("validates an empty student identifier", async () => {
    render(<AssessmentStart />);
    fireEvent.click(screen.getByRole("button", { name: "Start assessment" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a student identifier");
    expect(startAttempt).not.toHaveBeenCalled();
  });

  it("trims the student ID and starts the English track", async () => {
    render(<AssessmentStart />);
    fireEvent.change(screen.getByLabelText("Student identifier"), { target: { value: "  qa_student  " } });
    fireEvent.click(screen.getByRole("button", { name: "Start assessment" }));
    await waitFor(() => expect(startAttempt).toHaveBeenCalledWith("qa_student", "en"));
    expect(push).toHaveBeenCalledWith("/assessment/attempt-1");
  });

  it("selects the Arabic track explicitly", async () => {
    render(<AssessmentStart />);
    fireEvent.change(screen.getByLabelText("Student identifier"), { target: { value: "qa_student" } });
    fireEvent.click(screen.getByRole("radio", { name: /العربية/ }));
    fireEvent.click(screen.getByRole("button", { name: "Start assessment" }));
    await waitFor(() => expect(startAttempt).toHaveBeenCalledWith("qa_student", "ar"));
  });

  it("uses accurate runtime readiness wording", async () => {
    render(<AssessmentStart />);
    expect(await screen.findByText("AI pipeline configured")).toBeInTheDocument();
    expect(screen.queryByText("Live generation ready")).not.toBeInTheDocument();
  });
});
