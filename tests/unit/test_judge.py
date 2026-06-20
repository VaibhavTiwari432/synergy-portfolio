"""Unit tests for the dimension-grain judge (prompt, parser, client).
OWNER: Chief Engineer. No network: transports are injected fakes."""

from __future__ import annotations

import json

import pytest

from contracts.schemas import CanonicalSession, Dimension, PartnerModel, Turn
from src.trait.judge.client import JUDGE_FAMILY, JudgeClient
from src.trait.judge.parser import (
    JudgeParseError,
    parse_judge_response,
    unavailable_output,
)
from src.trait.judge.prompt import (
    JUDGE_PROMPT_VERSION,
    MAX_TURN_CHARS,
    SYSTEM_PROMPT,
    build_user_prompt,
    render_transcript,
)


def _session(family: str = "openai", n: int = 4) -> CanonicalSession:
    turns = [
        Turn(index=i, role="human" if i % 2 == 0 else "ai", text=f"text {i}")
        for i in range(n)
    ]
    return CanonicalSession(
        session_id="j-1", source="plaintext",
        partner_model=PartnerModel(family=family), turns=turns,
    )


def _good_json(es_null: bool = True) -> str:
    entry = {"score": 0.6, "confidence": 0.8, "evidence_turns": [0, 2], "tom_tag": None}
    data = {d.value: dict(entry) for d in Dimension}
    if es_null:
        data["ES"]["score"] = None
    return json.dumps(data)


# ── prompt ───────────────────────────────────────────────────────────────────


def test_prompt_is_dimension_grain_not_neuron_grain():
    assert "107" not in SYSTEM_PROMPT  # the neuron count belongs to v1.3, not v2.x
    for dim in Dimension:
        assert f'"{dim.value}"' in SYSTEM_PROMPT
    assert JUDGE_PROMPT_VERSION == "v2.1"
    # v2.1 regression pin: ES anchors present, behavior-not-topic rule stated
    assert "ES DIMENSION — CALIBRATION ANCHORS" in SYSTEM_PROMPT
    assert "NOT ethical sensitivity" in SYSTEM_PROMPT


def test_render_transcript_truncates_long_turns():
    long_text = "x" * (MAX_TURN_CHARS + 500)
    s = CanonicalSession(
        session_id="j-2", source="plaintext",
        partner_model=PartnerModel(family="openai"),
        turns=[Turn(index=0, role="human", text=long_text)],
    )
    rendered = render_transcript(s)
    assert "[truncated 500 chars]" in rendered
    assert len(rendered) < len(long_text) + 200


def test_user_prompt_contains_turn_markers():
    p = build_user_prompt(_session())
    assert "[T0 HUMAN]" in p and "[T1 AI]" in p


# ── parser ───────────────────────────────────────────────────────────────────


def test_parser_accepts_clean_json():
    out = parse_judge_response(
        _good_json(), judge_model="m", judge_family="google",
        partner_family="openai", prompt_version="v2.0",
    )
    assert out.scores[Dimension.AL].score == 0.6
    assert out.scores[Dimension.ES].score is None  # event-triggered N/A
    assert out.judge_unavailable is False
    assert out.judge_family_conflict is False


def test_parser_strips_code_fences_and_prose():
    wrapped = "Here are the scores:\n```json\n" + _good_json() + "\n```\nDone."
    out = parse_judge_response(
        wrapped, judge_model="m", judge_family="google",
        partner_family="openai", prompt_version="v2.0",
    )
    assert out.scores[Dimension.CA].score == 0.6


def test_parser_flags_same_family_judgment():
    out = parse_judge_response(
        _good_json(), judge_model="m", judge_family="google",
        partner_family="google", prompt_version="v2.0",
    )
    assert out.judge_family_conflict is True  # ADR-0002 / D-001


@pytest.mark.parametrize("mutation", [
    lambda d: d.pop("CA"),                                  # missing dimension
    lambda d: d["AL"].update(score=None),                   # null outside ES
    lambda d: d["PR"].update(score=1.7),                    # out of range
    lambda d: d["EC"].update(score="high"),                 # non-numeric
])
def test_parser_rejects_substantive_defects(mutation):
    data = json.loads(_good_json())
    mutation(data)
    with pytest.raises(JudgeParseError):
        parse_judge_response(
            json.dumps(data), judge_model="m", judge_family="google",
            partner_family="openai", prompt_version="v2.0",
        )


def test_unavailable_output_is_na_never_zero():
    out = unavailable_output(
        judge_model="m", judge_family="google",
        partner_family="openai", prompt_version="v2.0",
    )
    assert out.judge_unavailable is True
    assert all(s.score is None for s in out.scores.values())


# ── client ───────────────────────────────────────────────────────────────────


def test_client_happy_path_first_attempt():
    calls: list[str] = []

    def fake(system: str, user: str) -> str:
        calls.append(user)
        return _good_json()

    out = JudgeClient(generate=fake, sleep=lambda _: None).score_session(_session())
    assert out.judge_unavailable is False
    assert len(calls) == 1


