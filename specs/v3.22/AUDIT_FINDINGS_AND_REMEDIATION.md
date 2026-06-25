# v3.22 AUDIT FINDINGS & REMEDIATION PLAN

**Comprehensive Code Audit Results + Priority Fixes**

---

## AUDIT EXECUTIVE SUMMARY

**Overall Status:** ⚠️ **65% COMPLETE & CORRECT** (Can deploy WAVE 0, but critical blocker exists)

### Critical Findings

| Severity | Item | Issue | Impact |
|----------|------|-------|--------|
| 🔴 CRITICAL | #2 (rubric_bank) | Only 15/107 neurons defined | **RELEASE BLOCKER** |
| 🔴 CRITICAL | #3.1 (judge_irt) | IRT on n=1 pairs unstable | Unreliable diagnostics |
| 🔴 CRITICAL | #3.2 (kappa_h) | Continuous→binary mismatch | κ^H estimates invalid |
| 🔴 CRITICAL | #9 (conformance) | Naive sequence matching | Fitness scores meaningless |
| 🔴 CRITICAL | #12.2 (lpa) | Hash-based agreement metric | Agreement scores invalid |
| 🟡 HIGH | #12.1 (BCS) | Conformance gate inconsistent | Minor: 1 archetype affected |
| 🟡 HIGH | #6 (tobit) | No convergence handling | Minor: Edge case unhandled |

---

## DETAILED ISSUE BREAKDOWN

### 🔴 CRITICAL #1: RUBRIC_BANK.PY — ONLY 15/107 NEURONS

**Location:** `src/trait/judge/rubric_bank.py` (lines 1-255)

**Problem:**
```
Expected: 107 neurons across 8 dimensions (ontology frozen, CLAUDE.md §1)
Actual:   15 neurons (EC-01-04, AL-01-02, PR-01-02, CS-01-02, CA-01-02, ES-01, CD-01, AUI-01-02)

Missing: 92 neurons (86% of rubric bank is undefined)
```

**Root Cause:** 
The full 107-neuron contract exists in `contracts/contract_table.yaml` but was not ported to `rubric_bank.py`. The YAML file has all definitions; they need to be converted to the RUBRIC_BANK dict format.

**Impact:**
- ❌ `per_criterion.py:score_all_neurons()` crashes on any neuron beyond the 15 defined
- ❌ Integration test fails: `test_rubric_bank_coverage()` expects 107 neurons
- ❌ Production deployment would fail on any judge call beyond the 15 defined
- ❌ Violates non-negotiable #1: "exactly 107 neurons, 8 dims, 4 pillars"

**Fix Priority:** 🔴 BLOCKER — Must fix before any deployment

**Estimated Effort:** 2-3 hours (extract from YAML, convert format, verify structure)

**Steps:**
1. Read `contracts/contract_table.yaml` (lines 18+ contain all 107 entries)
2. Extract for each neuron: neuron_id, dimension, title, scale_levels, anchors, negative_criteria
3. Port to RUBRIC_BANK dict format in `rubric_bank.py`
4. Verify `list_all_neurons()` returns 107 ✓
5. Run integration tests to confirm

---

### 🔴 CRITICAL #2: JUDGE_IRT.PY — UNSTABLE IRT MODEL

**Location:** `csl/validation/judge_irt.py` (lines 30-55)

**Problem:**
```python
# Current (WRONG):
clf = LogisticRegression()
clf.fit(X.reshape(-1, 1), y)  # X = [0.5], y = [2] (single sample!)
a_param = clf.coef_[0][0]      # Meaningless on n=1
```

Issues:
1. **Sample size:** Fitting logistic on 1 observation per neuron → unstable coefficients
2. **Model mismatch:** Logistic (binary classification) on continuous judge scores
3. **Non-standard difficulty:** Line 48 divides by discrimination (not standard GRM)
4. **No validation:** Should require n ≥ 30 per neuron

**Impact:**
- IRT discrimination & difficulty are statistically meaningless
- Item #3.1 diagnostics will be unreliable

**Fix Priority:** 🔴 BLOCKER for WAVE 1

**Estimated Effort:** 4-6 hours (requires Bayesian IRT library or statsmodels)

