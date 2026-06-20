"""CSL Phase 2.4 — emergence scanner + judge confirmation (`SPEC_emergence.md`).

Detects discrete exchange windows where the dyad produced a formulation neither
party was independently approaching. A sequence scanner, not a per-turn score.

A candidate exists only when all three conditions hold jointly:
  1. Bilateral novelty — the human formulation is far from BOTH the human prior
     and the AI prior centroids.
  2. Fused dependency — the human response BOTH uses the anchor AI turn (uptake)
     AND injects content not derivable from the AI prior (injection).
  3. Reframing trace — the loop closes on a reframing, not a refinement.
Candidates clearing all three are passed to a judge for confirmation; only
judge-confirmed events are reportable (#judge_confirmed). Emergence is valid only
at C4/C6 — never C1/C2.

Claim rung: MEASURABLE only after judge ICC certification (Phase 3.2); never proof
of above-baseline synergy without the retention/transfer probe. Until the judge is
wired and certified, the default confirmer abstains, so the reportable count is 0.

Two dependencies are handled by the repo's established conventions:

* EMBEDDINGS are not live (DISCREPANCY D-018). Per the `redundancy_of` precedent,
  the semantic embedder swaps in behind a stable interface later. Here the
  centroid/distance math is real; the default `Embedder` is a deterministic
  `LexicalEmbedder` fallback. No call is made to an embedder that does not exist.

* THE HIGH-DISTANCE THRESHOLD comes from a frozen artifact
  (`csl/emergence_thresholds.yaml`), loaded fail-loud. The scanner never computes
  or refits a cut at runtime, and refuses an embedder that does not match the
  artifact's `embedder_id`.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

import yaml

from contracts.schemas import CanonicalSession

DEFAULT_CONFIG_PATH = Path(__file__).with_name("emergence_thresholds.yaml")
_EMBED_DIM = 256
_REQUIRED_THRESHOLDS = ("novelty_high", "uptake_min", "injection_min", "reframing_min")
_REQUIRED_WINDOW = ("max_human_turns", "ai_prior_turns", "human_prior_turns")


# ── frozen threshold artifact (fail-loud) ──────────────────────────────────────


@dataclass(frozen=True)
class EmergenceConfig:
    version: str
    status: str
    embedder_id: str
    thresholds: dict[str, float]
    window: dict[str, int]


def load_emergence_config(path: str | Path = DEFAULT_CONFIG_PATH) -> EmergenceConfig:
    """Load the frozen threshold artifact. Fail loudly if it is missing or
    malformed — never fall back to a default cut (SPEC_emergence: "fail loudly if
    the threshold artifact is missing ... must not compute or refit cut points")."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"emergence threshold artifact missing: {p}. The scanner refuses to "
            "run without a frozen cut (SPEC_emergence: no runtime refit)."
        )
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("emergence threshold artifact must be a mapping")

    embedder_id = raw.get("embedder_id")
    if not embedder_id:
        raise ValueError("emergence threshold artifact must declare embedder_id")

    thresholds = raw.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("emergence threshold artifact must define thresholds")
    missing = [k for k in _REQUIRED_THRESHOLDS if k not in thresholds]
    if missing:
        raise ValueError(f"emergence thresholds missing keys: {missing}")

    window = raw.get("window")
    if not isinstance(window, dict):
        raise ValueError("emergence threshold artifact must define window")
    missing_w = [k for k in _REQUIRED_WINDOW if k not in window]
    if missing_w:
        raise ValueError(f"emergence window missing keys: {missing_w}")

    return EmergenceConfig(
        version=str(raw.get("version", "")),
        status=str(raw.get("status", "")),
        embedder_id=str(embedder_id),
        thresholds={k: float(thresholds[k]) for k in _REQUIRED_THRESHOLDS},
        window={k: int(window[k]) for k in _REQUIRED_WINDOW},
    )


# ── embedding interface + deterministic lexical fallback ───────────────────────


@runtime_checkable
class Embedder(Protocol):
    id: str

    def embed(self, text: str) -> tuple[float, ...]: ...


