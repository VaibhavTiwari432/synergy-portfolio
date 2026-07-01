"""CSL Phase 2.6 — three-panel CSL report (user-friendly, four-state, never-collapse).

The CSL report is a parallel descriptive layer over ARI. It renders three panels:

  Panel A — per-level contribution bars: your share vs the AI's share, INDEPENDENT
            per level (they do NOT sum to 100 across levels). Never a bare
            percentage — every OK bar carries a CI; the four states render as
            distinct labels (#never-collapse).
  Panel B — emergence ribbon ABOVE the stack: count, levels, bilateral fraction,
            carrying the mandatory indicator-not-proof caveat string verbatim from
            SPEC_emergence.md.
  Panel C — ARI capability dot per level, flagging high-ARI / low-your-share as the
            Borrowed-Brilliance signal. ARI dots are NEVER averaged into the bars
            (separate channel, separate panel — Do-NOT #3).

This build has no `output/` package (the v3.2 doc's `output/translation.py` is the
older ChatClassifier layout); user-friendly translation is co-located here. Like
`src/claims/report.py`, every user-facing string passes the tier forbidden-word
scan — "synergy"/"surrender"/"dependent" can never appear at Tier 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contracts.schemas import Dimension, DimensionScore, Rung, ScoreStatus, Tier
from csl.crosswalk import ACF_LEVELS, ACFCrosswalk, load_acf_crosswalk
from csl.emergence import EmergenceEvent, reportable_events
from csl.ownership import OwnershipResult
from src.claims.report import ForbiddenWordViolation, forbidden_word_scan

#: SPEC_emergence.md "Reporting Language" — the mandatory caveat, VERBATIM. The
#: only substitution is the integer count in place of the literal "N". A test
#: asserts the shipped string equals this spec text with the count filled in, so
#: any drift from the spec wording fails CI.
EMERGENCE_CAVEAT_TEMPLATE = (
    "This session contained N emergence events: moments where the exchange "
    "produced formulations neither party was approaching independently. These "
    "indicate genuine complementarity. They are not proof of performance gain "
    "above what you could achieve alone, which requires the unaided follow-up "
    "task to establish."
)

#: provisional Borrowed-Brilliance heuristics (NOT corpus-calibrated cuts).
DEFAULT_HIGH_ARI = 0.66
DEFAULT_LOW_SHARE = 0.34

#: the four states, rendered as DISTINCT user-facing labels (never collapsed).
_STATE_LABEL: dict[ScoreStatus, str] = {
    ScoreStatus.OK: "measured",
    ScoreStatus.NOT_APPLICABLE: "did not arise this session",
    ScoreStatus.INSUFFICIENT_SAMPLE: "too few signals to resolve",
    ScoreStatus.MEASUREMENT_SATURATED: "at the instrument limit",
}


@dataclass(frozen=True)
class PanelABar:
    """One ACF level's independent contribution bar."""

    level: str
    label: str
    status: ScoreStatus
    status_label: str
    your_share: float | None
    ai_share: float | None
    ci_low: float | None
    ci_high: float | None
    n_eff: float | None  # C3: effective contributing opportunities; always present for OK bars
    censored: str | None  # e.g. "≥ 0.80" when saturated


@dataclass(frozen=True)
class PanelBRibbon:
    """Emergence ribbon above the stack."""

    count: int
    levels: tuple[str, ...]
    bilateral_fraction: float | None
    caveat: str


@dataclass(frozen=True)
class PanelCDot:
    """ARI capability dot per level — a SEPARATE channel from the bars."""

    level: str
    label: str
    ari_capability: float | None
    your_share: float | None
    borrowed_brilliance: bool
    note: str | None


@dataclass(frozen=True)
class CSLReport:
    panel_a: tuple[PanelABar, ...]
    panel_b: PanelBRibbon
    panel_c: tuple[PanelCDot, ...]
    tier_caveat: str
    rung: Rung
    notes: tuple[str, ...] = field(default_factory=tuple)


_TIER_CAVEAT = (
    "Contribution view (transcript-only): these are displayed-contribution "
    "observations from one conversation — who visibly drove each kind of work. "
    "They are not a measure of ability; what you could do unaided requires a "
    "follow-up task. Capability dots and contribution bars are separate and are "
    "never combined."
)


def ari_capability_by_level(
    profile: dict[Dimension, DimensionScore],
    crosswalk: ACFCrosswalk,
) -> dict[str, float | None]:
    """Per-level ARI capability = mean of OK dimension values across the distinct
    dimensions whose neurons map to the level. Kept entirely separate from the
    ownership bars — this feeds Panel C dots only, never Panel A."""
    out: dict[str, float | None] = {}
    for level in ACF_LEVELS:
        dims = {
            nid.split("-", 1)[0] for nid in crosswalk.levels[level]["neurons"]
        }
        vals = [
            s.value
            for dim, s in profile.items()
            if dim.value in dims and s.status == ScoreStatus.OK and s.value is not None
        ]
        out[level] = round(sum(vals) / len(vals), 6) if vals else None
    return out


