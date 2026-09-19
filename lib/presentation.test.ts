import { accuracyTieCount, formatTopicName, summarizeSignal } from "./presentation";

describe("presentation helpers", () => {
  it("formats raw topic names without changing their source values", () => {
    const raw = "variables and assignment";
    expect(formatTopicName(raw)).toBe("Variables and Assignment");
    expect(raw).toBe("variables and assignment");
  });

  it("summarizes long signals at a word boundary", () => {
    const full = "Confuses the exclusive range stop boundary with an inclusive final value";
    const summary = summarizeSignal(full, 42);
    expect(summary.endsWith("…")).toBe(true);
    expect(full.startsWith(summary.slice(0, -1))).toBe(true);
  });

  it("counts honest strongest and weakest ties", () => {
    const topics = [{ accuracy: 80 }, { accuracy: 80 }, { accuracy: 40 }, { accuracy: 40 }];
    expect(accuracyTieCount(topics, "highest")).toBe(2);
    expect(accuracyTieCount(topics, "lowest")).toBe(2);
  });
});