def test_client_retries_then_uses_fallback():
    def flaky(system: str, user: str) -> str:
        raise RuntimeError("transport down")

    fallback_calls: list[str] = []

    def fallback(system: str, user: str) -> str:
        fallback_calls.append(user)
        return _good_json()

    out = JudgeClient(generate=flaky, fallback=fallback, sleep=lambda _: None).score_session(_session())
    assert out.judge_unavailable is False
    assert len(fallback_calls) == 1  # last attempt goes to the fallback


def test_client_all_fail_returns_unavailable():
    attempts: list[int] = []

    def dead(system: str, user: str) -> str:
        attempts.append(1)
        raise RuntimeError("down")

    out = JudgeClient(generate=dead, fallback=dead, sleep=lambda _: None).score_session(_session())
    assert out.judge_unavailable is True
    assert len(attempts) == 3  # exactly max_attempts transport calls
    assert all(s.score is None for s in out.scores.values())


def test_client_retries_on_parse_error_too():
    responses = iter(["not json at all", _good_json()])

    def improving(system: str, user: str) -> str:
        return next(responses)

    out = JudgeClient(generate=improving, sleep=lambda _: None).score_session(_session())
    assert out.judge_unavailable is False


def test_client_flags_gemini_partner_sessions():
    out = JudgeClient(generate=lambda s, u: _good_json(), sleep=lambda _: None).score_session(
        _session(family=JUDGE_FAMILY)
    )
    assert out.judge_family_conflict is True


# ── openai-family judge (re-judge path, non-negotiable #20) ──────────────────

from src.trait.judge.client import (  # noqa: E402 — appended with its tests
    DEFAULT_OPENAI_JUDGE_MODEL,
    JUDGE_MODEL,
    REJUDGE_MODEL_ENV,
    openai_family_judge,
)


def test_openai_judge_model_from_env_and_family_openai(monkeypatch):
    monkeypatch.setenv(REJUDGE_MODEL_ENV, "openai/gpt-4.1-mini")
    client = openai_family_judge(generate=lambda s, u: _good_json(), sleep=lambda _: None)
    out = client.score_session(_session(family="google"))
    assert out.judge_family == "openai"
    assert out.judge_model == "openai/gpt-4.1-mini"


def test_openai_judge_default_model_when_env_unset(monkeypatch):
    monkeypatch.delenv(REJUDGE_MODEL_ENV, raising=False)
    client = openai_family_judge(generate=lambda s, u: _good_json(), sleep=lambda _: None)
    out = client.score_session(_session(family="google"))
    assert out.judge_family == "openai"
    assert out.judge_model == DEFAULT_OPENAI_JUDGE_MODEL == "openai/gpt-4o-mini"


def test_openai_judge_has_no_fallback_transport(monkeypatch):
    monkeypatch.delenv(REJUDGE_MODEL_ENV, raising=False)
    client = openai_family_judge(generate=lambda s, u: _good_json(), sleep=lambda _: None)
    assert client._fallback is None  # never a silent Gemini fallback


def test_openai_judge_google_partner_no_conflict(monkeypatch):
    monkeypatch.delenv(REJUDGE_MODEL_ENV, raising=False)
    client = openai_family_judge(generate=lambda s, u: _good_json(), sleep=lambda _: None)
    out = client.score_session(_session(family="google"))
    assert out.judge_family_conflict is False  # the whole point of the re-judge
    assert out.judge_unavailable is False


def test_openai_judge_openai_partner_flags_conflict(monkeypatch):
    monkeypatch.delenv(REJUDGE_MODEL_ENV, raising=False)
    client = openai_family_judge(generate=lambda s, u: _good_json(), sleep=lambda _: None)
    out = client.score_session(_session(family="openai"))
    assert out.judge_family_conflict is True  # ADR-0002 / D-001


@pytest.mark.parametrize("bad_model", [
    "anthropic/claude-sonnet-4",
    "claude-3-5-haiku",
    "Anthropic/Claude-Opus",
    "some-vendor/ANTHROPIC-special",
])
def test_openai_judge_rejects_anthropic_models(bad_model, monkeypatch):
    monkeypatch.delenv(REJUDGE_MODEL_ENV, raising=False)
    with pytest.raises(ValueError):
        openai_family_judge(bad_model, generate=lambda s, u: _good_json())


def test_openai_judge_rejects_anthropic_models_from_env(monkeypatch):
    monkeypatch.setenv(REJUDGE_MODEL_ENV, "anthropic/claude-sonnet-4")
    with pytest.raises(ValueError):
        openai_family_judge(generate=lambda s, u: _good_json())


@pytest.mark.parametrize("non_openai_model", [
    "google/gemini-2.5-flash",   # the D-003 case: google id with openai provenance
    "mistralai/mistral-large",
    "gpt-4o-mini",               # right family, wrong form — no provider prefix
])
def test_openai_judge_requires_openai_prefix(non_openai_model, monkeypatch):
    monkeypatch.delenv(REJUDGE_MODEL_ENV, raising=False)
    with pytest.raises(ValueError):
        openai_family_judge(non_openai_model, generate=lambda s, u: _good_json())


def test_default_client_regression_pin_gemini_google():
    out = JudgeClient(generate=lambda s, u: _good_json(), sleep=lambda _: None).score_session(
        _session(family="openai")
    )
    assert out.judge_model == JUDGE_MODEL == "gemini-2.5-flash"
    assert out.judge_family == "google"
    assert out.judge_family_conflict is False
