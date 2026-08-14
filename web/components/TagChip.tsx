import type { Tag } from "@/lib/types";

const PASTELS = [
  { bg: "var(--pale-blue)", ink: "var(--pale-blue-ink)" },
  { bg: "var(--pale-green)", ink: "var(--pale-green-ink)" },
  { bg: "var(--pale-yellow)", ink: "var(--pale-yellow-ink)" },
  { bg: "var(--pale-red)", ink: "var(--pale-red-ink)" },
];

function tone(category: string) {
  const n = [...category].reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return PASTELS[n % PASTELS.length];
}

export function TagChip({ tag }: { tag: Tag }) {
  const { bg, ink } = tone(tag.category);
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-[2px] font-mono text-[10px] uppercase tracking-[0.06em]"
      style={{ background: bg, color: ink, borderRadius: 9999 }}
    >
      {tag.tag}
      {tag.needs_review ? " ?" : ""}
      {tag.low_confidence ? " *" : ""}
    </span>
  );
}
