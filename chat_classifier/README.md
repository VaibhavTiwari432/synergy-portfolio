# chat_classifier

Scores AI-collaboration quality from a raw chat transcript. Reads a conversation between a human and an AI assistant (ChatGPT, Claude, or Gemini) and returns 8 dimension scores, 4 pillar scores, a composite synergy score (κ), and three risk flags — without any self-report.

---

## How to run

**Requires:** `GEMINI_API_KEY` set in your environment.

### CLI

```
python -m chat_classifier.main <transcript.json> [chatgpt|claude|plaintext]
```

The second argument is the source hint for the parser. Omit it only if the file is already in `RawChat` format.

### Python API

```python
from chat_classifier.main import run

report = run("chat.json", source="chatgpt")
print(report.dimension_scores)   # {"AL": 0.61, "PR": 0.54, ...}
print(report.risk_flags)         # {"fluent_incompetence": False, ...}
```

`run()` returns a `SynergyReport` (see `schemas.py`). All fields are typed and Pydantic-validated.

---

## Pipeline stages

| # | Stage | Module | What it does |
|---|-------|--------|-------------|
| 1 | **Parse** | `ingestion/parsers.py` | Converts raw export JSON (or plaintext) into a `RawChat` with normalised `human`/`assistant` turns. Handles ChatGPT flat, ChatGPT mapping, Claude, and plaintext formats. |
| 2 | **Intent tag** | `tagger/intent_tagger.py` | Labels each human turn with one or more intent tags (`VERIFY`, `EXTRACT`, `INJECT_CONTEXT`, `OVERRIDE`, `DECOMPOSE`, `SCAFFOLD`, `PIVOT`, `ETHICS_GATE`, `ANTHROPOMORPHIZE`, `SELF_AUDIT`). Deterministic regex pass; no model call. |
| 3 | **Phase classify** | `tagger/phase_classifier.py` | Assigns the conversation a distribution over four AILit phases (Explore, Refine, Extract, Evaluate) based on tag frequency. Output is a `{phase: fraction}` dict summing to 1.0. |
| 4 | **Composite metrics** | `scorer/composite_metrics.py` | Computes six session-level NLP metrics: `verification_ratio`, `generative_query_ratio`, `attribution_gap`, `actualization_depth`, `iteration_depth`, and `semantic_distance_delta` (sentence-transformer cosine, lazy-loaded). Returns a `CompositeMetrics` object. |
| 5 | **Judge** | `scorer/gemini_judge.py` | Sends a structured transcript summary to Gemini 2.5 Flash and requests a JSON object with 107 neuron scores in `[0.0, 1.0]`. Validates the response with Pydantic; retries up to 3 times on parse failure. Temperature fixed at 0.0. |
| 6 | **Aggregate** | `aggregator/dimension_aggregator.py` | Computes weighted dimension means from neuron scores (EC×1.5, CS×1.5, all others×1.0). Applies scorability gate (τ=1: a dimension is `None` if fewer than 1 neuron fired). Rolls up four pillar scores and the composite κ. |
| 7 | **Risk flags** | `flags/risk_evaluator.py` | Evaluates three binary flags against the aggregated scores and composite metrics. `fluent_incompetence`: high PR + low EC + low CS + low verification ratio + high attribution gap. `cognitive_debt`: verification ratio in first half > 1.4× second half. `true_synergy`: both EC and CS above threshold with adequate verification. |
| 8 | **Report** | `main.py` → `_print_report` | Renders the `SynergyReport` to stdout: phase bar chart, composite metrics, per-dimension scores with weight tags, pillar scores, κ, risk flags, and neuron coverage count. |

---

## Known limitations

**EC MAE on high-band chats.** At calibration v1.3 (26 gold chats) the Error Correction dimension has an MAE of 0.41 against a target of ≤0.375. The failure mode is systematic underscoring of genuinely strong verification behaviour: the judge prompt's few-shot anchors were set from mid-band examples, so high-band EC patterns (multi-step verification chains, explicit counter-evidence injection) receive scores 0.3–0.5 lower than human raters. Fix requires 40+ gold chats with representation at the 4-band before the anchors can be updated.

**Expert attribution gap noise.** The `attribution_gap` metric measures lexical overlap between AI output tokens and the human's subsequent contribution. In expert domains this signal is noisy: a domain expert who correctly re-uses precise AI phrasing (because the terminology is correct) scores identically to a passive copier. No disambiguation is applied at the current lexical level. This inflates `fluent_incompetence` false-positive rates for expert users and will require embedding-level attribution before it can be used as a hard gate.
