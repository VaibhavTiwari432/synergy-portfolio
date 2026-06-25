# v3.22 FAQ & Glossary

**Frequently Asked Questions** and **Quick Reference Terms**

---

## FAQ — General

### Q: What is v3.22?

**A:** v3.22 is a major update to the Synergy system that delivers 12 foundational improvements across judge reliability, measurement honesty, corpus growth automation, and fair user assessment. It's designed to scale from the current 26-chat gold set to 200+ chats while maintaining quality and fairness.

### Q: Do I need to deploy v3.22 immediately?

**A:** No. v3.22 is production-ready, but deployment is phased:
- **WAVE 0 (Immediate):** Deploy cascaded replication, per-criterion calls, active learning, Tobit EC
- **WAVE 1 (Alongside 0):** Deploy validation & monitoring
- **WAVE 2 (Month 2-3):** Auto-unlock κ^H + LPA when corpus reaches n=200
- **WAVE 3 (Month 3-4):** Activate CRO after DIF clearance

### Q: Will v3.22 break existing functionality?

**A:** No. v3.22 is 100% backward compatible with v3.21. All existing Scope A features continue to work. Non-negotiables are upheld: ontology frozen, no regressions, no "synergy" in output.

### Q: How long does WAVE 0 deployment take?

**A:** ~1 week in staging (validation), ~1 day in production (activation). The deployment script automates most of it.

---

## FAQ — Judge Quality

### Q: What is "cascaded replication"?

**A:** A judge calling strategy where:
1. Judge scores a neuron **3 times** initially
2. If disagreement > threshold, escalate to **up to 10 more** calls
3. Otherwise, stop at 3
4. **Benefit:** 30-50% compute savings vs always calling 5 times

### Q: Why per-criterion calls instead of joint prompts?

**A:** Per-criterion (one call per neuron) eliminates three biases:
- **Halo effect:** Good score on EC doesn't bleed into AL
- **Central tendency:** Judges don't average everything toward the middle
- **Leniency bias:** Each neuron scored independently

**Trade-off:** 107 calls/session vs 1-2 (higher latency, better quality)

### Q: What is Tobit censoring?

**A:** EC (Explicit Confidence) scores are sometimes unobserved (user off-screen during verification). Tobit is a statistical model that:
- Detects when EC is likely censored
- Returns **honest confidence intervals** (wider when uncertainty high)
- Replaces fake precision with real uncertainty

---

## FAQ — Corpus Growth

### Q: How does active learning work?

**A:** Active learning selects the most informative new chats to annotate:
1. **Uncertainty:** Chats where judge is most disagreeing
2. **Diversity:** Chats that differ from already-labeled ones
3. **Archetype:** Balance across user types (stage, domain)

**Result:** Corpus grows to 200 chats in 2-3 months (vs ~2 years random sampling)

### Q: What is "cleanlab audit"?

**A:** A mislabel detection tool that:
- Identifies confident vs at-risk labels in the gold set
- Flags top 10 suspects for manual review
- Doesn't auto-correct (human-in-loop only)

### Q: Why does the system need 200 chats?

**A:** 200 chats is the threshold where:
- κ^H (efficiency) falsification gate can pass
- LPA (archetype discovery) achieves > 70% agreement
- Statistical power is sufficient for DIF analysis

---

## FAQ — Fairness & Measurement

### Q: What is κ^H?

**A:** **κ^H = Efficiency Factor**

A per-user trait measuring how many tokens the human saved by using the AI. 
- **Falsification gate:** Var(κ^H) > 0.01 (prevents noise from masquerading as signal)
- **Status:** Data-gated (unlocks at n ≥ 200)

### Q: What is LPA (Latent Profile Analysis)?

**A:** An unsupervised clustering algorithm that:
- Discovers natural user archetypes from data
- Validates against 10 "decreed" archetypes (baseline specs)
- Flags archetype definitions that need revision

**Example:** If LPA finds 3 clusters but decreed archetypes are 10, something is wrong.

### Q: What is CRO (Competency Reference Overlay)?

**A:** **Competency Reference Overlay**

