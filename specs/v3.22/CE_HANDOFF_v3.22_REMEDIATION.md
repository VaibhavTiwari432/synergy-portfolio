# CLAUDE ENGINEER HANDOFF — v3.22 REMEDIATION (AMENDED)

**Authority:** v3.22_SpecDelta.md + AUDIT_FINDINGS_AND_REMEDIATION.md  
**Priority:** 5 critical issues across 7 days  
**Acceptance:** All items must pass spec compliance + new test suite before merge  
**Status:** 87% ready; 4 targeted amendments applied below

---

## DAY 1 — CRITICAL PATH: ITEM #2 (RUBRIC_BANK.PY)

**Task:** Port all 92 missing neurons to complete the 107-neuron rubric bank.

**Source of Truth:** `contracts/contract_table.yaml` (lines 18+) + SAF_ARI_Final_Master_Compilation.md Appendix C.

**What to extract for each of 107 neurons:**
- `neuron_id` (e.g., "EC-01")
- `dimension` (AL, PR, EC, ES, CS, CD, AUI, CA)
- `title` (human-readable name)
- `scale_type` ("ordinal" 0–4 or "binary" 0–1 per spec)
- `scale_levels` (list of level names)
- `behavioral_anchors` (dict: level → description)
- `negative_criteria` (list: leniency-penalty conditions)

**Target:** All 107 neurons in `RUBRIC_BANK` dict.

**Acceptance Test:**
```python
from src.trait.judge.rubric_bank import list_all_neurons, get_rubric

neurons = list_all_neurons()
assert len(neurons) == 107, f"Expected 107, got {len(neurons)}"

for neuron_id in neurons:
    rubric = get_rubric(neuron_id)
    assert 'scale_levels' in rubric
    assert 'behavioral_anchors' in rubric
    assert len(rubric['behavioral_anchors']) == len(rubric['scale_levels'])
```

**Estimated Effort:** 6–8 hours.

**Blocker Status:** 🔴 RELEASE BLOCKER.

---

## DAYS 2–3 — TYPE A FIXES: ITEMS #3.2 AND #12.2

### ITEM #3.2: `kappa_efficiency.py` — Gaussian Likelihood

**Current:** Binary Bernoulli on continuous S_human ∈ [0,1].

**Problem:** S_human is continuous, not binary.

**Fix:** Gaussian likelihood.

```python
def log_likelihood(params, s_human_values):
    mu, sigma = params[:-1], params[-1]
    residuals = s_human_values - mu
    ll = -0.5 * np.sum(np.log(sigma**2) + (residuals / sigma)**2)
    return -ll

result = minimize(log_likelihood, [0.5, 0.1], 
                  bounds=[(None, None), (1e-3, None)])
mu_est, sigma_est = result.x

kappa_h = mu_est
var_kappa = sigma_est**2
falsification_pass = var_kappa > 0.01  # Signal, not noise
```

**Spec Authority:** v3.22_SpecDelta.md §3.2. Continuous Response Model: Samejima (1973). κ^H is a token-domain IRT ability parameter per §5.8d of the master spec.

**Acceptance Test:**
- Fit to synthetic Gaussian data with known μ, σ; verify parameter recovery ✓
- Falsification gate passes on diverse corpus, fails on flat corpus ✓

**Estimated Effort:** 2–3 hours.

---

### ITEM #12.2: `lpa_archetype_discovery.py` — Correct Metrics + Model Selection

**Current:** Hash-based encoding + hash-based agreement.

**Problems:** 
1. Hash instability across Python versions
2. Hash doesn't measure statistical similarity  
3. n_clusters hardcoded to 10

**Fix — Three parts:**

**Part A: Feature Encoding** (deterministic, not hash-based)
```python
from sklearn.preprocessing import LabelEncoder

education_stage_enc = LabelEncoder().fit_transform([r['education_stage'] for r in corpus])
domain_enc = LabelEncoder().fit_transform([r['domain'] for r in corpus])

X = np.column_stack([
    education_stage_enc,
    domain_enc,
    [r['ai_familiarity'] for r in corpus],
    [r['synergy_score'] for r in corpus],
    [r['s_human'] for r in corpus],
    [r['kappa_h'] for r in corpus],
])

X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-6)
```

