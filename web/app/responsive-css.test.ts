import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("responsive presentation contract", () => {
  const css = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8");

  it("defines deliberate mobile, tablet, laptop, and wide-desktop breakpoints", () => {
    expect(css).toContain("@media (max-width: 640px)");
    expect(css).toContain("@media (min-width: 641px) and (max-width: 1023px)");
    expect(css).toContain("@media (min-width: 1024px) and (max-width: 1399px)");
    expect(css).toContain("@media (min-width: 1400px)");
  });

  it("contains page-overflow and intentional mobile-table safeguards", () => {
    expect(css).toMatch(/body\s*\{[^}]*overflow-x:\s*hidden/s);
    expect(css).toMatch(/\.student-table-wrap\s*\{[^}]*overflow-x:\s*auto/s);
    expect(css).toContain(".table-scroll-hint");
  });

  it("retains reduced-motion overrides", () => {
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});

describe("Next.js scrolling contract", () => {
  it("declares intentional smooth scrolling on the root element", () => {
    const layout = readFileSync(join(process.cwd(), "app", "layout.tsx"), "utf8");
    expect(layout).toContain('data-scroll-behavior="smooth"');
  });
});