class LexicalEmbedder:
    """Deterministic hashed bag-of-words embedder (the D-018 lexical placeholder).

    A real sentence-transformers embedder swaps in behind this same interface
    later. Uses hashlib (not salted `hash()`) so vectors are byte-identical across
    runs. Vectors are L2-normalized; cosine distance is then 1 - dot product.
    """

    id = "lexical-bow-hashing-v0"

    def __init__(self, dim: int = _EMBED_DIM):
        self.dim = dim

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def embed(self, text: str) -> tuple[float, ...]:
        vec = [0.0] * self.dim
        for tok in self._tokens(text):
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return tuple(vec)
        return tuple(v / norm for v in vec)


class EmbeddingCache:
    """Memoized embedder + centroid/distance helpers (the type the spec names)."""

    def __init__(self, embedder: Embedder | None = None):
        self.embedder: Embedder = embedder or LexicalEmbedder()
        self._cache: dict[str, tuple[float, ...]] = {}

    @property
    def embedder_id(self) -> str:
        return self.embedder.id

    def embed(self, text: str) -> tuple[float, ...]:
        if text not in self._cache:
            self._cache[text] = self.embedder.embed(text)
        return self._cache[text]

    def centroid(self, texts: list[str]) -> tuple[float, ...] | None:
        vecs = [self.embed(t) for t in texts if t.strip()]
        if not vecs:
            return None
        dim = len(vecs[0])
        mean = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]
        norm = math.sqrt(sum(m * m for m in mean))
        if norm == 0.0:
            return tuple(mean)
        return tuple(m / norm for m in mean)

    @staticmethod
    def distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        return 1.0 - dot


# ── candidate signals, packet, event ───────────────────────────────────────────


@dataclass(frozen=True)
class CandidateSignals:
    novelty_vs_human_prior: float
    novelty_vs_ai_prior: float
    uptake: float
    injection: float
    reframing: int


@dataclass(frozen=True)
class JudgeConfirmation:
    judge_confirmed: bool
    acf_level: str
    trigger_type: str
    confirmation: str
    direction_change: bool
    output_delta: bool


@dataclass(frozen=True)
class EmergenceEvent:
    ev_id: str
    turn_range: tuple[int, int]
    acf_level: str          # "C4" | "C6"
    trigger_type: str       # "HI" | "AR" | "BI"
    confirmation: str       # "explicit" | "behavioral" | "none"
    direction_change: bool
    output_delta: bool
    judge_confirmed: bool


@runtime_checkable
class EmergenceConfirmer(Protocol):
    def confirm(self, packet: dict[str, Any]) -> JudgeConfirmation: ...


class AbstainingConfirmer:
    """Default confirmer: the judge is not wired (gated on ICC, Phase 3.2), so it
    abstains. Candidates remain audit-only and the reportable count stays 0 —
    never an unconfirmed event surfacing as reportable."""

    def confirm(self, packet: dict[str, Any]) -> JudgeConfirmation:
        return JudgeConfirmation(
            judge_confirmed=False,
            acf_level=packet["proposed_acf_level"],
            trigger_type=packet["proposed_trigger_type"],
            confirmation="none",
            direction_change=False,
            output_delta=False,
        )


# ── lexical signal cues (deterministic candidate gate) ─────────────────────────

_UPTAKE_CUES = re.compile(
    r"\byou (said|suggested|mentioned|wrote|proposed|gave)\b|\byour\b|"
    r"\bthat (approach|idea|suggestion|point|answer|code)\b|\bbuilding on\b|"
    r"\bbased on (that|your|this)\b|\bbuild on\b",
    re.IGNORECASE,
)
_INJECTION_CUES = re.compile(
    r"\bbut\b|\binstead\b|\bwhat about\b|\bconsider\b|\bmust\b|\bconstraint\b|"
    r"\bactually\b|\balso need\b|\bwe also\b|\brequirement\b|\bin my case\b|"
    r"\bfor my\b|\bgiven that\b|\bhowever\b|\bexcept\b",
    re.IGNORECASE,
)
_REFRAME_CUES = re.compile(
    r"\brefram(e|ing)\b|\bdifferent way\b|\bthe real (question|problem|issue)\b|"
    r"\bthink of (it|this) as\b|\bwhat if we\b|\bstep back\b|\binstead of\b|"
    r"\bactually,? the\b|\bthe key insight\b|\bturn(s)? (it|this) into\b|"
    r"\bthe underlying\b|\bbigger picture\b|\bnot about .* but about\b",
    re.IGNORECASE,
)
_C6_CUES = re.compile(
    r"\bcreate\b|\bdesign\b|\bnovel\b|\bsynthesi[sz]e\b|\bcombine\b|\binvent\b|"
    r"\bnew concept\b|\bprototype\b|\bcompose\b|\bgenerate a\b",
    re.IGNORECASE,
)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