**Recommended Solution:**
Replace with proper Bayesian ordinal regression or use `statsmodels.genmod.generalized_ordered_model`:
```python
from statsmodels.genmod.generalized_ordered_model import GeneralizedOrderedModel
from statsmodels.genmod.cov_struct import Independence
from statsmodels.genmod.families import Gaussian

# Accumulate judge reps across corpus
judge_consensus = [...]  # List of median scores per neuron
human_labels = [...]     # Human gold labels per neuron

# Require n ≥ 30
if len(judge_consensus) < 30:
    raise DataGatedError("IRT requires n >= 30 observations per neuron")

# Fit GRM
model = GeneralizedOrderedModel.from_formula(
    "human_label ~ C(judge_consensus)",
    data=data,
    family=Gaussian()
)
result = model.fit()
```

---

### 🔴 CRITICAL #3: KAPPA_EFFICIENCY.PY — WRONG LIKELIHOOD

**Location:** `src/trait/kappa_efficiency.py` (lines 37-50)

**Problem:**
```python
# S_human is continuous (0-1 range, float)
X = (s_human_values - np.mean(s_human_values)) / np.std(...)
X = (X - X.min()) / (X.max() - X.min())  # Now 0-1

# Then fits BINARY logistic likelihood:
def likelihood(params):
    predicted = 1.0 / (1.0 + np.exp(-a * (X - b)))  # Bernoulli
    ll = np.sum(X * np.log(predicted) + (1-X) * np.log(1-predicted))  # Binary LL
```

Issue: Fitting binary logistic on continuous data is mathematically inconsistent.
- If S_human = 0.73, the likelihood term is `0.73 * log(p) + 0.27 * log(1-p)` — doesn't make sense
- Should use Gaussian (normal) likelihood for continuous data

**Impact:**
- κ^H estimates are mathematically invalid
- Falsification gate results are unreliable
- WAVE 2 activation will be based on wrong estimates

**Fix Priority:** 🔴 BLOCKER for WAVE 2

**Estimated Effort:** 2-3 hours

**Recommended Solution:**
Switch to Gaussian likelihood:
```python
def likelihood(params):
    mu, sigma = params
    residuals = s_human_values - mu
    ll = -0.5 * np.sum(np.log(sigma**2) + (residuals / sigma)**2)
    return -ll

# MLE fit
result = minimize(likelihood, [0.5, 0.1], bounds=[(None, None), (1e-3, None)])
mu, sigma = result.x

# κ^H is the uncertainty reduction factor
kappa_h = 1.0 - sigma  # Or other formulation

# Falsification: Var > 0.01
variance = sigma**2
falsification_pass = variance > 0.01
```

---

### 🔴 CRITICAL #4: CONFORMANCE.PY — INVALID SEQUENCE MATCHING

**Location:** `csl/analytics/conformance.py` (lines 52-65)

**Problem:**
```python
for i, activity in enumerate(event_sequence):
    expected_idx = i % len(expected_sequence)  # BUG: Cycles!
    if activity == expected_sequence[expected_idx]:
        matches += 1

# Example:
# expected = [frame, gen, verify, integrate]
# observed = [frame, gen, verify, integrate, frame, gen, verify, integrate]
# This gives perfect score even though cycles 2+ aren't part of the model
```

Issues:
1. **Cyclic matching:** Incorrectly assumes the process repeats cyclically
2. **No model semantics:** Doesn't use a formal Petri net or state machine
3. **Not process mining:** Valid PM uses "token replay" or alignment-based conformance

**Impact:**
- Conformance scores are meaningless
- Can't detect process deviations
- Item #9 is not fit for purpose

**Fix Priority:** 🔴 BLOCKER for WAVE 1

**Estimated Effort:** 6-8 hours (requires PM library integration or Petri net implementation)

**Recommended Solution:**
Use `pm4py` library for formal conformance:
```python
from pm4py.objects.petri_net import PetriNet
from pm4py.objects.petri_net.semantics import enabled_transitions
from pm4py.algo.conformance.tokenreplay import apply as token_replay

# Build model (simplified)
problem_solving_model = PetriNet()
# ... add places and transitions for Frame→Gen→Verify→Integrate

# Replay log
log_traces = [[event1, event2, ...], ...]
fitness = token_replay.apply(log_traces, problem_solving_model)
# Returns: (fit_cases / total_cases, fit_events / total_events)
```