**Part B: Model Selection (BIC)**
```python
from sklearn.mixture import GaussianMixture

best_bic, best_n = float('inf'), None
best_labels = None

for n_clusters in range(5, 15):
    gmm = GaussianMixture(n_components=n_clusters, random_state=42, n_init=10)
    labels = gmm.fit_predict(X)
    if gmm.bic(X) < best_bic:
        best_bic, best_n, best_labels = gmm.bic(X), n_clusters, labels

discovered_n_clusters = best_n
discovered_labels = best_labels
```

**Part C: Agreement Metric (Adjusted Rand Index)**
```python
from sklearn.metrics import adjusted_rand_score

archetype_to_id = {
    'SCHOOL_STUDENT_8_10': 0,
    'UNDERGRAD_STEM_Y2': 1,
    # ... all 10
}
decreed_labels = np.array([archetype_to_id[r.get('archetype_decreed')] 
                           for r in corpus])

agreement_ari = adjusted_rand_score(decreed_labels, discovered_labels)

if agreement_ari < 0.70:
    raise DataGatedError(f"LPA agreement {agreement_ari:.2%} < 70%")
```

**AMENDMENT #1 — Data-Gating Guard for Sparse Archetype Labels:**

The ARI comparison requires `archetype_decreed` to be populated in corpus records. At current corpus size (26 chats), this may be sparse. Add before ARI computation:

```python
records_with_archetype = [r for r in corpus if r.get('archetype_decreed')]
if len(records_with_archetype) < 50:
    return {
        'status': 'data_gated',
        'reason': f'archetype_decreed populated for only {len(records_with_archetype)}; need ≥50 for ARI',
        'agreement_ari': None,
    }
```

This prevents false gate failures from sparse labels.

**Acceptance Test:**
- On synthetic 10-cluster data, BIC selects n=10 ✓
- ARI recovers clusters correctly on diverse corpus ✓
- ARI < 0.70 on homogeneous corpus (gate works) ✓

**Estimated Effort:** 3–4 hours.

---

## DAYS 3–4 — TYPE B FIXES: ITEMS #3.1 AND #9

### ITEM #3.1: `judge_irt.py` — Bayesian Graded Response Model

**Current:** Logistic regression on n=1 sample per neuron.

**Problem:** GRM requires observations accumulated across **multiple chats per neuron**, not single observations.