def build_csl_report(
    ownership: dict[str, OwnershipResult],
    emergence: list[EmergenceEvent],
    ari_profile: dict[Dimension, DimensionScore],
    *,
    tier: Tier = 1,
    crosswalk: ACFCrosswalk | None = None,
    high_ari: float = DEFAULT_HIGH_ARI,
    low_share: float = DEFAULT_LOW_SHARE,
) -> CSLReport:
    """Assemble the three-panel CSL report and enforce the forbidden-word scan.

    `ownership` and `ari_profile` are independent inputs and stay independent:
    Panel A renders ownership; Panel C renders ARI capability; the two are only
    ever COMPARED (Borrowed Brilliance), never averaged (Do-NOT #3).
    """
    cw = crosswalk or load_acf_crosswalk()

    panel_a = _panel_a(ownership, cw)
    panel_b = _panel_b(emergence)
    panel_c = _panel_c(ownership, ari_profile, cw, high_ari, low_share)

    report = CSLReport(
        panel_a=panel_a,
        panel_b=panel_b,
        panel_c=panel_c,
        tier_caveat=_TIER_CAVEAT,
        rung=Rung.DESIGNED,  # displayed ownership is uncertified until per-level ICC
        notes=(
            "Bars are independent per level and do not sum across levels.",
            "Capability dots are never averaged into the contribution bars.",
        ),
    )

    _enforce_forbidden_words(report, tier)
    return report


# ── panels ──────────────────────────────────────────────────────────────────────


def _panel_a(ownership: dict[str, OwnershipResult], cw: ACFCrosswalk) -> tuple[PanelABar, ...]:
    bars: list[PanelABar] = []
    for level in ACF_LEVELS:
        label = str(cw.levels[level]["label"])
        r = ownership.get(level)
        if r is None:
            bars.append(PanelABar(
                level=level, label=label, status=ScoreStatus.NOT_APPLICABLE,
                status_label=_STATE_LABEL[ScoreStatus.NOT_APPLICABLE],
                your_share=None, ai_share=None, ci_low=None, ci_high=None,
                n_eff=None, censored=None,
            ))
            continue
        censored = None
        if r.status == ScoreStatus.MEASUREMENT_SATURATED and r.censored is not None:
            cmp = "≥" if r.censored.direction == "high" else "≤"
            censored = f"{cmp} {r.censored.bound:.2f}"
        bars.append(PanelABar(
            level=level, label=label, status=r.status,
            status_label=_STATE_LABEL[r.status],
            your_share=r.human_pct, ai_share=r.ai_pct,
            ci_low=r.ci.low if r.ci else None,
            ci_high=r.ci.high if r.ci else None,
            n_eff=r.n_eff if r.status == ScoreStatus.OK else None,
            censored=censored,
        ))
    return tuple(bars)


def _panel_b(emergence: list[EmergenceEvent]) -> PanelBRibbon:
    confirmed = reportable_events(emergence)
    count = len(confirmed)
    levels = tuple(sorted({e.acf_level for e in confirmed}))
    bilateral_fraction = (
        round(sum(1 for e in confirmed if e.trigger_type == "BI") / count, 6)
        if count else None
    )
    caveat = EMERGENCE_CAVEAT_TEMPLATE.replace("N emergence events", f"{count} emergence events", 1)
    return PanelBRibbon(
        count=count, levels=levels, bilateral_fraction=bilateral_fraction, caveat=caveat,
    )


def _panel_c(
    ownership: dict[str, OwnershipResult],
    ari_profile: dict[Dimension, DimensionScore],
    cw: ACFCrosswalk,
    high_ari: float,
    low_share: float,
) -> tuple[PanelCDot, ...]:
    ari_by_level = ari_capability_by_level(ari_profile, cw)
    dots: list[PanelCDot] = []
    for level in ACF_LEVELS:
        label = str(cw.levels[level]["label"])
        ari = ari_by_level.get(level)
        r = ownership.get(level)
        your_share = r.human_pct if (r is not None and r.status == ScoreStatus.OK) else None

        borrowed = (
            ari is not None and your_share is not None
            and ari >= high_ari and your_share < low_share
        )
        note = (
            "You score high here but the AI visibly carried most of it — "
            "borrowed brilliance to watch."
            if borrowed else None
        )
        dots.append(PanelCDot(
            level=level, label=label, ari_capability=ari,
            your_share=your_share, borrowed_brilliance=borrowed, note=note,
        ))
    return tuple(dots)


def _enforce_forbidden_words(report: CSLReport, tier: Tier) -> None:
    texts: list[str] = [report.tier_caveat, report.panel_b.caveat, *report.notes]
    for bar in report.panel_a:
        texts.extend([bar.label, bar.status_label])
    for dot in report.panel_c:
        texts.append(dot.label)
        if dot.note:
            texts.append(dot.note)
    violations = forbidden_word_scan(texts, tier)
    if violations:
        raise ForbiddenWordViolation("; ".join(violations))