A z-score normalization system that:
- Normalizes κ^H by **competency cell** (education_stage × domain)
- Compares users within their cohort, not globally
- **Never public** (Commitment-12)

**Example:** Undergraduate STEM student compared to undergrad STEM peers, not to all users.

### Q: What is "Commitment-12"?

**A:** A commitment to **never surface z-scores publicly**:
- No leaderboards (would unfairly rank users)
- No percentiles (would enable comparison)
- No badges (would publicize relative performance)

Z-scores exist for **private self-diagnostic only.**

### Q: Will users see rankings or percentiles?

**A:** **No.** Commitment-12 explicitly prevents this. If a future feature wants to show z-scores, it requires explicit approval and infrastructure changes.

---

## FAQ — Deployment & Operations

### Q: What if cascaded replication isn't saving compute?

**A:** If savings < 20%, the disagreement threshold is too loose. Adjust:
```python
cascaded_evaluate(..., disagreement_threshold=0.25)  # Increase to escalate less often
```

### Q: What if the corpus stops growing?

**A:** Check:
1. Unlabeled pool size (should be > 20)
2. Annotation queue (should have capacity)
3. Active learning uncertainty scores (should be diverse)

If stalled: Contact PM to prioritize annotation or expand session collection.

### Q: What if κ^H gate fails?

**A:** Falsification gate failure (Var < 0.01) means S_human is noise, not signal. This **blocks κ^H activation.** Debug:
1. Check S_human computation (spot-check 10 chats)
2. Verify extraction logic is correct
3. If broken, fix and recompute entire corpus

### Q: Can we bypass data-gates?

**A:** **No.** Gates are load-bearing for fairness & quality. If a gate is blocking progress, the solution is:
1. Investigate root cause (not good data quality? insufficient corpus? bias issues?)
2. Fix the underlying problem
3. Retry gate

Forcing past a gate risks deploying a broken feature.

---

## FAQ — Troubleshooting

### Q: Judge returned an error, what do I do?

**A:** Check:
```
1. Is the judge service healthy?
   curl https://api.judge.internal/health

2. Is your API key valid?
   curl -H "Authorization: Bearer $JUDGE_API_KEY" \
        https://api.judge.internal/validate

3. Is the prompt malformed?
   Check the transcript for encoding issues

4. Is the judge cache full?
   SELECT COUNT(*) FROM judge_cache
```

If still stuck, contact judge provider support.

### Q: Per-criterion calls failing on some neurons

**A:** Check:
```
1. Are all 107 neurons in rubric_bank.py?
   from src.trait.judge.rubric_bank import list_all_neurons
   len(list_all_neurons()) == 107

2. Is the transcript empty?
   if not transcript or len(transcript) < 10:
       raise ValueError("Transcript too short")

3. Is JSON parsing failing?
   Look at error logs for malformed judge response
```

### Q: Tobit fitting not converging

**A:** Try:
```python
# Use smart initialization
from src.trait.extractors.per_dimension.ec_tobit import fit_tobit_ec

result = fit_tobit_ec(ec_scores, initial_params=None)  # Auto-init
if not result['convergence']:
    # Try with fewer iterations
    result = fit_tobit_ec(ec_scores, max_iter=100)
```

### Q: Active learning selecting same users repeatedly

**A:** Increase diversity constraint:
```python
selected = select_next_batch(
    ...,
    diversity_weight=0.8,  # Increase (0-1 scale)
    embedding_model='sentence-transformers/all-MiniLM-L6-v2'
)
```

---

## Glossary

### Core Concepts

| Term | Definition |
|------|-----------|
| **Cascaded Replication** | Judge calling strategy: 3 reps initially, escalate to 10 if disagreement > threshold |
| **Per-Criterion** | One independent judge call per neuron (vs joint prompt for all) |
| **Tobit Model** | Statistical model for left-censored data (EC unobserved off-screen) |
| **Active Learning** | Corpus selection via uncertainty × diversity sampling |
| **Cleanlab Audit** | Mislabel detection: confident vs at-risk labels |

### User Assessment

