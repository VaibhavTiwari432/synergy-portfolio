# v3.22 Deployment Guide

**Version:** v3.22  
**Status:** Production-Ready (Testing Phase)  
**Last Updated:** 2026-06-26  
**Owner:** Engineering Team

---

## Pre-Deployment Checklist

### Code Review
- [ ] All 12 items code-reviewed for correctness
- [ ] All 56 tests passing on staging
- [ ] No regressions in existing functionality
- [ ] Non-negotiables upheld (ontology, no multipliers, backward compat)

### Testing
- [ ] Unit tests: 56/56 passing
- [ ] Integration tests: All WAVE 0-3 integration tests pass
- [ ] Performance: Judge compute savings measured (target: 30-50%)
- [ ] Data-gates: All gates raise errors when preconditions unmet

### Data Preparation
- [ ] Active learning corpus baseline established
- [ ] Cleanlab audit completed on gold set
- [ ] Tobit EC parameters fitted on v3.21 gold set
- [ ] All 107 neurons have anchored rubrics

### Infrastructure
- [ ] Database backup created
- [ ] Migration 014 validated (two-table event log)
- [ ] Configuration files verified (YAML, etc.)
- [ ] Logging and monitoring configured

---

## Deployment Steps

### Phase 1: Staging Deployment

**Duration:** 1 week  
**Goals:** Validate WAVE 0 items, establish baselines

#### 1.1 Merge to Main
```bash
git checkout main
git pull origin main
git merge feat/v3.22-twelve-upgrades
git push origin main
```

#### 1.2 Deploy to Staging
```bash
./scripts/v3_22_deploy.sh staging
```

**What this does:**
- Runs all unit tests
- Validates database migration (dry-run)
- Checks configurations
- Verifies data-gates

#### 1.3 Activate WAVE 0 Features

**Cascaded Replication:**
```python
from src.trait.judge.cascade_eval import cascaded_evaluate, batch_cascaded_evaluate

# In judge scoring pipeline:
result = cascaded_evaluate(
    judge_fn, 
    neuron_id, 
    transcript,
    target_phi=0.70,
    initial_reps=3,
    max_reps=10
)

# Log savings
savings = compute_savings(total_reps_used, fixed_n_reps=5, n_neurons=107)
print(f"Compute savings: {savings['savings_percent']:.1f}%")
```

**Per-Criterion Judge Calls:**
```python
from src.trait.judge.per_criterion import score_all_neurons

# Replace old joint-prompt scoring with per-criterion
result = score_all_neurons(judge_fn, transcript)
for neuron_id, response in result['results'].items():
    # Each neuron independently scored with anchored rubric
    score = response['score']
    reasoning = response['reasoning']
    confidence = response['confidence']
```

**Active Learning:**
```python
from calibration.active_learning import select_next_batch

# Monthly: select next batch for annotation
selected, metadata = select_next_batch(
    gold_set,
    unlabeled_pool,
    judge_replications,
    batch_size=5,
    archetype_targets=['ARCH_0', 'ARCH_1', ...]
)

# Prioritize high-uncertainty, under-represented archetypes
for chat_id in selected:
    print(f"Annotate: {chat_id} (uncertainty: {metadata['uncertainties'][chat_id]:.3f})")
```

**Tobit EC:**
```python
from src.trait.extractors.per_dimension.ec_tobit import apply_tobit_to_ec_scores

# For each EC score, compute honest confidence interval
for score in ec_scores:
    result = apply_tobit_to_ec_scores({'ec_score': score})
    # {ci_lo, ci_hi, censored, ...}
    # Widen CIs when censoring suspected (off-screen verification)
```

#### 1.4 Validation Checklist (Staging)

- [ ] Judge compute savings measured (document baseline)
- [ ] Per-criterion calls working without halo effects
- [ ] Active learning selecting diverse chats
- [ ] Tobit CIs computed without errors
- [ ] No regressions in existing Scope A functionality
- [ ] Event log concepts validated
- [ ] BCS specs accessible and valid

