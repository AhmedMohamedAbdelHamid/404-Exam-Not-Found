const minorWords = new Set(["and", "or", "of", "the", "to", "in", "for"]);

export function formatTopicName(topic: string): string {
  return topic
    .trim()
    .split(/\s+/)
    .map((word, index) => {
      const normalized = word.toLocaleLowerCase("en");
      if (index > 0 && minorWords.has(normalized)) return normalized;
      return normalized ? normalized[0].toLocaleUpperCase("en") + normalized.slice(1) : normalized;
    })
    .join(" ");
}

export function summarizeSignal(signal: string, limit = 54): string {
  const normalized = signal.trim().replace(/\s+/g, " ");
  if (normalized.length <= limit) return normalized;
  const candidate = normalized.slice(0, limit + 1);
  const lastSpace = candidate.lastIndexOf(" ");
  const end = lastSpace >= Math.floor(limit * 0.65) ? lastSpace : limit;
  return `${normalized.slice(0, end).trimEnd()}…`;
}

export function accuracyTieCount(
  topics: Array<{ accuracy: number }>,
  edge: "highest" | "lowest",
): number {
  if (!topics.length) return 0;
  const accuracies = topics.map((topic) => topic.accuracy);
  const target = edge === "highest" ? Math.max(...accuracies) : Math.min(...accuracies);
  return topics.filter((topic) => topic.accuracy === target).length;
}
