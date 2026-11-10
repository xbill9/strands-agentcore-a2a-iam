"""Who can reach the worker: each case is one identity and one request shape.

    WORKER_RUNTIME_ARN=... python3 -m bench.boundary

Writes results/<stamp>/boundary.json with the status and verbatim body of
every call, and prints one line per case.
"""

from __future__ import annotations

import os

from bench.common import (
    assume, call, card_url, message_body, signer, worker, write_result,
)
from caller.sigv4 import runtime_url

QUESTION = "Convert 100 USD to EUR"


def main() -> int:
    arn, region = worker()
    url = runtime_url(arn, region)
    card = card_url(arn, region)
    other_arn = arn.rsplit("/", 1)[0] + "/speedrunMissing-0000000000"

    invoke = assume("speedrun-caller-invoke", region)
    runtime_only = assume("speedrun-caller-runtime-only", region)
    none = assume("speedrun-caller-none", region)

    cases = [
        ("invoke role, card", "GET", card, signer(invoke, region), None),
        ("invoke role, message", "POST", url, signer(invoke, region), message_body(QUESTION)),
        ("runtime-only role, card", "GET", card, signer(runtime_only, region), None),
        ("runtime-only role, message", "POST", url, signer(runtime_only, region), message_body(QUESTION)),
        ("no-permission role, card", "GET", card, signer(none, region), None),
        ("no-permission role, message", "POST", url, signer(none, region), message_body(QUESTION)),
        ("unsigned, card", "GET", card, None, None),
        ("unsigned, message", "POST", url, None, message_body(QUESTION)),
        ("invoke role, signed for service 'bedrock'", "POST", url,
         signer(invoke, region, service="bedrock"), message_body(QUESTION)),
        ("invoke role, runtime outside the policy", "POST", runtime_url(other_arn, region),
         signer(invoke, region), message_body(QUESTION)),
    ]

    results = []
    for name, method, target, auth, body in cases:
        r = call(method, target, auth, body=body)
        r["case"] = name
        results.append(r)
        print(f"{r['status']}  {r['seconds']:7.2f} s  {name}: {r['body'][:160]!r}")

    path = write_result("boundary", {
        "runtime_arn": arn,
        "region": region,
        "question": QUESTION,
        "cases": results,
        "versions": versions(),
    })
    print(f"wrote {path}")
    return 0


def versions() -> dict:
    import importlib.metadata as md
    return {p: md.version(p) for p in ("strands-agents", "a2a-sdk", "botocore", "httpx")}


if __name__ == "__main__":
    raise SystemExit(main())
