"""Gate D smoke: live POST /v1/sessions → GET /v1/sessions/{id}/score on a
fresh non-gold chat, real Gemini judge. Passes if the pipeline runs without
error and the response contract is satisfied (not a performance test)."""

from __future__ import annotations

import json
import os
import sys

from fastapi.testclient import TestClient

from contracts.schemas import Dimension
from src.api.main import create_app
from src.api.store import SessionStore
from src.claims.report import forbidden_word_scan

os.environ.setdefault("SAF_API_KEY", "gate-d-smoke-key")
HEADERS = {"X-API-Key": os.environ["SAF_API_KEY"]}

# fresh, non-gold, plausible human+Claude exchange (14 turns)
TRANSCRIPT = """\
User: I'm building a small Flask API for my college fest's food-stall ordering. Here is my plan: one /orders POST endpoint, SQLite, no auth for now. Poke holes in my reasoning before I start.
Claude: A few risks: no auth means anyone can spam orders; SQLite under concurrent writes can lock; and you have no idempotency, so double-taps create duplicate orders. I'd add a per-stall token, WAL mode, and a client-generated order UUID.
User: Good catches. Use this format for the plan: numbered steps, max 6, each with a one-line risk note.
Claude: 1. Define order schema (risk: changing it later breaks clients). 2. Enable SQLite WAL (risk: slightly stale reads). 3. Client UUID idempotency key (risk: clients that don't send one). 4. Per-stall bearer token (risk: token leakage via QR). 5. POST /orders with validation (risk: oversized payloads). 6. Basic rate limit (risk: shared campus NAT tripping it).
User: Are you sure WAL mode actually helps here? The docs say WAL helps concurrent readers, but my writes are the bottleneck.
Claude: You're right to push back — WAL improves read concurrency; writes still serialize. For your load (a few orders per second at peak) serialized writes are fine; the real fix for write contention would be Postgres, which is overkill here.
User: ok
Claude: Want me to draft the schema next?
User: Yes, draft the orders table schema, must include stall_id, status, and a created_at with timezone. Don't include user accounts.
Claude: CREATE TABLE orders (id TEXT PRIMARY KEY, stall_id TEXT NOT NULL, items TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', idempotency_key TEXT UNIQUE, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
User: You didn't mention how status transitions are enforced. What about that? And what's missing for refunds?
Claude: Good omission catch. Status should be constrained (pending→accepted→ready→collected, or →cancelled) — enforce in the API layer with an allowed-transitions map. For refunds you'd need a payments table with an amount and a reversal row; right now nothing records payment at all.
User: Park refunds for now. Before you answer anything else: I think the rate limit should be per stall token, not per IP — am I wrong about the campus NAT issue?
Claude: You're not wrong — per-IP limits on a campus NAT would throttle everyone behind one address. Per-token is correct here, with a modest global cap as a backstop.
User: Great. Write the allowed-transitions map as a Python dict, exactly 5 keys, and add one pytest for an illegal transition.
Claude: TRANSITIONS = {"pending": ["accepted", "cancelled"], "accepted": ["ready", "cancelled"], "ready": ["collected"], "collected": [], "cancelled": []} — and a pytest asserting that moving "collected" → "pending" raises InvalidTransition.
"""


def main() -> int:
    client = TestClient(create_app(store=SessionStore(":memory:")))
    failures: list[str] = []

    def check(name: str, ok: bool) -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            failures.append(name)

    resp = client.post("/v1/sessions", json={"payload": TRANSCRIPT}, headers=HEADERS)
    print(f"POST /v1/sessions -> {resp.status_code}")
    check("POST returns 200", resp.status_code == 200)
    session_id = resp.json()["session_id"]
    check("detected_tier is 1", resp.json()["detected_tier"] == 1)

    score = client.get(f"/v1/sessions/{session_id}/score", headers=HEADERS)
    print(f"GET /v1/sessions/{session_id}/score -> {score.status_code}")
    check("GET returns 200", score.status_code == 200)
    body = score.json()

    # all 8 dims present, each value-or-status, rung on every scored field
    dims = body["profile"]
    check("all 8 dimensions present", set(dims.keys()) == {d.value for d in Dimension})
    check("every dim has value or N/A/INSUFFICIENT status",
          all((d["value"] is not None) or d["status"] in ("N/A", "INSUFFICIENT_SAMPLE")
              for d in dims.values()))
    check("rung present on every profile field", all(d.get("rung") for d in dims.values()))

    composite = body["composite"]
    check("composite present (value or null+gates)",
          composite["value"] is not None or composite["gates_passed"].get("scorability") is False)
    check("composite carries rung + CI-or-null",
          bool(composite.get("rung")) and ("ci" in composite))

    check("state_strip populated", len(body["state_strip"]) > 0)
    check("flags present", "theater_counter" in body["flags"])
    check("regime_overlay present", "occupancy" in body["regime_overlay"])
    check("sustainability present (s_human, ewma, lambda)",
          all(k in body["sustainability"] for k in ("s_human_hat", "debt_ewma", "lambda")))

    report = body["report"]
    check("report has >=1 observed", len(report["observed"]) >= 1)
    check("tier_caveat set", bool(report["tier_caveat"]))

    user_facing = [*report["observed"], *report["inferred"], *report["hypothesized"],
                   report["tier_caveat"]]
    violations = forbidden_word_scan(user_facing, tier=1)
    check("no forbidden word in user-facing fields", violations == [])

    rung_fields = [composite, body["state_validity"], body["flags"],
                   body["regime_overlay"], body["sustainability"]["s_human_hat"],
                   body["sustainability"]["debt_ewma"], body["sustainability"]["lambda"],
                   report]
    check("rung on every scored component", all(f.get("rung") for f in rung_fields))
    check("nothing above MEASURABLE at tier 1",
          all(f.get("rung") != "VALIDATED" for f in rung_fields))
    check("judge actually scored (not unavailable)", body["flags"]["judge_unavailable"] is False)

    print(f"\nGATE D: {'PASS' if not failures else 'FAIL — ' + ', '.join(failures)}")
    print(json.dumps({d: dims[d]["value"] for d in sorted(dims)}, indent=None))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
