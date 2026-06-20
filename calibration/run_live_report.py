"""Generic live pipeline report runner.
Usage: python -m calibration.run_live_report <chat_id> <user_label> <session_type>
"""
from __future__ import annotations
import json, os, pathlib, sys

os.environ.setdefault("SAF_API_KEY", "report-key")

from contracts.schemas import Dimension, PartnerModel, ScoreStatus
from src.ingestion.canonical import ingest
from src.api.pipeline import score_session
from src.trait.judge.client import JudgeClient

BAND_TO_FLOAT = {"low": 0.25, "mid": 0.55, "high": 0.80, "not_applicable": None}
DIM_LABELS = {
    "AL": "Agentic Literacy",   "PR": "Prompt Reasoning",
    "EC": "Epistemic Calibration", "ES": "Ethical Sensitivity",
    "CS": "Cognitive Synthesis",   "CD": "Creative Divergence",
    "AUI": "AI Use Integration",  "CA": "Cognitive Agency",
}
RUNG_MAP = {"MEASURABLE": "Measurable (transcript evidence)",
            "VALIDATED": "Validated", "DESIGNED": "Designed (structural placeholder)"}
LOAD_FMT = {"LOW_LOAD": "✓ Low", "HIGH_ICL": "↑ High (ICL)",
            "HIGH_ECL": "↑ High (ECL)", "FATIGUE": "↓ Fatigue"}

def band(v):
    if v is None: return "—"
    return "HIGH" if v >= 0.70 else ("MID" if v >= 0.40 else "LOW")

def fmt_val(v):
    return "N/A" if v is None else f"{v:.2f}  ({band(v)})"

def fmt_ci(ci):
    return "—" if ci is None else f"[{ci['low']:.2f}, {ci['high']:.2f}]"