# ── scanner ────────────────────────────────────────────────────────────────────


def scan_emergence(
    chat: CanonicalSession,
    embeddings: EmbeddingCache | None = None,
    *,
    config: EmergenceConfig | None = None,
    confirmer: EmergenceConfirmer | None = None,
) -> list[EmergenceEvent]:
    """Scan AI-anchored windows for emergence candidates and judge-confirm them.

    Returns every candidate as an `EmergenceEvent` carrying its `judge_confirmed`
    flag; reportable events are `reportable_events(...)` (judge_confirmed only).
    Fails loud if the frozen threshold artifact is missing and refuses an embedder
    that does not match the artifact's `embedder_id`.
    """
    cfg = config or load_emergence_config()
    cache = embeddings or EmbeddingCache()
    if cache.embedder_id != cfg.embedder_id:
        raise ValueError(
            f"embedder '{cache.embedder_id}' does not match the frozen threshold "
            f"artifact embedder_id '{cfg.embedder_id}'. The lexical cut is not "
            "valid for a different embedder (re-freeze + ADR required)."
        )
    judge = confirmer or AbstainingConfirmer()

    turns = chat.turns
    ai_indices = [i for i, t in enumerate(turns) if t.role == "ai" and t.text.strip()]
    events: list[EmergenceEvent] = []

    for anchor_pos in ai_indices:
        window = _build_window(chat, anchor_pos, cfg)
        if window is None:
            continue
        human_new, human_prior, ai_prior, turn_range = window

        signals = _signals(cache, human_new, human_prior, ai_prior, turns[anchor_pos].text)
        if signals is None:
            continue  # bilateral novelty INSUFFICIENT_SAMPLE (no prior centroid)

        if not _passes_all_conditions(signals, cfg):
            continue

        proposed_level = "C6" if _C6_CUES.search(" ".join(human_new)) else "C4"
        proposed_trigger = "BI"  # condition 2 requires both sides → bilateral
        packet = {
            "window_id": f"ev-{chat.session_id}-{turn_range[0]}",
            "turn_range": list(turn_range),
            "anchor_ai_summary": turns[anchor_pos].text[:400],
            "human_response_summary": " ".join(human_new)[:400],
            "human_prior_terms": _terms(human_prior),
            "ai_prior_terms": _terms(ai_prior),
            "signals": {
                "novelty_vs_human_prior": signals.novelty_vs_human_prior,
                "novelty_vs_ai_prior": signals.novelty_vs_ai_prior,
                "uptake": signals.uptake,
                "injection": signals.injection,
                "reframing": signals.reframing,
            },
            "proposed_acf_level": proposed_level,
            "proposed_trigger_type": proposed_trigger,
        }
        confirmation = judge.confirm(packet)
        level = confirmation.acf_level
        # structural guard: emergence is never valid at C1/C2 (SPEC scope), even
        # if a judge mislabels — such a candidate is not a reportable event.
        confirmed = confirmation.judge_confirmed and level in ("C4", "C6")
        events.append(
            EmergenceEvent(
                ev_id=packet["window_id"],
                turn_range=turn_range,
                acf_level=level if level in ("C4", "C6") else proposed_level,
                trigger_type=confirmation.trigger_type,
                confirmation=confirmation.confirmation,
                direction_change=confirmation.direction_change,
                output_delta=confirmation.output_delta,
                judge_confirmed=confirmed,
            )
        )

    return events


