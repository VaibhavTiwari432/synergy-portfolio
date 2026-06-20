"""Run gc-027 (Vaibhav_ChatGPT) through the full live pipeline and print
every framework metric in report format."""

from __future__ import annotations
import json, os, sys, pathlib

os.environ.setdefault("SAF_API_KEY", "report-key")

from contracts.schemas import Dimension, PartnerModel, ScoreStatus
from src.ingestion.canonical import ingest
from src.api.pipeline import score_session
from src.trait.judge.client import JudgeClient

# ── load transcript ──────────────────────────────────────────────────────────
raw = json.loads(pathlib.Path("data/gold/chats/gc-027.json").read_text())

payload = json.dumps(raw)  # gold_json format already

session = ingest(
    payload,
    partner_model=PartnerModel(family="openai"),
    session_id="gc-027",
    user_ref="vaibhav",
    is_minor=False,
    source="gold_json",
)

print(f"Session ingested: {len(session.turns)} turns "
      f"({sum(1 for t in session.turns if t.role=='human')} human / "
      f"{sum(1 for t in session.turns if t.role=='ai')} AI)")

# ── score ────────────────────────────────────────────────────────────────────
judge = JudgeClient()
r = score_session(session, judge=judge)

# ── helpers ──────────────────────────────────────────────────────────────────
DIM_LABELS = {
    "AL": "Agentic Literacy",
    "PR": "Prompt Reasoning",
    "EC": "Epistemic Calibration",
    "ES": "Ethical Sensitivity",
    "CS": "Cognitive Synthesis",
    "CD": "Creative Divergence",
    "AUI": "AI Use Integration",
    "CA": "Cognitive Agency",
}
RUNG_MAP = {"MEASURABLE": "Measurable (transcript evidence)", "VALIDATED": "Validated",
            "DESIGNED": "Designed (structural placeholder)"}

def fmt_val(v):
    if v is None: return "N/A"
    return f"{v:.2f}  ({band(v)})"

def band(v):
    if v is None: return "—"
    if v >= 0.70: return "HIGH"
    if v >= 0.40: return "MID"
    return "LOW"

def fmt_ci(ci):
    if ci is None: return "—"
    return f"[{ci['low']:.2f}, {ci['high']:.2f}]"

def fmt_load(lbl): return {"LOW_LOAD": "✓ Low", "HIGH_ICL": "↑ High (ICL)", "HIGH_ECL": "↑ High (ECL)", "FATIGUE": "↓ Fatigue"}.get(lbl, lbl)

# ── PRINT ────────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("  SAF/ARI v2.2  |  SAMPLE SESSION REPORT")
print("  User: Vaibhav  |  Platform: ChatGPT  |  Session: gc-027")
print("  Type: Open-ended philosophical inquiry — AI Ethics Socratic Dialogue")
print("="*72)

# ── SECTION 1: Profile ───────────────────────────────────────────────────────
print("\n── 1. DIMENSION PROFILE (TRAIT / ARI) " + "─"*34)
print(f"{'Dim':<5} {'Dimension':<24} {'Score':>6}  {'CI (95%)':>16}  {'n_eff':>5}  {'Status'}")
print("─"*72)
for dim_key in ["AL","PR","EC","ES","CS","CD","AUI","CA"]:
    d = r.profile[Dimension(dim_key)]
    val_str = f"{d.value:.2f}" if d.value is not None else "  N/A"
    ci_str  = fmt_ci(d.ci.model_dump() if d.ci else None)
    neff    = f"{d.n_eff:.0f}" if d.n_eff else "—"
    status  = d.status.value if d.status != ScoreStatus.OK else band(d.value)
    flags   = " ["+",".join(d.flags)+"]" if d.flags else ""
    print(f"{dim_key:<5} {DIM_LABELS[dim_key]:<24} {val_str:>6}  {ci_str:>16}  {neff:>5}  {status}{flags}")

# Gold bands for comparison
gold = {"AL":"high","PR":"high","EC":"high","ES":"high","CS":"high","CD":"high","AUI":"high","CA":"high"}
print("\n  Gold annotation (human scorer): " + "  ".join(f"{k}:{v}" for k,v in gold.items()))

# ── SECTION 2: Composite ─────────────────────────────────────────────────────
comp = r.composite
print("\n── 2. COMPOSITE SCORE " + "─"*50)
print(f"  Value : {fmt_val(comp.value)}")
print(f"  CI    : {fmt_ci(comp.ci.model_dump() if comp.ci else None)}")
print(f"  Rung  : {RUNG_MAP.get(comp.rung.value if comp.rung else '', comp.rung)}")
print(f"  State-compromised caveat: {comp.state_compromised_caveat}")
print(f"  Gates : scorability={comp.gates_passed.get('scorability')}  "
      f"state_validity={comp.gates_passed.get('state_validity')}")
print("\n  Pillar breakdown (soft-min p=−2, hollow pillar cannot average away):")
print("    ENGAGE  (AL+PR)  |  MANAGE  (EC+ES)  |  CREATE  (CS+CD)  |  DESIGN  (AUI+CA)")