| Term | Definition |
|------|-----------|
| **κ^H** | Efficiency factor: tokens saved by human (info-theoretic measure) |
| **S_human** | Information bottleneck measure; numerator of κ^H |
| **LPA** | Latent Profile Analysis; unsupervised archetype discovery |
| **CRO** | Competency Reference Overlay; z-score normalization by cell |
| **DIF** | Differential Item Functioning; bias analysis by archetype |

### Architecture

| Term | Definition |
|------|-----------|
| **107 Neurons** | Fixed ontology: 8 dimensions × ~13-14 neurons each |
| **8 Dimensions** | EC, AL, PR, CS, CA, ES, CD, AUI |
| **4 Pillars** | Judge Output, Cognitive Ability, Synergy, User Context |
| **Baseline Capability Specs** | 10 archetype profiles with observable proof tasks |
| **Two-Table Event Log** | Separate `human_control_signals` + `ai_action_log` tables |

### Quality Gates

| Term | Definition |
|------|-----------|
| **Cascaded Savings** | Should be 30-50%; alert if < 20% |
| **Escalation Rate** | Should be < 30%; alert if > 40% |
| **Corpus Growth** | Should be 5+ chats/week; alert if < 2/week |
| **κ^H Falsification** | Var(κ^H) > 0.01; fails if human signal is noise |
| **LPA Agreement** | > 70% agreement with decreed archetypes |
| **Tobit CI Coverage** | ~95% coverage (confidence intervals should contain true values) |
| **IRT Discrimination** | > 0.8 per neuron; < 0.8 = ambiguous rubric |
| **Conformance Fitness** | > 0.8 (sessions should follow expected model) |

### Fairness & Privacy

| Term | Definition |
|------|-----------|
| **Commitment-12** | Never surface z-scores publicly (private diagnostic only) |
| **Cell Size** | Minimum N ≥ 10 per competency cell before z-score computation |
| **DIF Clearance** | Approval that CRO has no material biases by archetype/stage/domain |
| **Archetype** | User class (e.g., undergraduate STEM, K-12 teacher, professional data analyst) |
| **Competency Cell** | Intersection of education_stage × domain (e.g., "UG×STEM") |

### Deployments

| Term | Definition |
|------|-----------|
| **WAVE 0** | Cascaded, per-criterion, active learning, Tobit EC (immediate) |
| **WAVE 1** | IRT diagnostics, SSSR validation, conformance (alongside 0) |
| **WAVE 2** | κ^H substrate, LPA discovery (at n ≥ 200) |
| **WAVE 3** | CRO overlay (after DIF clearance) |
| **Data-Gate** | Precondition that must be met before activation (e.g., n ≥ 200) |

### Code Organization

| Path | Purpose |
|------|---------|
| `src/trait/judge/cascade_eval.py` | Cascaded replication logic |
| `src/trait/judge/per_criterion.py` | Per-criterion judge calls |
| `src/trait/judge/rubric_bank.py` | 107-neuron rubric definitions |
| `src/trait/extractors/per_dimension/ec_tobit.py` | Tobit censoring model |
| `src/trait/kappa_efficiency.py` | κ^H substrate (data-gated) |
| `calibration/active_learning.py` | Corpus selection pipeline |
| `calibration/cleanlab_audit.py` | Mislabel detection |
| `calibration/lpa_archetype_discovery.py` | LPA archetype discovery (data-gated) |
| `csl/validation/judge_irt.py` | IRT diagnostics |
| `csl/analytics/conformance.py` | Process-mining conformance |
| `src/claims/cro_overlay.py` | CRO z-score overlay (data-gated) |
| `contracts/baseline_capability_specs.yaml` | 10 archetype definitions |
| `alembic/versions/014_two_table_event_log.py` | Database migration |

---

## For More Information

- **Full Spec:** `v3.22_SpecDelta.md`
- **Completion Summary:** `v3_22_COMPLETION_SUMMARY.md`
- **Deployment Guide:** `v3_22_DEPLOYMENT_GUIDE.md`
- **Operational Runbooks:** `v3_22_OPERATIONAL_RUNBOOKS.md`
- **Code:** `feat/v3.22-twelve-upgrades` branch

---

**Last Updated:** 2026-06-26  
**Owner:** Engineering Team