def reportable_events(events: list[EmergenceEvent]) -> list[EmergenceEvent]:
    """User-facing emergence count: judge-confirmed events only (SPEC)."""
    return [e for e in events if e.judge_confirmed]


# ── window + signal helpers ────────────────────────────────────────────────────


def _build_window(
    chat: CanonicalSession,
    anchor_pos: int,
    cfg: EmergenceConfig,
) -> tuple[list[str], list[str], list[str], tuple[int, int]] | None:
    """Return (human_new, human_prior, ai_prior, turn_range) for the anchor, or
    None when there is no following human turn to form a response span."""
    turns = chat.turns
    max_human = cfg.window["max_human_turns"]

    human_new: list[str] = []
    last_idx = anchor_pos
    for j in range(anchor_pos + 1, len(turns)):
        t = turns[j]
        if t.role == "human" and t.text.strip():
            human_new.append(t.text)
            last_idx = j
            if len(human_new) >= max_human:
                break
        # intervening AI turns are context, not human injection; keep scanning
    if not human_new:
        return None

    human_prior = [
        t.text for t in turns[:anchor_pos] if t.role == "human" and t.text.strip()
    ][-cfg.window["human_prior_turns"]:]
    ai_prior = [
        t.text for t in turns[: anchor_pos + 1] if t.role == "ai" and t.text.strip()
    ][-cfg.window["ai_prior_turns"]:]

    return human_new, human_prior, ai_prior, (anchor_pos, last_idx)


def _signals(
    cache: EmbeddingCache,
    human_new: list[str],
    human_prior: list[str],
    ai_prior: list[str],
    anchor_text: str,
) -> CandidateSignals | None:
    human_new_centroid = cache.centroid(human_new)
    human_prior_centroid = cache.centroid(human_prior)
    ai_prior_centroid = cache.centroid(ai_prior)
    if human_new_centroid is None or human_prior_centroid is None or ai_prior_centroid is None:
        return None  # cannot form a prior centroid → INSUFFICIENT_SAMPLE

    novelty_human = cache.distance(human_new_centroid, human_prior_centroid)
    novelty_ai = cache.distance(human_new_centroid, ai_prior_centroid)

    human_text = " ".join(human_new)
    human_tokens = _tokens(human_text)
    anchor_tokens = _tokens(anchor_text)
    ai_prior_tokens = _tokens(" ".join(ai_prior))

    # uptake: lexical overlap with the anchor AI turn, plus explicit-reference cues.
    overlap = (len(human_tokens & anchor_tokens) / len(human_tokens)) if human_tokens else 0.0
    uptake = overlap + (0.5 if _UPTAKE_CUES.search(human_text) else 0.0)

    # injection: share of human tokens NOT derivable from the AI prior, plus cues.
    novel_share = (
        len(human_tokens - ai_prior_tokens) / len(human_tokens) if human_tokens else 0.0
    )
    injection = novel_share if _INJECTION_CUES.search(human_text) else novel_share * 0.5

    reframing = len(_REFRAME_CUES.findall(human_text))

    return CandidateSignals(
        novelty_vs_human_prior=round(novelty_human, 6),
        novelty_vs_ai_prior=round(novelty_ai, 6),
        uptake=round(uptake, 6),
        injection=round(injection, 6),
        reframing=reframing,
    )


def _passes_all_conditions(s: CandidateSignals, cfg: EmergenceConfig) -> bool:
    th = cfg.thresholds
    bilateral_novelty = (
        s.novelty_vs_human_prior >= th["novelty_high"]
        and s.novelty_vs_ai_prior >= th["novelty_high"]
    )
    fused_dependency = s.uptake >= th["uptake_min"] and s.injection >= th["injection_min"]
    reframing_trace = s.reframing >= th["reframing_min"]
    return bilateral_novelty and fused_dependency and reframing_trace


def _terms(texts: list[str], k: int = 12) -> list[str]:
    """Minimized summary terms (no transcript text persisted, #16)."""
    seen: list[str] = []
    for tok in re.findall(r"[a-z0-9]+", " ".join(texts).lower()):
        if len(tok) > 3 and tok not in seen:
            seen.append(tok)
        if len(seen) >= k:
            break
    return seen
