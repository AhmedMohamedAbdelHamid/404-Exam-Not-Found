import type { Language } from "@/lib/api";

const ltrRun = /[A-Za-z0-9_][A-Za-z0-9_ \t=+\-*/%<>()\[\]{},.:;'"\\]*/g;
const codeMarker = /[_=+\-*/%<>()\[\]{}'"`]|\d|\b(?:print|def|return|for|while|if|else|True|False|None)\b/;
const codeRun = /\b(?:[A-Za-z_]\w*\s*(?:==|!=|<=|>=|=)\s*(?:[A-Za-z_]\w*|\d+)(?:\s*[+\-*/%]\s*(?:[A-Za-z_]\w*|\d+))?|[A-Za-z_]\w*\([^()\n]*\)|(?:def|return|for|while|if|elif|else)\b[^\n?.!،؛]*)/g;

function renderArabicPlain(text: string, keyPrefix: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  for (const match of text.matchAll(ltrRun)) {
    const index = match.index ?? 0;
    if (index > cursor) parts.push(text.slice(cursor, index));
    const fragment = match[0];
    parts.push(
      <bdi key={`${keyPrefix}-${index}-${fragment}`} dir="ltr" className={codeMarker.test(fragment) ? "code-fragment" : "ltr-fragment"}>
        {fragment}
      </bdi>,
    );
    cursor = index + fragment.length;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts;
}

export function MixedText({ text, language, className = "" }: { text: string; language: Language; className?: string }) {
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  for (const match of text.matchAll(codeRun)) {
    const index = match.index ?? 0;
    if (index > cursor) {
      const plain = text.slice(cursor, index);
      parts.push(...(language === "ar" ? renderArabicPlain(plain, `plain-${cursor}`) : [plain]));
    }
    const fragment = match[0];
    parts.push(
      <code key={`code-${index}-${fragment}`} dir="ltr" className="code-fragment">
        {fragment}
      </code>,
    );
    cursor = index + fragment.length;
  }
  if (cursor < text.length) {
    const plain = text.slice(cursor);
    parts.push(...(language === "ar" ? renderArabicPlain(plain, `tail-${cursor}`) : [plain]));
  }
  return <span dir={language === "ar" ? "rtl" : "auto"} className={`mixed-text ${className}`}>{parts.length ? parts : text}</span>;
}