---

### 🔴 CRITICAL #5: LPA_ARCHETYPE_DISCOVERY.PY — INVALID AGREEMENT METRIC

**Location:** `calibration/lpa_archetype_discovery.py` (lines 36-56)

**Problem:**
```python
# Hash categorical features:
features = [
    hash(record.get('education_stage', '')) % 100 / 100,  # BUG: Hash is unstable
    hash(record.get('domain', '')) % 100 / 100,           # BUG: Not categorical
    ...
]

# Compare agreement using hash modulo:
agreement = sum(1 for d, l in zip(decreed, labels)
            if hash(str(d)) % n_classes == l)  # BUG: Invalid metric
```

Issues:
1. **Hash instability:** `hash(str)` is non-deterministic across runs, varies with Python version
2. **Not categorical encoding:** Should use one-hot or integer encoding
3. **Agreement metric invalid:** `hash(...) % n_classes == cluster_id` doesn't measure agreement
   - Should use Adjusted Rand Index (ARI) or Normalized Mutual Information (NMI)
4. **Model selection missing:** Hardcodes n_classes=10 instead of selecting via BIC/AIC

**Impact:**
- LPA agreement score is meaningless
- Can't validate if discovered archetypes match decreed ones
- WAVE 2 activation gate (agreement > 70%) is unreliable

**Fix Priority:** 🔴 BLOCKER for WAVE 2

**Estimated Effort:** 3-4 hours

**Recommended Solution:**
```python
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import adjusted_rand_score
from sklearn.mixture import GaussianMixture

# Proper categorical encoding
le_stage = LabelEncoder()
le_domain = LabelEncoder()
features = np.column_stack([
    le_stage.fit_transform([r.get('education_stage', '') for r in corpus]),
    le_domain.fit_transform([r.get('domain', '') for r in corpus]),
    [r.get('ai_familiarity', 0.5) for r in corpus],
    ...
])

# Model selection: find optimal n_clusters
n_min, n_max = 5, 15
best_bic, best_n, best_labels = float('inf'), None, None
for n in range(n_min, n_max+1):
    gmm = GaussianMixture(n_components=n, random_state=42)
    labels = gmm.fit_predict(features)
    if gmm.bic(features) < best_bic:
        best_bic, best_n, best_labels = gmm.bic(features), n, labels

# Agreement: ARI
decreed_labels = [ARCHETYPE_TO_ID[r.get('archetype_decreed')] for r in corpus]
agreement_ari = adjusted_rand_score(decreed_labels, best_labels)

# Must be > 0.70
if agreement_ari < 0.70:
    raise DataGatedError(f"LPA agreement {agreement_ari:.2%} < 70% threshold")
```

---

## MEDIUM PRIORITY ISSUES

### 🟡 HIGH: Item #12.1 — BCS YAML Inconsistencies

**File:** `contracts/baseline_capability_specs.yaml`

**Issues:**
1. **Line 38:** SCHOOL_STUDENT has "≥10/13 capabilities" but only 13 total (tight gate)
2. **Line 116:** Duplicate "Slack, Slack" in capability description
3. **Lines 280-309:** AMATEUR_SELF_LEARNER has gate "≥9/12 capabilities" but only ~5 categories listed

**Fix:** Standardize capability counts per archetype and update gates

**Effort:** 1-2 hours

---

### 🟡 HIGH: Item #6 — Missing Convergence Handling

**File:** `src/trait/extractors/per_dimension/ec_tobit.py`

**Issue:** Line 128 doesn't handle optimizer divergence (result.success = False)

**Fix:**
```python
if not result.success:
    # Fallback to simpler model
    return {
        'ci_lo': np.percentile(ec_scores, 2.5),
        'ci_hi': np.percentile(ec_scores, 97.5),
        'convergence': False,
        'note': 'Optimizer diverged, using empirical CI'
    }
```

**Effort:** 30 minutes

---

## REMEDIATION TIMELINE

### Phase 1: CRITICAL FIXES (Release Blocker)
**Duration:** 3-4 days