**Critical Data Structure (AMENDMENT #2):**
- **Input:** `judge_replications[neuron_id]` = 2D array shape (N_chats, K_reps)
  - Each row is one chat's K judge replications on that neuron
  - Example: EC-01 has 26 chats × 5 reps = (26, 5) array
- **Accumulation:** Estimate `theta_i` per chat from K reps
  - `theta_i = mean(judge_replications[neuron_id][chat_i, :])`
- **Observations:** Fit against (theta_i, human_label_i) pairs across all N_chats

**Correct Implementation:**

```python
import pymc as pm
import numpy as np

def fit_grm_bayesian(judge_replications_per_neuron, human_gold_per_chat, n_min=30):
    """
    Fit GRM to accumulated judge replications across multiple chats.
    
    Args:
        judge_replications_per_neuron: dict[neuron_id] -> np.array shape (N_chats, K_reps)
        human_gold_per_chat: dict[chat_id] -> label (0-4)
        n_min: minimum chats required (default 30)
    
    Returns:
        dict[neuron_id] -> {discrimination, thresholds, interpretation, n_chats}
    """
    
    results = {}
    chat_ids = list(human_gold_per_chat.keys())
    
    for neuron_id, judge_reps_array in judge_replications_per_neuron.items():
        # judge_reps_array: shape (N_chats, K_reps)
        n_chats = judge_reps_array.shape[0]
        
        if n_chats < n_min:
            results[neuron_id] = {
                'error': f'n_chats={n_chats} < {n_min}',
                'discrimination': None,
                'thresholds': None,
                'n_chats': n_chats,
            }
            continue
        
        # Estimate theta per chat from replications (CRUCIAL STEP)
        theta_per_chat = judge_reps_array.mean(axis=1)  # shape (N_chats,)
        
        # Human labels in same order
        labels_per_chat = np.array([human_gold_per_chat[cid] for cid in chat_ids[:n_chats]])
        
        # Bayesian model: fit on accumulated (theta, label) pairs
        with pm.Model() as model:
            # Priors
            a = pm.Gamma('a', alpha=2, beta=0.5)  # Discrimination > 0
            
            # Thresholds (order-constrained for 4-level scale)
            b_raw = pm.Normal('b_raw', mu=[-1, 0, 1], sigma=2, shape=3)
            b = pm.math.sort(b_raw)
            
            # Ordered logistic likelihood
            obs = pm.OrderedLogistic(
                'obs',
                eta=a * theta_per_chat,  # Linear predictor per chat
                cutpoints=b,
                observed=labels_per_chat
            )
            
            # Inference
            trace = pm.sample(2000, return_inferencedata=True, progressbar=False, chains=2)
        
        # Extract posterior mean
        a_est = trace.posterior['a'].mean().item()
        b_est = trace.posterior['b'].mean(dim=['chain', 'draw']).values
        
        # Interpretation
        interpretation = ""
        if a_est < 0.8:
            interpretation += "LOW DISCRIMINATION (ambiguous rubric). "
        if np.max(np.diff(b_est)) > 1.5:
            interpretation += "WIDE THRESHOLDS (inconsistent scale). "
        if not interpretation:
            interpretation = "Acceptable IRT fit."
        
        results[neuron_id] = {
            'discrimination': a_est,
            'thresholds': b_est,
            'interpretation': interpretation,
            'n_chats': n_chats,
        }
    
    return results
```

**Spec Authority:** v3.22_SpecDelta.md §3.1. Standard: Samejima (1973) Continuous Response Model. The spec's §8.5 G-study gate (≥30 subjects × judge replications) requires this cross-chat accumulation.

**Acceptance Test:**
- On synthetic data (known a=1.2, b=[-1,0,1]), recover parameters within 0.1 tolerance ✓
- With n_chats=30, discrimination ∈ [0.8, 1.6] ✓
- With n_chats=10, output warning but still produce estimates ✓

**Estimated Effort:** 4–6 hours.

---

### ITEM #9: `conformance.py` — Token-Based Process Mining

**Current:** Cyclic index matching of event sequences.

**Problem:** Doesn't implement formal process model semantics.

**Spec Definition:** Per v3.22 Item #9 (van der Aalst 2016, pm4py), token-replay fitness.

**AMENDMENT #3 — Provide Working Petri Net Definition:**

CE needs at least one runnable Petri net to write acceptance tests. Here is the `problem_solving` session type:

```python
from pm4py.objects.petri_net.obj import PetriNet, Marking
from pm4py.objects.petri_net.utils import petri_utils

def build_problem_solving_net():
    """Build Petri net for problem-solving sessions: Frame → Gen → Verify → Integrate."""
    net = PetriNet("problem_solving")
    
    # Places
    start = petri_utils.add_place(net, "start")
    p_frame = petri_utils.add_place(net, "p_frame")
    p_gen = petri_utils.add_place(net, "p_gen")
    p_verify = petri_utils.add_place(net, "p_verify")
    p_integrate = petri_utils.add_place(net, "p_integrate")
    end = petri_utils.add_place(net, "end")
    
    # Transitions (ACTIVITY NAMES MUST MATCH ai_action_log.ai_act_type VALUES)
    t_frame = petri_utils.add_transition(net, "frame_problem", "frame_problem")
    t_gen = petri_utils.add_transition(net, "generate_solutions", "generate_solutions")
    t_verify = petri_utils.add_transition(net, "verify_solutions", "verify_solutions")
    t_integrate = petri_utils.add_transition(net, "integrate_learning", "integrate_learning")
    
    # Arcs (flow)
    petri_utils.add_arc_from_to(start, t_frame, net)
    petri_utils.add_arc_from_to(t_frame, p_frame, net)
    petri_utils.add_arc_from_to(p_frame, t_gen, net)
    petri_utils.add_arc_from_to(t_gen, p_gen, net)
    petri_utils.add_arc_from_to(p_gen, t_verify, net)
    petri_utils.add_arc_from_to(t_verify, p_verify, net)
    petri_utils.add_arc_from_to(p_verify, t_integrate, net)
    petri_utils.add_arc_from_to(t_integrate, p_integrate, net)
    petri_utils.add_arc_from_to(p_integrate, end, net)
    
    # Markings
    im = Marking({start: 1})
    fm = Marking({end: 1})
    
    return net, im, fm

# Global registry
PETRI_NETS = {
    'problem_solving': build_problem_solving_net(),
}
```

**CRITICAL:** The activity label names (`frame_problem`, `generate_solutions`, `verify_solutions`, `integrate_learning`) must match the enum values in Migration 014's `ai_action_log.ai_act_type` column. Verify alignment before implementation.

**Token-Replay Implementation:**

```python
from pm4py.algo.conformance.tokenreplay import apply as token_replay_apply

def conformance_check_session(session_id, event_sequence, session_type='problem_solving'):
    """
    Compute token-based conformance fitness.
    
    Returns: {fitness_score, fired, missing, trace_id}
    """
    
    petri_net_tuple = PETRI_NETS.get(session_type)
    if petri_net_tuple is None:
        return {
            'error': f'No Petri net defined for {session_type}',
            'fitness_score': None,
        }
    
    net, im, fm = petri_net_tuple
    
    # Run token replay
    fitness_dict = token_replay_apply(
        [event_sequence],  # Log as list of traces
        net,
        im,
        fm,
    )
    
    # Fitness for trace 0
    fitness = fitness_dict['fitness']
    
    return {
        'session_id': session_id,
        'session_type': session_type,
        'fitness_score': fitness,
        'n_events': len(event_sequence),
        'interpretation': 'Good fit' if fitness > 0.8 else 'Deviations detected',
    }
```

**Acceptance Test:**
- Perfect trace [frame_problem, generate_solutions, verify_solutions, integrate_learning]: fitness = 1.0 ✓
- Missing verify: [frame, gen, integrate]: fitness < 0.8 ✓
- Out-of-order: [frame, verify, gen, integrate]: fitness reflects deviation ✓

**Architectural Note:** Additional session types (e.g., `exploration`, `clarification`) require Petri net definitions from PM. Stub the architectural hooks; CE implements token-replay once nets are provided.

**Estimated Effort:** 6–8 hours (largest task).

**Spec Authority:** v3.22_SpecDelta.md §9, based on van der Aalst (2016), Syamsiyah et al. (2022).

---

## DAY 5 — QUALITY FIXES

### ITEM #12.1: BCS Gate Inconsistencies (1–2 hours)

Fix `contracts/baseline_capability_specs.yaml`:
- Line 38: SCHOOL_STUDENT gate vs capability count
- Line 116: "Slack, Slack" copy-paste error  
- Lines 280–309: AMATEUR_SELF_LEARNER gate vs capability count

### ITEM #6: Tobit Convergence Guard (30 minutes)

Add to `src/trait/extractors/per_dimension/ec_tobit.py`:

```python
if not result.success:
    logger.warning(f"Tobit optimizer diverged for {neuron_id}; using empirical CI")
    return {
        'ci_lo': np.percentile(ec_scores, 2.5),
        'ci_hi': np.percentile(ec_scores, 97.5),
        'convergence': False,
        'note': 'Optimizer diverged; empirical CI used',
    }
```

---

## DAYS 6–7 — VALIDATION & TEST SUITE

**Full Test Suite:** 70+ tests passing  
**Staged Deployment Readiness:** Ready for code review

---

## FINAL CHECKLIST FOR CE

- [ ] Item #2: 107 neurons ported ✓
- [ ] Item #3.1: Bayesian GRM (n_chats accumulation) ✓
- [ ] Item #3.2: Gaussian likelihood ✓
- [ ] Item #9: pm4py token-replay + problem_solving net ✓
- [ ] Item #12.2: BIC + ARI + archetype-sparsity guard ✓
- [ ] Item #12.1: BCS gates ✓
- [ ] Item #6: Convergence guard ✓
- [ ] Full test suite passing (70+ tests) ✓
- [ ] All fixes spec-compliant ✓

---

**Authority Chain:** This handoff supersedes earlier versions. Reference the spec documents directly.
