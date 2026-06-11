"""
Parse Abhishek_1.pdf — ChatGPT export with right-aligned human bubbles.

Layout (confirmed by block inspection, A4 595pt wide):
  x0 > 380  → human turn start (right-side bubble, x0 ≈ 429)
  x0 ≈ 57.8 → AI response body
  x0 ≈ 81.8 → indented list item within AI response
  x0 = 24.0, sz = 8.0 → page timestamp margin noise → skip
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from unittest.mock import patch

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parents[2]))

import fitz

PDF_PATH = Path(__file__).parents[2] / "gold_standard/chats/Abhishek_1.pdf"
OUT_PATH = Path(__file__).parents[2] / "gold_standard/chats/abhishek_1.json"

HUMAN_X0_MIN = 380.0     # right-bubble threshold
NOISE_RE     = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}.*AM$|^\d+$", re.I)

doc = fitz.open(str(PDF_PATH))
print(f"Pages: {len(doc)}", file=sys.stderr)
page_height = doc[0].rect.height

# ── Collect all blocks ────────────────────────────────────────────────────────
all_blocks: list[tuple[float, float, float, str]] = []  # (abs_y, x0, sz, text)

for page_num, page in enumerate(doc):
    base_y = page_num * page_height
    for b in page.get_text("dict")["blocks"]:
        if "lines" not in b:
            continue
        x0   = b["bbox"][0]
        y0   = b["bbox"][1] + base_y
        # get dominant font size of block
        sizes = [sp["size"] for line in b["lines"] for sp in line["spans"] if sp["text"].strip()]
        sz   = max(sizes) if sizes else 12.0
        text = " ".join(
            sp["text"] for line in b["lines"] for sp in line["spans"]
        ).strip()
        if not text:
            continue
        # Skip margin timestamps and standalone page numbers
        if sz <= 9.0 and x0 < 40:
            continue
        if NOISE_RE.match(text):
            continue
        all_blocks.append((y0, x0, sz, text))

all_blocks.sort(key=lambda b: b[0])

# ── Walk blocks, split on human-x0 markers ───────────────────────────────────
turns_raw: list[dict] = []
current_role:   str | None = None
current_chunks: list[str] = []

def flush():
    if current_role and current_chunks:
        content = re.sub(r"\s{2,}", " ", " ".join(current_chunks)).strip()
        if content:
            turns_raw.append({"role": current_role, "content": content})

for y0, x0, sz, text in all_blocks:
    is_human = x0 >= HUMAN_X0_MIN

    if is_human:
        flush()
        current_role   = "user"
        current_chunks = [text]
    else:
        if current_role == "user":
            flush()
            current_role   = "assistant"
            current_chunks = [text]
        elif current_role == "assistant":
            current_chunks.append(text)
        else:
            current_role   = "assistant"
            current_chunks = [text]

flush()

h_c = sum(1 for t in turns_raw if t["role"] == "user")
a_c = sum(1 for t in turns_raw if t["role"] == "assistant")
print(f"Turns: {len(turns_raw)}  human={h_c}  ai={a_c}", file=sys.stderr)

OUT_PATH.write_text(json.dumps({
    "id": "abhishek-1",
    "platform": "chatgpt",
    "turns": [{"role": t["role"], "content": t["content"], "turn_index": i}
              for i, t in enumerate(turns_raw)],
    "annotations": []
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved {OUT_PATH}", file=sys.stderr)

# ── SAF pipeline stages 1-4 ──────────────────────────────────────────────────
from saf_chat_analyser.src.parser.transcript_parser import parse_transcript
from saf_chat_analyser.src.tagger.intent_tagger import tag_turns, intent_counts
from saf_chat_analyser.src.tagger.turn_classifier import compute_as_ratios
from saf_chat_analyser.src.tagger.phase_classifier import classify_phases
from saf_chat_analyser.src.metrics.composite_metrics import compute_metrics

with patch("saf_chat_analyser.src.metrics.composite_metrics._compute_semantic_distance",
           return_value=None):
    turns  = parse_transcript(turns_raw)
    tagged = tag_turns(turns)
    counts = intent_counts(tagged)
    phases = classify_phases(tagged)
    ratios = compute_as_ratios(tagged)
    metrics = compute_metrics(turns, tagged)

h_turns = [t for t in turns if t.role == "human"]
a_turns = [t for t in turns if t.role == "ai"]
wc_h    = sorted(t.word_count for t in h_turns) if h_turns else [0]

# ── Visual report ─────────────────────────────────────────────────────────────
W = 72

def hbar(val, width=36, ch="#"):
    if val is None: return " [N/A]"
    f = max(0, int(round(val * width)))
    return f" [{'#'*f}{'-'*(width-f)}] {val:.3f}"

def section(t):
    print(f"\n  {t} " + "-" * max(W - len(t) - 5, 4))

print()
print("=" * W)
print("  SAF TIER-1 ANALYSIS  --  Abhishek_1 / ChatGPT  (Stages 1-4, no LLM)")
print("=" * W)
print(f"\n  Session turns : {metrics.session_turns}  |  Human: {len(h_turns)}  |  AI: {len(a_turns)}")
avg_wc = sum(wc_h)/len(wc_h) if wc_h else 0
print(f"  Avg words/human turn: {avg_wc:.0f}  |  median: {wc_h[len(wc_h)//2]}  |  max: {wc_h[-1]}")

section("Human Turn Samples (first 10)")
for i, tt in enumerate([x for x in tagged if x.turn.role == "human"][:10]):
    preview = tt.turn.content[:80].replace("\n", " ")
    print(f"  [{i:02d}] [{tt.turn.word_count:3d}w] tags={tt.tags}  dominant={tt.dominant_intent}")
    print(f"       {preview}")

section("A/S Turn Partition  (§5.3.1)")
print(f"  A-turns (autonomous / low-info)  {hbar(metrics.a_turn_ratio)}")
print(f"  S-turns (steered / constraint)   {hbar(metrics.s_turn_ratio)}")

section("AILit/OECD Phase Distribution")
for lbl, key in [("MANAGE","manage"),("ENGAGE","engage"),("CREATE","create"),("DESIGN","design")]:
    v = phases.get(key, 0.0)
    f = max(0, int(round(v * 32)))
    print(f"  {lbl:<8} [{'#'*f}{'-'*(32-f)}] {v:.3f}")

section("Intent Tag Frequencies  (human turns only)")
th = len(h_turns)
for tag, cnt in sorted(counts.items(), key=lambda x: -x[1]):
    if cnt == 0: continue
    pct = cnt / th if th else 0
    f   = max(0, int(pct * 32))
    print(f"  {tag:<18} {cnt:>4}  [{'#'*f}{'-'*(32-f)}] {pct:.0%}")

section("Composite Behavioural Metrics")
rows = [
    ("verification_ratio",  metrics.verification_ratio,
     "VERIFY turns / AI turns — challenges AI output"),
    ("generative_q_ratio",  metrics.generative_query_ratio,
     "Generative / (gen+extractive) — depth of probing"),
    ("attribution_gap",     metrics.attribution_gap,
     "Pure-EXTRACT / human turns — cognitive offloading proxy"),
    ("actualization_depth", metrics.actualization_depth,
     "Scope-mod loops / decomposed tasks"),
    ("iteration_depth",     metrics.iteration_depth,
     "Refinement/override turns / total human turns"),
]
for name, val, desc in rows:
    print(f"  {name:<22}{hbar(val)}")
    print(f"    [{desc}]")

section("Verification Trend  (first half vs second half)")
vr_f, vr_s = metrics.vr_first_half, metrics.vr_second_half
print(f"  First half  {hbar(vr_f)}")
print(f"  Second half {hbar(vr_s)}")
if vr_f is not None and vr_s is not None:
    if vr_f == 0 and vr_s == 0:
        print("  Trend: FLAT at zero — no verification in either half.")
    elif vr_f > 0:
        delta = ((vr_s - vr_f) / vr_f) * 100
        lbl = "DOWN" if delta < -15 else "STABLE" if abs(delta) <= 15 else "UP"
        print(f"  Trend: {lbl}  ({delta:+.1f}%)")

section("Deterministic Risk Signals")
vr     = metrics.verification_ratio or 0.0
ag     = metrics.attribution_gap or 0.0
eng    = phases.get("engage", 0.0)
manage = phases.get("manage", 0.0)
create = phases.get("create", 0.0)
design = phases.get("design", 0.0)
signals = [
    ("explanation_trap",     eng > 0.5 and vr < 0.10,
     f"engage={eng:.2f}, VR={vr:.3f}"),
    ("cognitive_debt",       vr_f is not None and vr_s is not None
                             and metrics.session_turns > 20
                             and vr_f > 0 and vr_s < vr_f * 0.714,
     f"VR_first={vr_f}, VR_second={vr_s}"),
    ("high_attribution_gap", ag > 0.60,
     f"AG={ag:.3f}"),
    ("manage_dominated",     manage > 0.70,
     f"MANAGE={manage:.2f}"),
    ("near_zero_verify",     vr < 0.05,
     f"VR={vr:.3f}"),
    ("design_signal",        design > 0.05,
     f"DESIGN={design:.3f}"),
    ("create_signal",        create > 0.10,
     f"CREATE={create:.3f}"),
    ("inject_context_signal",counts.get("INJECT_CONTEXT",0) > 0,
     f"INJECT_CONTEXT={counts.get('INJECT_CONTEXT',0)} turns"),
    ("override_signal",      counts.get("OVERRIDE",0) > 0,
     f"OVERRIDE={counts.get('OVERRIDE',0)} turns"),
    ("verify_signal",        counts.get("VERIFY",0) > 0,
     f"VERIFY={counts.get('VERIFY',0)} turns"),
    ("self_audit_signal",    counts.get("SELF_AUDIT",0) > 0,
     f"SELF_AUDIT={counts.get('SELF_AUDIT',0)} turns"),
]
for name, fired, detail in signals:
    status = "!! FLAGGED" if fired else "  clear   "
    print(f"  [{status}] {name:<26} ({detail})")

# ── Projected dim scores ──────────────────────────────────────────────────────
import math
verify_c   = counts.get("VERIFY", 0)
override_c = counts.get("OVERRIDE", 0)
inject_c   = counts.get("INJECT_CONTEXT", 0)
scaffold_c = counts.get("SCAFFOLD", 0)
self_c     = counts.get("SELF_AUDIT", 0)
decomp_c   = counts.get("DECOMPOSE", 0)
pivot_c    = counts.get("PIVOT", 0)
ethics_c   = counts.get("ETHICS_GATE", 0)
extract_c  = counts.get("EXTRACT", 0)

proj = {}
proj["EC"]  = min(1.0, (verify_c  / max(len(a_turns),1)) * 4
                      + (self_c   / max(th,1)) * 3
                      + (override_c/max(th,1)) * 1 + 0.05)
proj["CS"]  = min(1.0, design * 0.5 + create * 0.5
                      + (inject_c / max(th,1)) * 2 + 0.08)
proj["AL"]  = min(1.0, (verify_c + self_c + decomp_c) / max(th,1) * 4 + 0.12)
proj["PR"]  = min(1.0, (inject_c + decomp_c + scaffold_c) / max(th,1) * 3
                      + (override_c/max(th,1)) * 1.5 + 0.15)
proj["ES"]  = min(1.0, (decomp_c / max(th,1)) * 4
                      + (override_c/max(th,1)) * 2 + 0.10)
proj["CD"]  = min(1.0, 1.0 - ag * 0.7 + 0.10)
proj["AUI"] = min(1.0, ethics_c / max(th,1) * 0.8 + design * 0.4 + 0.12)
proj["CA"]  = min(1.0, decomp_c / max(th,1) * 3
                      + inject_c / max(th,1) * 2
                      + design   * 0.4 + 0.10)

section("Projected Dimension Scores (heuristic, without judge)")
for dim, score in sorted(proj.items()):
    f = max(0, int(round(score * 32)))
    print(f"  {dim:<5} [{'#'*f}{'-'*(32-f)}] {score:.3f}")

pillars = {
    "Engage": (proj["AL"] * 1.0 + proj["PR"] * 1.0) / 2.0,
    "Manage": (proj["EC"] * 1.5 + proj["ES"] * 1.0) / 2.5,
    "Create": (proj["CS"] * 1.5 + proj["CD"] * 1.0) / 2.5,
    "Design": (proj["AUI"]* 1.0 + proj["CA"] * 1.0) / 2.0,
}
pillar_min = min(pillars.values())
gate_prod  = (0.7 if any(v < 0.05 for v in proj.values()) else 1.0) * (0.85 if vr == 0 else 1.0)
kappa_proj = pillar_min * gate_prod

section("Projected Pillar Scores → Composite")
for pname, pscore in sorted(pillars.items(), key=lambda x: x[1]):
    marker = " <-- MIN" if pscore == pillar_min else ""
    f = max(0, int(round(pscore * 32)))
    print(f"  {pname:<8} [{'#'*f}{'-'*(32-f)}] {pscore:.3f}{marker}")
print(f"\n  Gates: scorability={0.7 if any(v < 0.05 for v in proj.values()) else 1.0}  "
      f"verification={0.85 if vr==0 else 1.0}  state_validity=1.0")
print(f"  Gate product: {gate_prod:.3f}")
print(f"\n  collaboration_quality_kappa (projected) ≈ {kappa_proj:.3f}  "
      f"[{'low' if kappa_proj < 0.3 else 'mid' if kappa_proj < 0.55 else 'high'} band]")

# ── Three-way comparison ──────────────────────────────────────────────────────
section("Three-Way Comparison: Abhishek vs Vaibhav vs Ritesh")
cmp = {
    "Abhishek": dict(VR=vr, AG=ag, GR=metrics.generative_query_ratio or 0,
                     manage=manage, design=design, create=create,
                     a_ratio=metrics.a_turn_ratio, kappa=kappa_proj,
                     turns=metrics.session_turns),
    "Vaibhav":  dict(VR=0.000, AG=0.652, GR=0.000, manage=0.652, design=0.348,
                     create=0.000, a_ratio=0.043, kappa=0.060, turns=46),
    "Ritesh":   dict(VR=0.000, AG=0.981, GR=0.000, manage=0.981, design=0.000,
                     create=0.000, a_ratio=0.154, kappa=0.047, turns=103),
}
metrics_list = [
    ("session_turns",       "turns",  False, "{:>6.0f}"),
    ("verification_ratio",  "VR",     True,  "{:>6.3f}"),
    ("attribution_gap",     "AG",     False, "{:>6.3f}"),
    ("manage_phase",        "manage", False, "{:>6.3f}"),
    ("design_phase",        "design", True,  "{:>6.3f}"),
    ("create_phase",        "create", True,  "{:>6.3f}"),
    ("a_turn_ratio",        "a_ratio",True,  "{:>6.3f}"),
    ("kappa_projected",     "kappa",  True,  "{:>6.3f}"),
]
names = ["Abhishek", "Vaibhav", "Ritesh"]
print(f"  {'Metric':<22} {'Abhishek':>10}  {'Vaibhav':>10}  {'Ritesh':>10}")
print(f"  {'-'*56}")
for label, key, higher_better, fmt in metrics_list:
    vals = {n: cmp[n][key] for n in names}
    best = max(vals, key=lambda n: vals[n]) if higher_better else min(vals, key=lambda n: vals[n])
    row = "  " + f"{label:<22}"
    for n in names:
        v = fmt.format(vals[n])
        marker = "*" if n == best else " "
        row += f" {marker}{v[1:]}"
    print(row)
print("  (* = best on that metric)")

print()
print("  NOTE: Heuristic projections only. Stage 5 (GEMINI_API_KEY) gives exact scores.")
print("=" * W)