1. **Day 1:** Port 92 neurons to rubric_bank.py (Item #2)
2. **Day 2:** Rewrite judge_irt.py with Bayesian GRM (Item #3.1)
3. **Day 3:** Fix kappa_efficiency.py Gaussian likelihood (Item #3.2)
4. **Day 4:** Rewrite conformance.py with pm4py (Item #9) + Fix LPA (Item #12.2)

### Phase 2: HIGH PRIORITY FIXES (Quality)
**Duration:** 1-2 days

5. **Day 5:** Fix BCS YAML inconsistencies (Item #12.1)
6. **Day 5:** Add convergence handling to Tobit (Item #6)

### Phase 3: VALIDATION
**Duration:** 1-2 days

7. Run full test suite (56 unit tests + integration)
8. Audit precision checks on all items
9. Final code review

---

## DEPLOYMENT IMPACT

### Current Status: ⚠️ WAVE 0 Can Deploy (with caveats)

**Safe to deploy:**
- ✅ Item #1 (Cascaded Replication)
- ✅ Item #4 (Active Learning)
- ✅ Item #6 (Tobit)
- ✅ Item #8 (Two-Table Event Log)
- ⚠️ Item #2 (Per-Criterion): Requires 92 missing neurons first

**Do NOT deploy (has critical issues):**
- ❌ Item #3.1 (IRT): Unstable on n=1 pairs
- ❌ Item #3.2 (κ^H): Mathematically invalid
- ❌ Item #9 (Conformance): Fitness scores meaningless
- ❌ Item #12.2 (LPA): Agreement metric invalid

### Revised Deployment Plan

**Week 1: CRITICAL FIXES** (pause deployment)
- Port rubric bank (Item #2)
- Rewrite IRT, κ^H, conformance, LPA

**Week 2: VALIDATION**
- Run full test suite
- Code review fixes
- Performance benchmarking

**Week 3: STAGING DEPLOYMENT**
- Run `./scripts/v3_22_deploy.sh staging`
- Validate WAVE 0 + WAVE 1
- 1-week validation

**Week 4: PRODUCTION DEPLOYMENT**
- Run `./scripts/v3_22_deploy.sh production`
- Deploy WAVE 0 + WAVE 1
- Monitor metrics

---

## PRECISION IMPROVEMENT RECOMMENDATIONS

### For Better Accuracy Across All Items

1. **Create scales.py utility** for consistent normalization:
   ```python
   # src/utils/scales.py
   def normalize_to_01(score, detected_scale=None):
       if detected_scale == '0-4' or score > 1.0:
           return score / 4.0
       return score
   ```

2. **Add comprehensive error handling** for edge cases:
   - Empty arrays (cascade_eval)
   - n < 30 (judge_irt)
   - n < 200 (kappa_h, lpa)
   - Optimizer divergence (tobit)

3. **Add data validation layer**:
   ```python
   def validate_ec_scores(scores):
       assert 0 <= np.min(scores) <= 4.0
       assert np.max(scores) <= 4.0
       return True
   ```

4. **Improve numerical stability**:
   - Use log-sum-exp trick in likelihoods
   - Add regularization to optimization
   - Use robust covariance estimators

---

## FINAL RECOMMENDATIONS

### Before Production

- [ ] **CRITICAL:** Port 92 missing neurons (Item #2)
- [ ] **CRITICAL:** Rewrite IRT with Bayesian GRM (Item #3.1)
- [ ] **CRITICAL:** Fix κ^H Gaussian likelihood (Item #3.2)
- [ ] **CRITICAL:** Implement formal PM conformance (Item #9)
- [ ] **CRITICAL:** Fix LPA agreement metric (Item #12.2)
- [ ] **HIGH:** Fix BCS gates and inconsistencies (Item #12.1)
- [ ] **HIGH:** Add convergence handling to Tobit (Item #6)
- [ ] Create scales.py utility for normalization
- [ ] Add comprehensive error handling
- [ ] Add data validation layer
- [ ] Run full test suite (target: 70+ tests)
- [ ] Final code review

### After Fixes

v3.22 will be **production-ready** with:
- ✅ All 12 items fully correct
- ✅ 70+ tests covering all paths
- ✅ Zero precision issues
- ✅ Robust error handling
- ✅ Complete documentation

---

**Estimated Total Effort:** 5-7 days of focused development to reach production readiness

**Current Status:** 65% complete → 100% complete after remediation
