"""
Parse Ritesh_Gemini.pdf into turns, run SAF stages 1-4, print visual report.
"""
from __future__ import annotations
import json, re, sys, io
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[2]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PDF_PATH = Path(__file__).parents[2] / "gold_standard/chats/Ritesh_Gemini.pdf"
OUT_PATH = Path(__file__).parents[2] / "gold_standard/chats/ritesh_gemini.json"

# ── Extract PDF text ──────────────────────────────────────────────────────────
import fitz
doc = fitz.open(str(PDF_PATH))
full_text = "\n".join(page.get_text() for page in doc)

# ── Clean noise ───────────────────────────────────────────────────────────────
full_text = re.sub(r"Exported with AI Exporter\s*\n\s*\d+ / \d+", "", full_text)
full_text = re.sub(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s*$", "", full_text, flags=re.M)

# ── Turn marker pattern ───────────────────────────────────────────────────────
# Matches both "You Asked" and "Gemini 3.1 Pro" / "Gemini 3 Flash" etc.
MARKER = re.compile(
    r"^(You Asked|Gemini[\s\d.]*(?:Flash|Pro|Ultra|Nano)?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Split on markers, keeping marker text
parts = []
prev_end = 0
for m in MARKER.finditer(full_text):
    if m.start() > prev_end:
        parts.append(("__content__", full_text[prev_end:m.start()]))
    parts.append(("__marker__", m.group(0).strip()))
    prev_end = m.end()
if prev_end < len(full_text):
    parts.append(("__content__", full_text[prev_end:]))

# Pair markers with their following content
turns_raw: list[dict] = []
i = 0
while i < len(parts):
    kind, text = parts[i]
    if kind == "__marker__":
        content_parts = []
        j = i + 1
        while j < len(parts) and parts[j][0] == "__content__":
            content_parts.append(parts[j][1])
            j += 1
        content = " ".join(content_parts).strip()
        # Collapse whitespace runs
        content = re.sub(r"\n{3,}", "\n\n", content).strip()
        if content:
            role = "user" if "you asked" in text.lower() else "assistant"
            turns_raw.append({"role": role, "content": content})
        i = j
    else:
        i += 1

print(f"Extracted {len(turns_raw)} turns "
      f"({sum(1 for t in turns_raw if t['role']=='user')} human, "
      f"{sum(1 for t in turns_raw if t['role']=='assistant')} AI)",
      file=sys.stderr)

# Save JSON
OUT_PATH.write_text(json.dumps({
    "id": "ritesh-gemini",
    "platform": "gemini",
    "turns": [{"role": t["role"], "content": t["content"], "turn_index": i}
              for i, t in enumerate(turns_raw)],
    "annotations": []
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved to {OUT_PATH}", file=sys.stderr)

# ── SAF pipeline stages 1-4 ───────────────────────────────────────────────────
from saf_chat_analyser.src.parser.transcript_parser import parse_transcript
from saf_chat_analyser.src.tagger.intent_tagger import tag_turns, intent_counts
from saf_chat_analyser.src.tagger.turn_classifier import compute_as_ratios
from saf_chat_analyser.src.tagger.phase_classifier import classify_phases
from saf_chat_analyser.src.metrics.composite_metrics import compute_metrics

with patch("saf_chat_analyser.src.metrics.composite_metrics._compute_semantic_distance",
           return_value=None):
    turns = parse_transcript(turns_raw)
    tagged = tag_turns(turns)
    counts = intent_counts(tagged)
    phases = classify_phases(tagged)
    ratios = compute_as_ratios(tagged)
    metrics = compute_metrics(turns, tagged)

h_turns = [t for t in turns if t.role == "human"]
a_turns = [t for t in turns if t.role == "ai"]

# ── Visual report ─────────────────────────────────────────────────────────────
W = 72

def hbar(value: float | None, width: int = 36, char: str = "#") -> str:
    if value is None:
        return " [N/A]"
    filled = max(0, int(round(value * width)))
    return f" [{char * filled}{'-' * (width - filled)}] {value:.3f}"

def section(title: str) -> None:
    pad = W - len(title) - 5
    print(f"\n  {title} " + "-" * max(pad, 4))

print()
print("=" * W)
print("  SAF TIER-1 ANALYSIS  --  Ritesh / Gemini  (Stages 1-4, no LLM)")
print("=" * W)
print()
print(f"  Session turns : {metrics.session_turns}  |  Human: {len(h_turns)}  |  AI: {len(a_turns)}")
avg_words = sum(t.word_count for t in h_turns) / len(h_turns) if h_turns else 0
print(f"  Avg words/human turn: {avg_words:.0f}")

section("A/S Turn Partition  (§5.3.1)")
print(f"  A-turns (autonomous / low-info) {hbar(metrics.a_turn_ratio)}")
print(f"  S-turns (steered / constraint)  {hbar(metrics.s_turn_ratio)}")
note_as = "  Interpretation: "
if metrics.a_turn_ratio > 0.6:
    note_as += "User mostly lets AI run -- low steering, high dependency risk."
elif metrics.a_turn_ratio < 0.2:
    note_as += "Highly steered session -- every prompt constrains AI output."
else:
    note_as += "Mixed: user both delegates and guides."
print(note_as)

section("AILit/OECD Phase Distribution")
phase_order = [("MANAGE", "manage"), ("ENGAGE", "engage"),
               ("CREATE", "create"), ("DESIGN", "design")]
for label, key in phase_order:
    val = phases.get(key, 0.0)
    filled = max(0, int(round(val * 32)))
    print(f"  {label:<8} [{'#' * filled}{'-' * (32 - filled)}] {val:.3f}")

section("Intent Tag Frequencies  (human turns only)")
total_h = len(h_turns)
sorted_counts = sorted(counts.items(), key=lambda x: -x[1])
for tag, cnt in sorted_counts:
    if cnt > 0:
        pct = cnt / total_h if total_h else 0
        filled = max(0, int(pct * 32))
        print(f"  {tag:<18} {cnt:>4}  [{'#' * filled}{'-' * (32 - filled)}] {pct:.0%}")

section("Composite Behavioural Metrics")
metrics_rows = [
    ("verification_ratio",   metrics.verification_ratio,
     "VERIFY turns / AI turns — how often user challenges AI"),
    ("generative_q_ratio",   metrics.generative_query_ratio,
     "Generative queries / (gen+extractive) — depth of engagement"),
    ("attribution_gap",      metrics.attribution_gap,
     "Pure passive EXTRACT / total human turns — outsourcing proxy"),
    ("actualization_depth",  metrics.actualization_depth,
     "Scope-mod loops / task-decompose count"),
    ("iteration_depth",      metrics.iteration_depth,
     "Refinement turns / total human turns"),
]
for name, val, desc in metrics_rows:
    print(f"  {name:<22}{hbar(val)}")
    print(f"    [{desc}]")

section("Verification Trend  (first half vs second half)")
vr_f = metrics.vr_first_half
vr_s = metrics.vr_second_half
print(f"  First half  {hbar(vr_f)}")
print(f"  Second half {hbar(vr_s)}")
if vr_f is not None and vr_s is not None:
    if vr_f == 0 and vr_s == 0:
        print("  Trend: FLAT at zero -- no verification detected in either half.")
    elif vr_f > 0:
        delta = ((vr_s - vr_f) / vr_f) * 100
        trend = "DOWN (-)" if delta < -15 else "STABLE (~)" if abs(delta) <= 15 else "UP (+)"
        print(f"  Trend: {trend}  ({delta:+.1f}%)")

section("Deterministic Risk Signals")
vr          = metrics.verification_ratio or 0.0
engage_frac = phases.get("engage", 0.0)
ag          = metrics.attribution_gap or 0.0
manage_frac = phases.get("manage", 0.0)

signals = [
    ("explanation_trap",
     engage_frac > 0.5 and vr < 0.10,
     f"engage={engage_frac:.2f}, VR={vr:.3f}"),
    ("cognitive_debt",
     vr_f is not None and vr_s is not None
     and metrics.session_turns > 20
     and vr_f > 0 and vr_s < vr_f * 0.714,
     f"VR-first={vr_f}, VR-second={vr_s}"),
    ("high_attribution_gap",
     ag > 0.60,
     f"AG={ag:.3f}"),
    ("manage_dominated",
     manage_frac > 0.75,
     f"MANAGE phase = {manage_frac:.2f} (mostly passive task extraction)"),
    ("near_zero_verify",
     vr < 0.05,
     f"VR={vr:.3f} -- user almost never challenges AI"),
]
for name, fired, detail in signals:
    status = "!! FLAGGED" if fired else "  clear   "
    print(f"  [{status}] {name:<25}  ({detail})")

section("Interpretation")
high_extract = counts.get("EXTRACT", 0) / total_h > 0.4 if total_h else False
high_decomp  = counts.get("DECOMPOSE", 0) / total_h > 0.3 if total_h else False
low_verify   = vr < 0.10

lines = []
if manage_frac > 0.75:
    lines.append("Session is dominated by MANAGE phase: Ritesh is sending content to")
    lines.append("the AI and asking it to explain/process -- classic task-extraction mode.")
if high_decomp:
    lines.append("High DECOMPOSE rate suggests structured multi-part requests, consistent")
    lines.append("with a student sending slide decks for page-by-page explanation.")
if low_verify:
    lines.append("Near-zero VERIFY rate: Ritesh rarely pushes back on AI answers.")
    lines.append("This is a key signal -- the AI's explanations are accepted without scrutiny.")
if ag < 0.3:
    lines.append("Attribution gap is low -- Ritesh's prompts are contextually rich enough")
    lines.append("that the AI is not fully autonomous; inputs carry meaningful framing.")
for line in lines:
    print(f"  {line}")

print()
print("  NOTE: Full neuron scores (107 dimensions) and collaboration_quality_kappa")
print("  require GEMINI_API_KEY for Stage 5. The above covers all deterministic stages.")
print("=" * W)
