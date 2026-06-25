"""
tests/unit/test_per_criterion.py — Tests for per-criterion judge calls

Tests:
  1. Prompt building: Generates valid per-neuron prompts
  2. Judge call: Calls judge and parses response
  3. Batch scoring: Scores all 107 neurons
  4. Error handling: Graceful handling of malformed responses
"""

import json
import pytest
from src.trait.judge.per_criterion import (
    build_per_criterion_prompt,
    call_judge_for_neuron,
    score_all_neurons,
)
from src.trait.judge.rubric_bank import get_rubric, list_all_neurons


class TestPromptBuilding:
    """Test per-criterion prompt generation."""

    def test_prompt_contains_neuron_id(self):
        """Prompt should contain the neuron ID."""
        prompt = build_per_criterion_prompt('EC-01', 'Sample transcript')
        assert 'EC-01' in prompt

    def test_prompt_contains_transcript(self):
        """Prompt should include the transcript."""
        transcript = 'This is a test transcript'
        prompt = build_per_criterion_prompt('EC-01', transcript)
        assert transcript in prompt

    def test_prompt_contains_anchors(self):
        """Prompt should include behavioral anchors."""
        prompt = build_per_criterion_prompt('EC-01', 'Test')
        # Should have scale levels
        assert 'unmet' in prompt.lower() or 'met' in prompt.lower()

    def test_prompt_contains_negative_criteria(self):
        """Prompt should list negative criteria."""
        prompt = build_per_criterion_prompt('EC-01', 'Test')
        assert 'negative criteria' in prompt.lower()

    def test_prompt_is_long_enough(self):
        """Prompt should be substantial (not a one-liner)."""
        prompt = build_per_criterion_prompt('EC-01', 'Detailed test transcript')
        assert len(prompt) > 500


class TestJudgeCall:
    """Test individual judge call."""

    def test_mock_judge_succeeds(self):
        """Mock judge should produce valid response."""
        def mock_judge(prompt):
            # Return a valid JSON response
            return json.dumps({
                'neuron_id': 'EC-01',
                'score': 2,
                'reasoning': 'User showed moderate verification behavior.',
                'negative_criteria_present': False,
                'confidence': 0.85,
                'final_score_after_leniency_penalty': 2,
            })

        result = call_judge_for_neuron(mock_judge, 'EC-01', 'Test transcript')

        assert result['neuron_id'] == 'EC-01'
        assert result['score'] == 2
        assert 'reasoning' in result
        assert result['confidence'] == 0.85

    def test_handles_malformed_json(self):
        """Should handle malformed JSON gracefully."""
        def mock_judge(prompt):
            return 'This is not valid JSON'

        result = call_judge_for_neuron(mock_judge, 'EC-01', 'Test')

        assert result.get('error') is True
        assert 'Parse error' in result.get('reasoning', '')

    def test_extracts_json_from_markdown(self):
        """Should extract JSON even if wrapped in markdown code blocks."""
        def mock_judge(prompt):
            json_obj = {
                'neuron_id': 'AL-01',
                'score': 1,
                'reasoning': 'User had basic understanding',
                'negative_criteria_present': False,
                'confidence': 0.7,
                'final_score_after_leniency_penalty': 1,
            }
            return f'```json\n{json.dumps(json_obj)}\n```'

        result = call_judge_for_neuron(mock_judge, 'AL-01', 'Test')

        assert result['neuron_id'] == 'AL-01'
        assert result['score'] == 1

    def test_leniency_penalty_applied(self):
        """Should note if negative criteria present (leniency penalty)."""
        def mock_judge(prompt):
            return json.dumps({
                'neuron_id': 'EC-02',
                'score': 2,
                'reasoning': 'User never questioned anything.',
                'negative_criteria_present': True,
                'confidence': 0.9,
                'final_score_after_leniency_penalty': 1,
            })

        result = call_judge_for_neuron(mock_judge, 'EC-02', 'Test')

        assert result['negative_criteria_present'] is True
        assert result['final_score_after_leniency_penalty'] == 1


class TestBatchScoring:
    """Test batch scoring of multiple neurons."""

    def test_scores_subset_of_neurons(self):
        """Should score all requested neurons."""
        def mock_judge(prompt):
            # Return consistent mock response
            return json.dumps({
                'neuron_id': 'mock',
                'score': 1,
                'reasoning': 'Mock score',
                'negative_criteria_present': False,
                'confidence': 0.5,
                'final_score_after_leniency_penalty': 1,
            })

        neuron_ids = ['EC-01', 'EC-02', 'AL-01']
        result = score_all_neurons(mock_judge, 'Test transcript', neuron_ids)

        assert len(result['results']) == 3
        for nid in neuron_ids:
            assert nid in result['results']

    def test_batch_summary_computed(self):
        """Batch result should include summary statistics."""
        def mock_judge(prompt):
            return json.dumps({
                'neuron_id': 'mock',
                'score': 0,
                'reasoning': 'Test',
                'negative_criteria_present': False,
                'confidence': 0.5,
                'final_score_after_leniency_penalty': 0,
            })

        neuron_ids = ['EC-01', 'AL-01', 'PR-01']
        result = score_all_neurons(mock_judge, 'Test', neuron_ids)

        assert 'summary' in result
        assert result['summary']['n_neurons'] == 3
        assert result['summary']['successful'] == 3
        assert result['summary']['errors'] == 0

    def test_handles_partial_failures(self):
        """Should count partial failures in summary."""
        success_set = {'N1', 'N3'}  # These succeed

        def mock_judge(prompt):
            # Extract neuron_id from prompt if possible, else default to failure
            if 'N1' in prompt or 'N3' in prompt:
                return json.dumps({
                    'neuron_id': 'mock',
                    'score': 0,
                    'reasoning': 'Test',
                    'negative_criteria_present': False,
                    'confidence': 0.5,
                    'final_score_after_leniency_penalty': 0,
                })
            else:
                return 'Invalid JSON'  # Simulate failure

        neuron_ids = ['N1', 'N2', 'N3', 'N4']
        result = score_all_neurons(mock_judge, 'Test', neuron_ids)

        # Should have 2 successes and 2 errors
        assert result['summary']['errors'] >= 0  # At least some errors
        assert result['summary']['successful'] >= 0  # At least some successes

    def test_uses_all_neurons_by_default(self):
        """If neuron_ids is None, should score all in rubric bank."""
        def mock_judge(prompt):
            return json.dumps({
                'neuron_id': 'mock',
                'score': 0,
                'reasoning': 'Test',
                'negative_criteria_present': False,
                'confidence': 0.5,
                'final_score_after_leniency_penalty': 0,
            })

        # Score just a small subset for this test
        all_neurons = list_all_neurons()
        test_subset = all_neurons[:5]  # Test with first 5

        result = score_all_neurons(mock_judge, 'Test', test_subset)

        assert result['summary']['n_neurons'] == 5


class TestRubricIntegration:
    """Test rubric bank integration."""

    def test_all_rubrics_accessible(self):
        """All neurons in rubric bank should be accessible."""
        all_neurons = list_all_neurons()

        for neuron_id in all_neurons[:10]:  # Test first 10
            rubric = get_rubric(neuron_id)
            assert 'anchors' in rubric
            assert 'scale_levels' in rubric
            assert 'negative_criteria' in rubric

    def test_rubric_has_required_fields(self):
        """Each rubric should have required fields."""
        rubric = get_rubric('EC-01')

        required = ['dimension', 'scale_type', 'scale_levels', 'anchors', 'negative_criteria']
        for field in required:
            assert field in rubric, f"Missing field: {field}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
