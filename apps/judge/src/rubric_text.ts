import type { RubricAnchor } from "@synergy/schemas";

export function formatRubricText(
  anchors: RubricAnchor[],
  filterDim?: string,
  excludeDims?: string[],
): string {
  const filtered = filterDim
    ? anchors.filter((a) => a.dimension === filterDim)
    : excludeDims
    ? anchors.filter((a) => !excludeDims.includes(a.dimension))
    : anchors;

  const byDim = new Map<string, RubricAnchor[]>();
  for (const a of filtered) {
    const list = byDim.get(a.dimension) ?? [];
    list.push(a);
    byDim.set(a.dimension, list);
  }

  const lines: string[] = [];
  for (const [, dimAnchors] of byDim) {
    for (const a of dimAnchors) {
      lines.push(`### ${a.dimension} — ${a.label} (band: ${a.band})`);
      lines.push(a.description);
      lines.push(`Positive signals: ${a.positive_signals.join("; ")}`);
      lines.push(`Negative signals: ${a.negative_signals.join("; ")}`);
      lines.push(`Example: ${a.example_chat_snippet}`);
      lines.push("");
    }
  }
  return lines.join("\n");
}