def run_report(chat_id: str, user_label: str, session_type: str):
    raw = json.loads(pathlib.Path(f"data/gold/chats/{chat_id}.json").read_text(encoding="utf-8"))
    platform = raw.get("platform", "chatgpt")
    family = "google" if platform == "gemini" else "openai"

    gold_bands = {}
    if raw.get("annotations"):
        gold_bands = {k: v for k, v in raw["annotations"][0]["bands"].items()}

    session = ingest(
        json.dumps(raw),
        partner_model=PartnerModel(family=family),
        session_id=chat_id,
        user_ref=user_label.lower(),
        is_minor=False,
        source="gold_json",
    )
    n_human = sum(1 for t in session.turns if t.role == "human")
    n_ai    = sum(1 for t in session.turns if t.role == "ai")
    print(f"Ingested: {len(session.turns)} turns ({n_human} human / {n_ai} AI)")

    judge = JudgeClient()
    r = score_session(session, judge=judge)

    print("\n" + "="*72)
    print(f"  SAF/ARI v2.2  |  SAMPLE SESSION REPORT")
    print(f"  User: {user_label}  |  Platform: {platform.upper()}  |  Session: {chat_id}")
    print(f"  Type: {session_type}")
    print("="*72)

    # ── 1. Dimension profile ────────────────────────────────────────────────
    print("\n── 1. DIMENSION PROFILE (TRAIT / ARI) " + "─"*34)
    print(f"{'Dim':<5} {'Dimension':<24} {'Score':>6}  {'CI (95%)':>16}  {'n':>4}  Gold  Status")
    print("─"*72)
    dim_order = ["AL","PR","EC","ES","CS","CD","AUI","CA"]
    for dk in dim_order:
        d = r.profile[Dimension(dk)]
        vs  = f"{d.value:.2f}" if d.value is not None else "  N/A"
        ci  = fmt_ci(d.ci.model_dump() if d.ci else None)
        ne  = f"{d.n_eff:.0f}" if d.n_eff else "—"
        gld = gold_bands.get(dk, "—")
        match = "✅" if (
            (gld == "not_applicable" and d.value is None) or
            (gld == "high"  and d.value is not None and d.value >= 0.70) or
            (gld == "mid"   and d.value is not None and 0.40 <= d.value < 0.70) or
            (gld == "low"   and d.value is not None and d.value < 0.40)
        ) else ("N/A" if gld == "not_applicable" else "⚠️")
        st  = d.status.value if d.status != ScoreStatus.OK else band(d.value)
        fl  = " ["+",".join(f.replace("state_conditioned_precision","SCP")
                              .replace("ec_low_calibration_confidence","ec↓cal")
                              .replace("judge_family_conflict","conflict") for f in d.flags)+"]" if d.flags else ""
        print(f"{dk:<5} {DIM_LABELS[dk]:<24} {vs:>6}  {ci:>16}  {ne:>4}  {gld:<4}  {match}{fl}")

    gold_str = "  ".join(f"{k}:{v}" for k,v in gold_bands.items())
    print(f"\n  Gold (human scorer): {gold_str}")

    # ── 2. Composite ────────────────────────────────────────────────────────
    comp = r.composite
    print("\n── 2. COMPOSITE SCORE " + "─"*50)
    print(f"  Value : {fmt_val(comp.value)}")
    print(f"  CI    : {fmt_ci(comp.ci.model_dump() if comp.ci else None)}")
    print(f"  Rung  : {RUNG_MAP.get(comp.rung.value if comp.rung else '', str(comp.rung))}")
    print(f"  State-compromised caveat: {comp.state_compromised_caveat}")
    print(f"  Gates : scorability={comp.gates_passed.get('scorability')}  "
          f"state_validity={comp.gates_passed.get('state_validity')}")
    print("  Pillars (soft-min p=−2): ENGAGE(AL+PR) | MANAGE(EC+ES) | CREATE(CS+CD) | DESIGN(AUI+CA)")

    # ── 3. State strip ──────────────────────────────────────────────────────
    sv = r.state_validity
    print("\n── 3. STATE STRIP (CSPC PROXIES — per human turn) " + "─"*22)
    print(f"  {'Turn':<6} {'Load':<16} {'Epistemic':>10} {'Metacog':<12} {'ToM':>6}")
    print("  " + "─"*52)
    for s in r.state_strip:
        load = LOAD_FMT.get(s.load.value if s.load else "—", "—")
        epi  = f"{s.epistemic:+.2f}" if s.epistemic is not None else "  N/A"
        meta = s.metacog.value if s.metacog else "—"
        tom  = f"{s.tom_signal:.2f}" if s.tom_signal is not None else "N/A"
        print(f"  T{s.turn_index:<5} {load:<16} {epi:>10} {meta:<12} {tom:>6}")
    print(f"\n  Surrender: {sv.surrender_detected}"
          + (f" (onset T{sv.surrender_onset_turn})" if sv.surrender_detected else ""))
    if sv.epistemic_mean is not None:
        print(f"  Epistemic mean/slope: {sv.epistemic_mean:.3f} / {sv.epistemic_slope:.3f}")
    if sv.tom_slope is not None:
        print(f"  ToM slope: {sv.tom_slope:.4f}")
    print(f"  State compromised: {sv.state_compromised}  caveats: {sv.caveats or 'none'}")

    # ── 4. Extractor firings ────────────────────────────────────────────────
    print("\n── 4. DETERMINISTIC NEURON FIRINGS " + "─"*37)
    fired_any = False
    for dk in dim_order:
        d = r.profile[Dimension(dk)]
        if d.raw_counts:
            print(f"  {dk}: opp={d.raw_counts.get('extractor_opportunities','—')}  "
                  f"fired={d.raw_counts.get('extractor_fired_pct','—')}%")
            fired_any = True
    if not fired_any:
        print("  No applicable neuron opportunities detected in this session.")

    # ── 5. Regime overlay ───────────────────────────────────────────────────
    print("\n── 5. REGIME OVERLAY " + "─"*51)
    ov = r.regime_overlay
    if ov.occupancy:
        for label, pct in ov.occupancy.items():
            bar = "█" * int(pct * 20)
            lbl = str(label).replace("RegimeLabel.", "")
            print(f"  {lbl:<22} {pct:>4.0%}  {bar}")
    else:
        print("  (No regime events detected)")
    arm = r.flags.accept_run_max
    print(f"  Accept-run max: {arm if arm is not None else '—'}  "
          f"mean: {r.flags.accept_run_mean:.2f}" if arm is not None else "  Accept-run: N/A")

    # ── 6. Sustainability ───────────────────────────────────────────────────
    sus = r.sustainability
    sh, ew = sus.s_human_hat, sus.debt_ewma
    print("\n── 6. SUSTAINABILITY " + "─"*51)
    print(f"  Ŝ_human : {fmt_val(sh.value)}")
    if sh.r_auto is not None:
        print(f"    r_auto={sh.r_auto:.3f}  r_steer={sh.r_steer:.3f}")
    print(f"  Debt EWMA: mode={ew.mode.value if ew.mode else '—'}  "
          f"value={fmt_val(ew.value)}  n_sessions={ew.n_sessions}")

    # ── 7. Flags ────────────────────────────────────────────────────────────
    fl = r.flags
    print("\n── 7. SESSION FLAGS " + "─"*52)
    print(f"  judge_unavailable={fl.judge_unavailable}  "
          f"judge_family_conflict={fl.judge_family_conflict}  "
          f"theater_counter={fl.theater_counter}")
    print(f"  ec_low_calibration={fl.ec_low_calibration_confidence}  "
          f"fluent_incompetence={fl.fluent_incompetence}")

    # ── 8. Claims report ────────────────────────────────────────────────────
    rep = r.report
    print("\n── 8. CLAIMS-GATED REPORT (Tier 1) " + "─"*36)
    print(f"  Caveat: {rep.tier_caveat[:120]}...")
    print(f"\n  OBSERVED:")
    for o in rep.observed: print(f"    • {o}")
    if rep.inferred:
        print(f"  INFERRED:")
        for i in rep.inferred: print(f"    • {i}")

    # ── Portfolio card ──────────────────────────────────────────────────────
    print("\n── 9. PORTFOLIO CARD (browser extension view) " + "─"*26)
    print(f"  ┌{'─'*60}┐")
    print(f"  │  {user_label:<30} {platform.upper():<10} {chat_id:>10}        │")
    print(f"  ├{'─'*60}┤")
    print(f"  │  COLLABORATION PROFILE              rung: MEASURABLE  │")
    for dk in dim_order:
        d = r.profile[Dimension(dk)]
        if d.value is not None:
            bar = "█" * int(d.value * 20)
            pad = "░" * (20 - len(bar))
            print(f"  │  {DIM_LABELS[dk]:<24} {bar}{pad} {d.value:.2f}  │")
        else:
            print(f"  │  {DIM_LABELS[dk]:<24} {'— N/A —':>24}        │")
    print(f"  ├{'─'*60}┤")
    cv = comp.value
    if cv is not None:
        bar = "█" * int(cv * 20)
        pad = "░" * (20 - len(bar))
        ci_s = fmt_ci(comp.ci.model_dump() if comp.ci else None)
        print(f"  │  Overall  {bar}{pad} {cv:.2f} {ci_s:>14}  │")
    else:
        print(f"  │  Overall  — insufficient scoreable dimensions —          │")
    print(f"  ├{'─'*60}┤")
    for o in rep.observed[:3]:
        print(f"  │  • {o[:56]:<56}  │")
    if rep.inferred:
        for i in rep.inferred[:2]:
            print(f"  │  ↳ {i[:56]:<56}  │")
    print(f"  ├{'─'*60}┤")
    print(f"  │  ⚠ Tier 1 — transcript-only. Process observations,    │")
    print(f"  │    not ability or outcome measures. Not validated.       │")
    print(f"  └{'─'*60}┘")
    print()

if __name__ == "__main__":
    chat_id      = sys.argv[1] if len(sys.argv) > 1 else "gc-020"
    user_label   = sys.argv[2] if len(sys.argv) > 2 else "User"
    session_type = sys.argv[3] if len(sys.argv) > 3 else "Chat session"
    run_report(chat_id, user_label, session_type)
