"""
Reusable fixture chat data for tests.
Keep fixtures minimal — just enough to exercise the parsers and chunker.
"""

from __future__ import annotations

# ── Plain-text fixture ───────────────────────────────────────────────────────
PLAINTEXT_20_TURN = "\n".join(
    [
        f"{'Human' if i % 2 == 0 else 'Assistant'}: Turn {i} content here."
        for i in range(20)
    ]
)

PLAINTEXT_SINGLE_TURN = "Human: Just one question."

PLAINTEXT_EMPTY = ""

# ── ChatGPT flat-list fixture (simple format) ────────────────────────────────
CHATGPT_FLAT_6_TURNS: list[dict] = [
    {"role": "user", "content": "Hello, explain neural networks."},
    {"role": "assistant", "content": "Neural networks are..."},
    {"role": "user", "content": "Can you give an example?"},
    {"role": "assistant", "content": "Sure, here's a simple perceptron..."},
    {"role": "user", "content": "How does backpropagation work?"},
    {"role": "assistant", "content": "Backpropagation computes gradients..."},
]

# ── Claude flat-list fixture ─────────────────────────────────────────────────
CLAUDE_FLAT_4_TURNS: list[dict] = [
    {"sender": "human", "text": "What is machine learning?"},
    {"sender": "assistant", "text": "Machine learning is a subset of AI..."},
    {"sender": "human", "text": "How does it differ from deep learning?"},
    {"sender": "assistant", "text": "Deep learning uses multi-layer neural networks..."},
]

# ── ChatGPT mapping-format fixture ──────────────────────────────────────────
CHATGPT_MAPPING_4_TURNS: dict = {
    "id": "conv-abc",
    "title": "Test Conversation",
    "mapping": {
        "root": {
            "message": None,
            "parent": None,
            "children": ["node1"],
        },
        "node1": {
            "message": {
                "id": "node1",
                "author": {"role": "user"},
                "content": {"content_type": "text", "parts": ["What is AI?"]},
                "create_time": 1700000000.0,
            },
            "parent": "root",
            "children": ["node2"],
        },
        "node2": {
            "message": {
                "id": "node2",
                "author": {"role": "assistant"},
                "content": {"content_type": "text", "parts": ["AI is artificial intelligence..."]},
                "create_time": 1700000010.0,
            },
            "parent": "node1",
            "children": ["node3"],
        },
        "node3": {
            "message": {
                "id": "node3",
                "author": {"role": "user"},
                "content": {"content_type": "text", "parts": ["Can it think?"]},
                "create_time": 1700000020.0,
            },
            "parent": "node2",
            "children": ["node4"],
        },
        "node4": {
            "message": {
                "id": "node4",
                "author": {"role": "assistant"},
                "content": {"content_type": "text", "parts": ["Not in the human sense..."]},
                "create_time": 1700000030.0,
            },
            "parent": "node3",
            "children": [],
        },
    },
}
