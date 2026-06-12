"""
src/sustainability/lambda_proxy.py — λ stub. OWNER: Chief Engineer.
(Brief §3.9: value null, rung DESIGNED, requires multi-session + probe.)

λ (retention decay) is estimable only as a difference-in-slopes against
no-AI probes (spec §10 A3). Scope A has no probes; this module exists so the
response schema carries an honest stub rather than an invented number.
"""

from __future__ import annotations

from contracts.schemas import LambdaStub


def lambda_estimate() -> LambdaStub:
    return LambdaStub()  # value=None, rung=DESIGNED, note frozen in the schema