**Staging Duration:** 1 week (or until all checks pass)

---

### Phase 2: Production Deployment

**Duration:** Immediate after staging validation  
**Goals:** Roll out WAVE 0 to production, monitor baselines

#### 2.1 Apply Database Migration
```bash
./scripts/v3_22_deploy.sh production
```

**What this does:**
- Creates `human_control_signals` table
- Creates `ai_action_log` table
- Sets up indexes and constraints
- Can be rolled back if needed

#### 2.2 Enable WAVE 0 Features
- Cascaded replication: monitor judge savings
- Per-criterion calls: monitor quality improvements
- Active learning: monitor corpus growth rate
- Tobit EC: backfill v3.21 gold set with CIs

#### 2.3 Monitoring Dashboard

Create alerts for:
```
- Judge compute usage (should drop ~30-50%)
- Judge disagreement (should track with threshold)
- Active learning corpus size (track growth to n=200)
- Tobit EC CI widths (should be 20-30% relative to scores)
```

#### 2.4 Validation Checklist (Production)

- [ ] All WAVE 0 items working without errors
- [ ] No impact on existing Scope A functionality
- [ ] Compute savings within expected range
- [ ] Corpus growth on pace (5+ chats/month via active learning)
- [ ] Monitoring alerts configured

**Production Duration:** Ongoing (continuous monitoring)

---

### Phase 3: Data-Gated Item Activation

**Trigger:** Corpus reaches n ≥ 200  
**Estimated Timeline:** Month 2-3 (via active learning)

#### 3.1 Pre-Activation Checks

- [ ] Corpus size verified: `SELECT COUNT(*) FROM chats WHERE gold = TRUE` ≥ 200
- [ ] Archetype distribution balanced (no single type > 60%)
- [ ] κ^H data requirements met (s_human values computed for all)

#### 3.2 Activate κ^H and LPA

```python
from src.trait.kappa_efficiency import estimate_kappa_h
from calibration.lpa_archetype_discovery import discover_archetypes_via_lpa

# κ^H substrate
kh_result = estimate_kappa_h(s_human_values)
if not kh_result['falsification_pass']:
    raise DataGatedError("Human signal is noise; falsification gate failed")

# LPA discovery
labels, summary = discover_archetypes_via_lpa(corpus_200)
if summary['agreement_with_decreed'] < 0.70:
    print(f"WARNING: Low agreement with decreed archetypes ({summary['agreement_with_decreed']:.1%})")
    # Investigate archetype definitions
```

#### 3.3 Validation Checklist (WAVE 2)

- [ ] κ^H falsification gate passes
- [ ] LPA agreement with decreed > 70%
- [ ] Both items producing valid outputs
- [ ] No data quality issues detected

---

### Phase 4: CRO Overlay Activation

**Trigger:** DIF clearance complete  
**Estimated Timeline:** Month 3-4

#### 4.1 DIF Analysis

- [ ] Run Differential Item Functioning analysis
- [ ] Check for bias by archetype, stage, domain
- [ ] Document findings and mitigations

#### 4.2 Activate CRO (Commitment-12 Enforced)

```python
from src.claims.cro_overlay import compute_cro_z_scores, cro_report_with_commitment_12

# Compute z-scores by competency cell
z_result = compute_cro_z_scores(kappa_h_estimates, covariates)

# Report WITHOUT surfacing z-scores (Commitment-12)
report = cro_report_with_commitment_12(z_result, enable_z_surface=False)

# Result:
# {
#   'status': 'computed but gated',
#   'tier_level': 'Tier 3 (private)',
#   'z_scores_visible': False,
#   'leaderboard_visible': False,
# }

# To surface z-scores, requires explicit approval + infrastructure changes
```

#### 4.3 Validation Checklist (WAVE 3)

