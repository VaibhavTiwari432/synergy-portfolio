# v3.22 Operational Runbooks

**Quick reference for common operations and scenarios.**

---

## Table of Contents

1. [Daily Checks](#daily-checks)
2. [Weekly Reviews](#weekly-reviews)
3. [Incident Response](#incident-response)
4. [Corpus Growth Management](#corpus-growth-management)
5. [Judge Quality Monitoring](#judge-quality-monitoring)
6. [Data-Gate Activation](#data-gate-activation)

---

## Daily Checks

### 1. Judge Health Verification

**Purpose:** Ensure judge is responding and cascaded replication is working  
**Frequency:** Daily (start of shift)  
**Duration:** 5 minutes

```bash
# Step 1: Check judge connectivity
curl -X POST https://api.judge.internal/health \
  -H "Authorization: Bearer $JUDGE_API_KEY" \
  -d '{"test": true}'

# Expected: 200 OK with {"status": "healthy"}

# Step 2: Sample cascaded evaluation
python3 << 'EOF'
from src.trait.judge.cascade_eval import cascaded_evaluate
import json

# Test on 1 neuron
result = cascaded_evaluate(
    judge_fn, 
    'EC-01',
    'Sample test transcript.',
    target_phi=0.70,
    initial_reps=3,
    max_reps=5
)

# Should complete in < 30 seconds
print(f"Judge responding: {result['score']}")
print(f"Reps used: {result['n_reps']}")
print(f"Escalated: {result['escalated']}")
EOF

# Expected: Score in [0, 4], n_reps in [3, 5], no errors
```

**Alert If:**
- Judge returns HTTP errors
- Response time > 60 seconds
- Cascaded replication fails or timeout

---

### 2. Active Learning Corpus Status

**Purpose:** Track corpus growth trajectory  
**Frequency:** Daily  
**Duration:** 2 minutes

```bash
# Check corpus size and growth rate
python3 << 'EOF'
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('synergy.db')
cursor = conn.cursor()

# Current size
cursor.execute("SELECT COUNT(*) FROM chats WHERE gold = TRUE")
total_gold = cursor.fetchone()[0]

# Weekly growth
week_ago = datetime.now() - timedelta(days=7)
cursor.execute(
    "SELECT COUNT(*) FROM chats WHERE gold = TRUE AND created_at > ?",
    (week_ago,)
)
weekly_growth = cursor.fetchone()[0]

print(f"Total gold: {total_gold}")
print(f"Weekly growth: {weekly_growth}")
print(f"On pace for n=200 in: {(200 - total_gold) / (weekly_growth / 7):.1f} days")

conn.close()
EOF

# Expected: 5+ new chats/week (on pace for n=200 in 2-3 months)
```

**Alert If:**
- Growth rate < 2/week (stalling)
- Corpus declining (data loss)
- Archetype balance skewed (> 60% one type)

---

### 3. Compute Savings Verification

**Purpose:** Confirm cascaded replication is saving compute  
**Frequency:** Daily  
**Duration:** 5 minutes

```python
# In monitoring dashboard
from src.trait.judge.cascade_eval import compute_savings

# After each batch:
total_reps_yesterday = get_total_judge_calls_yesterday()  # From logs
fixed_n_reps = 5  # What we would have used
n_neurons = 107

savings = compute_savings(total_reps_yesterday, fixed_n_reps, n_neurons)

print(f"Reps yesterday: {total_reps_yesterday}")
print(f"Savings: {savings['savings_percent']:.1f}%")

# Alert if savings < 20%
if savings['savings_percent'] < 20:
    alert("Cascaded replication not saving compute; investigate disagreement threshold")
```

**Expected:** 30-50% savings  
**Alert If:** < 20% savings (threshold too loose)

---

## Weekly Reviews

### 1. Judge Quality Analysis

**Purpose:** Detect judge drift or rubric ambiguity  
**Frequency:** Weekly (end of week)  
**Duration:** 30 minutes

```python
from csl.validation.judge_irt import fit_grm_to_judge_reps

# Collect all judge replications from week
judge_reps = get_cascaded_reps_from_week()
human_gold = get_gold_labels()

# Fit IRT model
irt_results = fit_grm_to_judge_reps(judge_reps, human_gold)

# Analyze per-neuron
for neuron_id, result in irt_results.items():
    if result.get('error'):
        print(f"⚠️  {neuron_id}: IRT fitting failed")
    else:
        a = result['discrimination']
        d = result['difficulty']
        
        if a < 0.8:
            print(f"⚠️  {neuron_id}: LOW DISCRIMINATION ({a:.2f}) — rubric ambiguous")
        if abs(d) > 2.0:
            print(f"⚠️  {neuron_id}: EXTREME DIFFICULTY ({d:.2f}) — check prompt")

print("✓ Weekly IRT analysis complete")
```

**Actions:**
- `LOW DISCRIMINATION` → Refine rubric for that neuron
- `EXTREME DIFFICULTY` → Review judge prompt; may be too strict/lenient

---

### 2. Active Learning Quality Check

**Purpose:** Verify mislabel detection is working  
**Frequency:** Weekly  
**Duration:** 15 minutes

```python
from calibration.cleanlab_audit import audit_gold_set_for_mislabels

gold_set = get_gold_chats()
judge_scores = get_latest_judge_scores()

audit = audit_gold_set_for_mislabels(gold_set, judge_scores)

print(f"Total gold: {len(gold_set)}")
print(f"Confident labels: {audit['confident_count']}")
print(f"At-risk labels: {audit['at_risk_count']}")

if audit['top_suspicious']:
    print("\nTop 10 suspects (review manually):")
    for chat_id, score, reason in audit['top_suspicious'][:10]:
        print(f"  {chat_id}: {reason} (judge={score:.2f})")

# Create review queue
if len(audit['top_suspicious']) > 5:
    create_pr("Weekly mislabel review", audit['top_suspicious'][:10])
```

**Action:** Review and re-annotate top 10 suspects if any

---

### 3. Corpus Diversity Assessment

**Purpose:** Ensure active learning is selecting diverse chats  
**Frequency:** Weekly  
**Duration:** 10 minutes

```python
import numpy as np

# Get diversity metrics from active learning batch
this_week_selected = get_batch_from_this_week()

# Check archetype balance
archetypes = {}
for chat in this_week_selected:
    arch = chat['archetype']
    archetypes[arch] = archetypes.get(arch, 0) + 1

print("Archetype distribution (selected this week):")
for arch, count in sorted(archetypes.items()):
    pct = count / len(this_week_selected) * 100
    print(f"  {arch}: {count} ({pct:.0f}%)")

# Alert if any archetype > 60%
max_pct = max(archetypes.values()) / len(this_week_selected) * 100
if max_pct > 60:
    print(f"⚠️  IMBALANCE: {max(archetypes, key=archetypes.get)} at {max_pct:.0f}%")
    print("    → Increase diversity sampling weight")
```

**Action:** Adjust archetype sampling weights if imbalanced

---

## Incident Response

### Scenario 1: Judge Timeouts Increasing

**Symptom:** Judge latency > 60 seconds or 5XX errors rising  
**Time to resolve:** 30 minutes

**Diagnosis:**
```bash
# Check judge service health
kubectl logs -l app=judge --tail=100 | grep -i error

# Check database load
SELECT COUNT(*) FROM judge_cache WHERE created_at > NOW() - INTERVAL 1 HOUR;

# Check API key validity
curl -X POST https://api.judge.internal/validate \
  -H "Authorization: Bearer $JUDGE_API_KEY"
```

**Fix:**
1. **If cache overfilled:** Clear old cache entries (keep last 7 days)
2. **If API key expired:** Rotate to backup key, generate new one
3. **If service unhealthy:** Scale up judge replicas or restart service
4. **If cascaded threshold too low:** Increase disagreement_threshold (fewer escalations)

**Escalation:**
- After 2 hours: Page on-call judge provider
- After 4 hours: Activate fallback (use fixed-N replication)

---

### Scenario 2: Corpus Growth Stalling

**Symptom:** < 2 chats/week for 2+ weeks  
**Time to resolve:** 1-2 days

**Diagnosis:**
```python
# Check unlabeled pool size
import sqlite3
conn = sqlite3.connect('synergy.db')
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM chats WHERE gold IS NULL")
unlabeled_count = cursor.fetchone()[0]

print(f"Unlabeled chats: {unlabeled_count}")

# Check annotation queue status
cursor.execute(
    "SELECT status, COUNT(*) FROM annotation_queue GROUP BY status"
)
for status, count in cursor.fetchall():
    print(f"  {status}: {count}")
```

**Fix:**
1. **If no unlabeled chats:** Expand session collection (increase sampling)
2. **If annotation queue full:** Hire annotators or deprioritize non-critical items
3. **If selection is slow:** Reduce active learning batch size or turn off diversity constraint

**Escalation:**
- Alert PM: corpus growth off-track for n=200 deadline

---

### Scenario 3: κ^H Falsification Gate Failing

**Symptom:** Var(κ^H | model) < 0.01 (message at activation attempt)  
**Time to resolve:** 1-2 days (investigation), 1+ week (fix)

**Diagnosis:**
```python
from src.trait.kappa_efficiency import estimate_kappa_h
import numpy as np

s_human_values = get_s_human_for_corpus()

print(f"S_human mean: {s_human_values.mean():.3f}")
print(f"S_human std: {s_human_values.std():.3f}")

result = estimate_kappa_h(s_human_values, verbose=True)

if not result['falsification_pass']:
    print("⚠️  HUMAN SIGNAL IS NOISE")
    print("    → Investigate S_human computation")
    print("    → Check if extraction is correctly measuring tokens saved")
```

**Root Causes:**
- S_human extraction is broken (always returns same value)
- Corpus doesn't have enough diversity in human contribution
- Token counting is off

**Fix:**
1. Verify S_human computation on 10 random chats (spot check)
2. Plot S_human distribution (should be multimodal, not mono)
3. If broken: Fix extraction logic and recompute for all corpus
4. Retry κ^H fitting

---

## Corpus Growth Management

### Monthly Growth Target Planning

**Goal:** Reach n=200 for WAVE 2 activation  
**Timeline:** 2-3 months (5+ chats/week required)

```python
from calibration.active_learning import compute_corpus_growth_schedule

# Plan: How many chats needed?
current_size = 26  # v3.21 gold set
target_size = 200
batch_size = 5  # Monthly batch
num_months = 3

schedule = compute_corpus_growth_schedule(
    current_size, target_size, batch_size, num_months
)

print("Growth schedule:")
for month, cumulative in enumerate(schedule['cumulative_per_month'], 1):
    print(f"  Month {month}: {cumulative} chats")
    if cumulative >= 200:
        print(f"  ✓ Reaches n=200 in Month {month}")
        break
```

**Monthly Checklist:**

**Start of Month:**
- [ ] Verify unlabeled pool size ≥ 20
- [ ] Review archetype distribution
- [ ] Check active learning uncertainty scores

**Mid-Month:**
- [ ] Batch selected, sent for annotation
- [ ] Annotators assigned
- [ ] Annotation deadline: end of month

**End of Month:**
- [ ] New chats added to gold set
- [ ] Verify total count
- [ ] If off-track: escalate to PM

---

## Judge Quality Monitoring

### Daily Judge Disagreement Tracking

```python
# Log to monitoring system
from src.trait.judge.cascade_eval import batch_cascaded_evaluate

results = batch_cascaded_evaluate(judge_fn, neuron_ids, transcript)

for neuron_id, result in results['results'].items():
    disagreement = result['disagreement']
    escalated = result['escalated']
    
    # Metric: disagreement_by_neuron
    log_metric(
        'judge.disagreement',
        disagreement,
        tags={'neuron': neuron_id, 'escalated': escalated}
    )

# Dashboard alert: if escalation_rate > 40%, investigate
```

### Weekly Judge Variance Report

```python
# Generate weekly digest
import json

week_data = get_judge_calls_from_week()

report = {
    'week_starting': get_monday_of_this_week(),
    'total_calls': len(week_data),
    'escalation_rate': sum(1 for c in week_data if c['escalated']) / len(week_data),
    'disagreement_by_neuron': {},
}

for neuron_id in list_all_neurons():
    calls = [c for c in week_data if c['neuron_id'] == neuron_id]
    if calls:
        disagreements = [c['disagreement'] for c in calls]
        report['disagreement_by_neuron'][neuron_id] = {
            'mean': np.mean(disagreements),
            'std': np.std(disagreements),
            'max': np.max(disagreements),
        }

# Alert on outliers
for neuron, stats in report['disagreement_by_neuron'].items():
    if stats['mean'] > 0.25:  # High disagreement
        print(f"⚠️  {neuron}: mean disagreement {stats['mean']:.2f} — rubric may be ambiguous")

print(json.dumps(report, indent=2))
```

---

## Data-Gate Activation

### Checklist: WAVE 2 Activation (n ≥ 200)

**Trigger:** Corpus reaches 200 chats  
**Duration:** 2-4 hours  
**Owner:** ML team

```
Pre-Activation (1 day before):
- [ ] Notify team: WAVE 2 activation planned
- [ ] Schedule brief meeting (30 min)
- [ ] Prepare rollback plan

Activation Day:
- [ ] Run final corpus size check: SELECT COUNT(*) FROM chats WHERE gold = TRUE
      Expected: ≥ 200
      
- [ ] Check archetype distribution (no single type > 60%)
      
- [ ] Run κ^H falsification gate:
      ```python
      s_human = get_s_human_for_all_gold()
      result = estimate_kappa_h(s_human)
      assert result['falsification_pass'], "Gate failed!"
      ```
      
- [ ] Run LPA discovery and check agreement:
      ```python
      labels, summary = discover_archetypes_via_lpa(corpus)
      assert summary['agreement_with_decreed'] > 0.70, "Low agreement!"
      ```
      
- [ ] Deploy κ^H + LPA to production
      
- [ ] Update monitoring dashboard with κ^H z-scores
      
- [ ] Create PR documenting: corpus size, archetype dist, gate results
      
- [ ] Notify team: WAVE 2 live

Post-Activation (1 week):
- [ ] Monitor κ^H distribution daily
- [ ] Check LPA cluster stability
- [ ] Re-run gates weekly (should still pass)
- [ ] Gather user feedback
```

---

### Checklist: WAVE 3 Activation (DIF Clearance)

**Trigger:** DIF analysis completed & no major issues found  
**Duration:** 4-6 hours  
**Owner:** Privacy/Fairness team

```
Pre-Activation:
- [ ] DIF report completed (check for bias by archetype, stage, domain)
- [ ] All material DIF issues resolved or documented
- [ ] CRO team briefed on Commitment-12 enforcement
- [ ] Infrastructure changes deployed (no z-score surfacing)

Activation Day:
- [ ] Activate CRO overlay:
      ```python
      z_result = compute_cro_z_scores(kappa_h_estimates, covariates)
      report = cro_report_with_commitment_12(z_result, enable_z_surface=False)
      assert report['z_scores_visible'] is False, "Commitment-12 violated!"
      ```
      
- [ ] Verify z-scores are NEVER returned in API responses
      
- [ ] Deploy CRO to production
      
- [ ] Update monitoring: CRO metrics dashboard (private viewing only)
      
- [ ] Create PR documenting: DIF findings, CRO configuration, Commitment-12 enforcement
      
- [ ] Notify team: WAVE 3 live

Post-Activation:
- [ ] Monitor cell sizes (N ≥ 10 for each competency cell)
- [ ] Weekly check: no z-scores leaked to users
- [ ] Monthly DIF re-check (trending)
- [ ] User support: CRO is diagnostic only (not public)
```

---

## Emergency Contacts

| Role | Contact | On-Call |
|------|---------|---------|
| Judge Provider Support | support@judge.internal | Yes |
| Database Admin | dba@org.internal | Yes |
| ML Team Lead | ml-lead@org.internal | No |
| Privacy Officer | privacy@org.internal | No |
| Product Manager | pm@org.internal | No |

---

## Glossary

**Cascaded Replication:** Judge calls escalate when disagreement > threshold  
**IRT:** Item Response Theory (discrimination + difficulty)  
**κ^H:** Efficiency factor (tokens saved by human)  
**LPA:** Latent Profile Analysis (archetype discovery)  
**CRO:** Competency Reference Overlay (z-score normalization)  
**DIF:** Differential Item Functioning (bias analysis)  
**S_human:** Information bottleneck measure (tokens saved)  
**Commitment-12:** Never surface z-scores publicly (private only)

---

**Last Updated:** 2026-06-26  
**Owner:** Engineering Team  
**Review Frequency:** Monthly
