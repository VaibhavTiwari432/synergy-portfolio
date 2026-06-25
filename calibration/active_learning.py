"""
calibration/active_learning.py — Active learning corpus sampling pipeline

ITEM #4 PART B: Principled corpus growth via uncertainty × diversity sampling.

Purpose: Instead of random sampling, select new gold chats by:
  1. Identifying uncertain instances (high judge disagreement)
  2. Clustering by embedding distance (diversity)
  3. Selecting high-uncertainty examples from under-represented archetypes

This operationalizes "archetype spread" and makes corpus growth efficient and predictable.

Non-negotiables:
  - Selection is recommendation only; human annotation required
  - Frozen anchor set remains unchanged (for drift detection)
  - Sampling respects archetype balance targets
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


def compute_uncertainty_score(judge_replications: List[float]) -> float:
    """
    Compute uncertainty from judge disagreement.

    Args:
        judge_replications: List of scores from multiple judge runs (0-1 or 0-4)

    Returns:
        Uncertainty score (0.0 = perfect agreement, 1.0 = maximum disagreement)
    """
    if len(judge_replications) < 2:
        return 0.0

    # Normalize to 0-1 if needed
    reps = np.array(judge_replications, dtype=np.float64)
    if reps.max() > 1.0:
        reps = reps / 4.0  # Convert 0-4 to 0-1

    # Uncertainty: variance across replications (normalized to 0-1)
    variance = np.var(reps)
    # Max variance for binary is 0.25, for 0-1 continuous is ~0.083
    # Normalize to 0-1 range
    uncertainty = min(1.0, variance / 0.25)

    return uncertainty


def select_next_batch(
    gold_set: List[Dict],
    unlabeled_pool: List[Dict],
    judge_replications_pool: Dict[str, List[List[float]]],  # chat_id -> [neuron_reps, ...]
    batch_size: int = 5,
    archetype_targets: Optional[List[str]] = None,
    diversity_k: int = 10,
) -> Tuple[List[str], Dict]:
    """
    Select next batch of chats for annotation using uncertainty × diversity.

    Args:
        gold_set: List of already-annotated gold chats
        unlabeled_pool: List of candidate chats not yet in gold set
        judge_replications_pool: Dict[chat_id] -> List of replicated judge scores
            across neurons (to compute uncertainty)
        batch_size: Number of chats to select (default 5)
        archetype_targets: List of target archetypes for balanced sampling.
            If None, infers from gold_set.
        diversity_k: Number of clusters for diversity (one per archetype)

    Returns:
        (selected_chat_ids, metadata_dict)
        where metadata includes uncertainty scores, archetype assignments, etc.
    """

    # Infer archetype targets from gold set if not provided
    if archetype_targets is None:
        archetype_targets = list(set(c.get('archetype') for c in gold_set))
        archetype_targets = [a for a in archetype_targets if a]  # Remove None

    if not archetype_targets:
        # Fallback: assume 10 archetypes
        archetype_targets = [f'ARCHETYPE_{i}' for i in range(10)]

    # Step 1: Compute uncertainty for unlabeled pool
    print(f"Computing uncertainty for {len(unlabeled_pool)} unlabeled chats...")
    uncertainties = {}

    for chat in unlabeled_pool:
        chat_id = chat['id']
        reps = judge_replications_pool.get(chat_id, [])

        if not reps or len(reps) == 0:
            # No replications available; use zero uncertainty (skip)
            uncertainties[chat_id] = 0.0
        else:
            # Aggregate uncertainty across neurons
            neuron_uncertainties = [
                compute_uncertainty_score(neuron_reps)
                for neuron_reps in reps
            ]
            uncertainties[chat_id] = np.mean(neuron_uncertainties)

    # Step 2: Cluster by archetype (simple proxy for diversity)
    # In a full implementation, this would use embedding-based clustering
    print(f"Clustering by archetype...")
    archetype_groups = defaultdict(list)

    for chat in unlabeled_pool:
        chat_id = chat['id']
        archetype = chat.get('archetype', 'UNKNOWN')

        # If archetype is unknown, skip (can't place in diversity constraint)
        if archetype == 'UNKNOWN' or archetype not in archetype_targets:
            archetype = np.random.choice(archetype_targets)  # Fallback

        archetype_groups[archetype].append(chat_id)

    # Step 3: Count current distribution in gold set
    gold_archetype_counts = defaultdict(int)
    for chat in gold_set:
        archetype = chat.get('archetype')
        if archetype in archetype_targets:
            gold_archetype_counts[archetype] += 1

    target_per_archetype = batch_size // len(archetype_targets)
    remainder = batch_size % len(archetype_targets)

    # Step 4: Select high-uncertainty chats, distributed across archetypes
    print(f"Selecting {batch_size} chats (target: ~{target_per_archetype} per archetype)...")
    selected = []
    selection_metadata = []

    for i, archetype in enumerate(archetype_targets):
        # Target for this archetype in this batch
        n_to_select_target = target_per_archetype + (1 if i < remainder else 0)

        # Get candidates for this archetype
        candidates = archetype_groups.get(archetype, [])
        if not candidates:
            continue

        # Sort candidates by uncertainty (highest first)
        candidates_with_unc = [
            (chat_id, uncertainties.get(chat_id, 0.0))
            for chat_id in candidates
        ]
        candidates_with_unc.sort(key=lambda x: x[1], reverse=True)

        # Select top N (up to target)
        n_to_select = min(n_to_select_target, len(candidates_with_unc))
        for chat_id, unc in candidates_with_unc[:n_to_select]:
            selected.append(chat_id)
            selection_metadata.append({
                'chat_id': chat_id,
                'archetype': archetype,
                'uncertainty': unc,
                'reason': 'high-uncertainty under-represented archetype',
            })

    # Trim to batch size
    selected = selected[:batch_size]
    selection_metadata = selection_metadata[:batch_size]

    print(f"Selected {len(selected)} chats for annotation")
    for meta in selection_metadata:
        print(f"  - {meta['chat_id']} (archetype={meta['archetype']}, unc={meta['uncertainty']:.3f})")

    return selected, {
        'selected_count': len(selected),
        'batch_size': batch_size,
        'metadata': selection_metadata,
        'uncertainties': {chat['chat_id']: chat['uncertainty'] for chat in selection_metadata},
    }


def compute_corpus_growth_schedule(
    current_gold_size: int = 26,
    target_size: int = 200,
    batch_size: int = 5,
    months_to_complete: float = 6.0,
) -> Dict:
    """
    Compute expected corpus growth schedule.

    Args:
        current_gold_size: Starting gold set size (default 26)
        target_size: Target corpus size (default 200)
        batch_size: Chats annotated per batch (default 5)
        months_to_complete: Desired timeline (default 6 months)

    Returns:
        dict with expected growth schedule
    """

    growth_needed = target_size - current_gold_size
    n_batches = np.ceil(growth_needed / batch_size)
    batches_per_month = n_batches / months_to_complete

    # Default: 1-2 batches per month (5-10 chats)
    if batches_per_month < 0.5:
        batches_per_month = 0.5  # Minimum: every 2 months
    if batches_per_month > 4:
        batches_per_month = 4  # Maximum: every week

    return {
        'current_gold_size': current_gold_size,
        'target_size': target_size,
        'growth_needed': growth_needed,
        'batch_size': batch_size,
        'n_batches': int(n_batches),
        'batches_per_month': batches_per_month,
        'months_to_complete': months_to_complete,
        'schedule': 'Annotate {} chats/month for {} months to reach {} total'.format(
            int(batches_per_month * batch_size),
            int(months_to_complete),
            target_size,
        ),
    }


if __name__ == '__main__':
    print("Active learning module loaded.")
    print("Usage:")
    print("  from calibration.active_learning import select_next_batch")
    print("  selected, metadata = select_next_batch(gold_set, unlabeled_pool, judge_reps)")