- [ ] DIF analysis cleared (no major biases)
- [ ] Z-scores computed for stable cells (N ≥ 10)
- [ ] Commitment-12 enforcement active (z never surfaced)
- [ ] CRO reporting available for diagnostics only

---

## Troubleshooting

### Issue: Cascaded Replication Not Escalating
**Diagnosis:** Check disagreement threshold
```python
# Review cascade decisions
for result in batch_results['results'].values():
    if result['escalated']:
        print(f"Escalated due to disagreement={result['disagreement']:.3f}")
```

**Fix:** Adjust `disagreement_threshold` or `target_phi` parameters

### Issue: Per-Criterion Judge Calls Failing
**Diagnosis:** JSON parsing errors
```python
# Check malformed responses
errors = [r for r in results.values() if r.get('error')]
for err in errors:
    print(f"Parse error: {err['error_message']}")
```

**Fix:** Review judge response format; ensure JSON compliance

### Issue: Active Learning Not Selecting Diverse Chats
**Diagnosis:** Archetype imbalance in unlabeled pool
```python
# Verify pool distribution
for arch, chats in archetype_groups.items():
    print(f"{arch}: {len(chats)} chats")
```

**Fix:** Expand unlabeled pool or adjust sampling weights

### Issue: κ^H Falsification Gate Failing
**Diagnosis:** Human signal is noise (Var < 0.01)
```python
# Investigate S_human distribution
print(f"S_human mean: {s_human.mean():.3f}, std: {s_human.std():.3f}")
```

**Fix:** Review S_human computation; may indicate measurement issue

### Issue: CRO Cells Too Small (N < 10)
**Diagnosis:** Cell size insufficient for normalization
```python
# Review cell distribution
for cell, data in cells.items():
    print(f"{cell}: N={len(data)}")
```

**Fix:** Expand corpus or increase cell-size threshold (requires approval)

---

## Rollback Procedures

### Rollback WAVE 0 (Cascaded, Per-Criterion, etc.)
1. Revert to previous judge.py
2. Disable cascade evaluation flag
3. Use per-neuron scores from existing system
4. Test before rolling back further

### Rollback Database Migration (Migration 014)
```bash
# Backup current state first
alembic current

# Rollback one migration
alembic downgrade -1

# Verify rollback
alembic current
```

### Full Rollback to v3.21
```bash
git revert HEAD  # Creates rollback commit
git push origin main

# Roll back database
alembic downgrade --sql <v3.21 migration stamp>
```

---

## Post-Deployment Monitoring

### Metrics to Track

**Judge Quality:**
- Cascaded vs fixed-N compute ratio
- Judge disagreement distribution
- Confidence interval widths (EC)

**Corpus Growth:**
- Monthly new chats via active learning
- Archetype distribution
- Uncertainty scores of selected chats

**Fairness:**
- κ^H distribution by archetype
- LPA cluster sizes
- DIF violations (if any)

### Alerting Thresholds

| Metric | Alert If | Action |
|--------|----------|--------|
| Cascade escalation rate | > 40% | Investigate judge variance |
| κ^H var < 0.01 | True | Human signal failing falsification |
| LPA agreement < 70% | True | Review archetype definitions |
| Cell N < 10 | True | Need more corpus data |
| Compute savings < 20% | True | Cascade threshold may be too loose |

---

## Support & Escalation

**Issue Type** | **Owner** | **Escalate If**
--- | --- | ---
Judge quality | Chief Engineer | Disagreement unexpectedly high
Active learning | Data team | Corpus growth stalling
κ^H/LPA | ML team | Falsification gate failing
CRO/DIF | Privacy/Fairness | Commitment-12 violated

---

## Sign-Off

- [ ] Deployment lead: ___________  
- [ ] QA lead: ___________  
- [ ] Security lead: ___________  
- [ ] Product lead: ___________  

**Deployment Date:** __________  
**Status:** ○ Ready | ○ On Hold | ○ Complete
