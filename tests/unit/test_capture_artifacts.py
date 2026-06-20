from src.db.queries import canonicalize_turn_indexes, derive_turn_event_log


def test_canonicalize_turn_indexes_uses_payload_order() -> None:
    turns = [
        {"role": "user", "text": "first", "turn_index": 0},
        {"role": "assistant", "text": "second", "turn_index": 0},
        {"role": "user", "text": "third", "turn_index": 99},
    ]

    result = canonicalize_turn_indexes(turns)

    assert [turn["turn_index"] for turn in result] == [0, 1, 2]
    assert [turn["text"] for turn in result] == ["first", "second", "third"]
    assert [turn["turn_index"] for turn in turns] == [0, 0, 99]


def test_derive_turn_event_log_never_reuses_client_duplicate_indexes() -> None:
    turns = [
        {"role": "user", "text": "Please debug this?", "turn_index": 0, "timestamp_ms": 1000},
        {"role": "assistant", "text": "I can help.", "turn_index": 0, "timestamp_ms": 1500},
    ]

    rows = derive_turn_event_log(turns)

    assert [row["turn_index"] for row in rows] == [0, 1]
    assert [row["role"] for row in rows] == ["user", "assistant"]
    assert [row["timestamp_offset_ms"] for row in rows] == [0, 500]
