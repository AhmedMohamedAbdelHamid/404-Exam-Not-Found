import { render } from "@testing-library/react";
import { MixedText } from "./mixed-text";

describe("MixedText", () => {
  it("keeps English text unchanged", () => {
    const source = "What does print(x) return?";
    const { container } = render(<MixedText text={source} language="en" />);
    expect(container.textContent).toBe(source);
    expect(container.querySelector("code")).toHaveTextContent("print(x)");
  });

  it("renders Arabic safely while isolating code left-to-right", () => {
    const source = "ماذا تطبع الشيفرة؟ x = 5 print(x)";
    const { container } = render(<MixedText text={source} language="ar" />);
    expect(container.querySelector("span")).toHaveAttribute("dir", "rtl");
    expect(container.querySelector('code[dir="ltr"]')).toBeInTheDocument();
    expect(container.textContent).toBe(source);
    expect(container.querySelector("script")).not.toBeInTheDocument();
  });

  it("styles multiple code expressions without changing the source string", () => {
    const source = "What does the following code print? x = 5 x = x + 3 print(x)";
    const { container } = render(<MixedText text={source} language="en" />);
    expect(container.textContent).toBe(source);
    expect(container.querySelectorAll("code")).toHaveLength(3);
  });

  it("treats markup-like generated content as text, not HTML", () => {
    const source = '<img src=x onerror="alert(1)"> safe';
    const { container } = render(<MixedText text={source} language="ar" />);
    expect(container.textContent).toBe(source);
    expect(container.querySelector("img")).not.toBeInTheDocument();
  });
});