# ── SECTION 3: State strip ───────────────────────────────────────────────────
print("\n── 3. STATE STRIP (CSPC PROXIES — per human turn) " + "─"*22)
print(f"  {'Turn':<6} {'Load':<16} {'Epistemic':>10} {'Metacog':<12} {'ToM Signal':>10}")
print("  " + "─"*56)
for sv in r.state_strip:
    load    = fmt_load(sv.load.value if sv.load else "—")
    epi     = f"{sv.epistemic:+.2f}" if sv.epistemic is not None else "  N/A"
    meta    = sv.metacog.value if sv.metacog else "—"
    tom     = f"{sv.tom_signal:.2f}" if sv.tom_signal is not None else "  N/A"
    print(f"  T{sv.turn_index:<5} {load:<16} {epi:>10} {meta:<12} {tom:>10}")

sv_summary = r.state_validity
print(f"\n  Session summary:")
print(f"    Surrender detected  : {sv_summary.surrender_detected}")
print(f"    Epistemic mean/slope: {sv_summary.epistemic_mean:.3f} / "
      f"{sv_summary.epistemic_slope:.3f}" if sv_summary.epistemic_mean is not None else "    Epistemic: N/A")
print(f"    ToM slope           : {sv_summary.tom_slope:.4f}" if sv_summary.tom_slope is not None else "    ToM slope: N/A")
print(f"    State compromised   : {sv_summary.state_compromised}")
print(f"    Caveats             : {sv_summary.caveats or 'none'}")

# ── SECTION 4: Deterministic neuron firings ──────────────────────────────────
print("\n── 4. DETERMINISTIC NEURON FIRINGS (extractor evidence) " + "─"*17)
neurons_found = False
for dim_key in ["AL","PR","EC","ES","CS","CD","AUI","CA"]:
    d = r.profile[Dimension(dim_key)]
    if d.raw_counts:
        print(f"  {dim_key}: opportunities={d.raw_counts.get('extractor_opportunities','—')}  "
              f"fired={d.raw_counts.get('extractor_fired_pct','—')}%")
        neurons_found = True
if not neurons_found:
    print("  (All neurons: 0 opportunities — structurally empty dims or short session)")

# ── SECTION 5: Regime overlay ────────────────────────────────────────────────
print("\n── 5. REGIME OVERLAY (dynamics — tag-derived) " + "─"*27)
ov = r.regime_overlay
if ov.occupancy:
    for label, pct in ov.occupancy.items():
        bar = "█" * int(pct * 20)
        print(f"  {label:<20} {pct:>4.0%}  {bar}")
else:
    print("  (No regime events detected)")
print(f"  Accept-run max: {r.flags.accept_run_max}  mean: {r.flags.accept_run_mean:.2f}"
      if r.flags.accept_run_max is not None else "  Accept-run: N/A")

# ── SECTION 6: Sustainability ────────────────────────────────────────────────
print("\n── 6. SUSTAINABILITY " + "─"*51)
sus = r.sustainability
sh  = sus.s_human_hat
ew  = sus.debt_ewma
print(f"  Ŝ_human (automation-steer balance):")
print(f"    Value     : {fmt_val(sh.value)}")
print(f"    r_auto    : {sh.r_auto:.3f}  (accept-flat rate)" if sh.r_auto is not None else "    r_auto: N/A")
print(f"    r_steer   : {sh.r_steer:.3f}  (steering-event rate)" if sh.r_steer is not None else "    r_steer: N/A")
print(f"    Rung      : {sh.rung.value if sh.rung else '—'}")
print(f"\n  Debt EWMA (multi-session trajectory):")
print(f"    Mode  : {ew.mode.value if ew.mode else '—'}")
print(f"    Value : {fmt_val(ew.value)}")
print(f"    n_sessions: {ew.n_sessions}  (single session → INSUFFICIENT_HISTORY is expected)")

# ── SECTION 7: Reaction signatures ──────────────────────────────────────────
print("\n── 7. REACTION SIGNATURES (E→R dynamics) " + "─"*31)
rs = r.reaction_signatures
print("  Note: trigger events (E-ERR, E-CONTRA, etc.) are not yet auto-detected")
print("  in transcript text — all event-conditional cells are gated N/A (n=0).")
print("  This is the one runtime gap in the v2.2 implementation (see Q2 answer).")
print(f"  Theater counter (EC): {r.flags.theater_counter} verification(s) "
      f"with zero downstream delta")

# ── SECTION 8: Session flags ─────────────────────────────────────────────────
print("\n── 8. SESSION FLAGS " + "─"*52)
fl = r.flags
print(f"  Judge unavailable  : {fl.judge_unavailable}")
print(f"  Judge family confl : {fl.judge_family_conflict}")
print(f"  EC low calibration : {fl.ec_low_calibration_confidence}")
print(f"  Theater counter    : {fl.theater_counter}")
print(f"  Fluent incompetence: {fl.fluent_incompetence}  (requires extractor evidence)")

# ── SECTION 9: Claims-gated report ──────────────────────────────────────────
print("\n── 9. CLAIMS-GATED REPORT (tier 1 — transcript only) " + "─"*19)
rep = r.report
print(f"  Tier caveat: {rep.tier_caveat}")
print(f"\n  OBSERVED (rung: MEASURABLE — claimed from transcript evidence):")
for obs in rep.observed:
    print(f"    • {obs}")
if rep.inferred:
    print(f"\n  INFERRED:")
    for inf in rep.inferred:
        print(f"    • {inf}")
if rep.hypothesized:
    print(f"\n  HYPOTHESIZED:")
    for hyp in rep.hypothesized:
        print(f"    • {hyp}")

print("\n" + "="*72)
print("  TIER 1 CEILING: nothing above MEASURABLE without validated telemetry.")
print("  No 'synergy', 'surrender', or peer rankings in any user-facing field.")
print("="*72)
