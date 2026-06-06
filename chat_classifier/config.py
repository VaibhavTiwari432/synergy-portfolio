"""
Central configuration for the Chat Classifier v2.
All dimension names, pillar assignments, weights, and thresholds live here.
Downstream code reads these; never hardcodes counts or specific dim names.
"""

from __future__ import annotations

from pathlib import Path

# ── Neurons data file ───────────────────────────────────────────────────────
NEURONS_FILE: Path = Path(__file__).parent.parent / "data" / "neurons" / "neurons_v6.json"
NEURON_COUNT_EXPECTED: int = 107

# ── Dimension set (v6 FINAL, from ARI_ChatClassifier_ClaudeCode_Context.md) ─
# Count is not hardcoded — read DIMENSIONS to get the current set.
DIMENSIONS: list[str] = ["AL", "PR", "EC", "ES", "CS", "CD", "AUI", "CA"]

# ── 4-pillar developmental grouping (OECD/PISA / AILit) ────────────────────
PILLAR_MAP: dict[str, list[str]] = {
    "Engage": ["AL", "PR"],
    "Manage": ["EC", "ES"],
    "Create": ["CS", "CD"],
    "Design": ["AUI", "CA"],
}

# ── Layer (construct) mapping ───────────────────────────────────────────────
LAYER_MAP: dict[str, str] = {
    "AL": "Foundational Interaction",
    "PR": "Foundational Interaction",
    "EC": "Critical Evaluation",
    "ES": "Critical Evaluation",
    "CS": "Integrative Synthesis",
    "CD": "Integrative Synthesis",
    "AUI": "Executive Control",
    "CA": "Executive Control",
}

# ── Dimension weights (CLAUDE_CODE_PROMPT_v2.md) ────────────────────────────
# EC and CS are elevated — primary cognitive-debt and offloading signals.
# These are initial approximations; Bayesian IRT will learn final weights.
# Do NOT treat as final truth; they will be updated after real-data training.
DIMENSION_WEIGHTS: dict[str, float] = {
    "AL": 1.0,
    "PR": 1.0,
    "EC": 1.5,   # ELEVATED — primary blind-trust detection signal
    "ES": 1.0,
    "CS": 1.5,   # ELEVATED — primary cognitive-offloading signal
    "CD": 1.0,
    "AUI": 1.0,
    "CA": 1.0,
}

# ── Context scope (drives dual extraction pass — Phase 3) ──────────────────
CHUNK_SCOPE_DIMS: set[str] = {"EC", "PR", "AL", "ES"}
CHAT_SCOPE_DIMS: set[str] = {"CS", "CA", "CD", "AUI"}

# ── Scorability gate ────────────────────────────────────────────────────────
SCORABILITY_TAU: int = 3  # min applicable items to score a dimension

# ── Chunker defaults ────────────────────────────────────────────────────────
DEFAULT_WINDOW_SIZE: int = 3
DEFAULT_STRIDE: int = 1

# ── Gemini judge settings ───────────────────────────────────────────────────
GEMINI_MODEL: str = "gemini-2.5-flash"
GEMINI_TEMPERATURE: float = 0.0      # determinism required for reproducibility
GEMINI_MAX_RETRIES: int = 3          # retry on parse failure

# ── Fluent incompetence flag thresholds (CLAUDE_CODE_PROMPT_v2.md) ──────────
FLAG_PR_HIGH_THRESHOLD: float = 0.65
FLAG_EC_LOW_THRESHOLD: float = 0.40
FLAG_CS_LOW_THRESHOLD: float = 0.40
FLAG_VERIFICATION_RATIO_LOW: float = 0.15
FLAG_ATTRIBUTION_GAP_HIGH: float = 0.60

# ── Cognitive debt flag thresholds ─────────────────────────────────────────
FLAG_DEBT_RATIO_MULTIPLIER: float = 1.4   # first_half / second_half > this
FLAG_DEBT_MIN_TURNS: int = 20

# ── True synergy thresholds ─────────────────────────────────────────────────
FLAG_SYNERGY_EC_MIN: float = 0.55
FLAG_SYNERGY_CS_MIN: float = 0.55
FLAG_SYNERGY_VERIFY_MIN: float = 0.30
FLAG_SYNERGY_GENERATIVE_MIN: float = 0.45

# ── Privacy / locality flag ─────────────────────────────────────────────────
LOCAL_ONLY: bool = False
