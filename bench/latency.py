"""Latency of the A2A call through AgentCore, by session state.

    WORKER_RUNTIME_ARN=... python3 -m bench.latency --runs 10

cold: a new runtime session id per call, so AgentCore starts a fresh session.
warm: one session id reused for every call.
Each call is a card GET followed by message/send, signed as speedrun-caller-invoke.
Signing time is measured inside the httpx.Auth, per request.
"""

from __future__ import annotations

import argparse
import json

from bench.common import (
    assume, call, card_url, message_body, signer, summary, worker, write_result,
)
from caller.sigv4 import new_session_id, runtime_url

QUESTION = "Convert 250 USD to EUR and JPY"


def one(url: str, card: str, auth, session_id: str) -> dict:
    c = call("GET", card, auth, session_id)
    m = call("POST", url, auth, session_id, message_body(QUESTION))
    ok = m["status"] == 200 and '"result"' in m["body"]
    return {"card_s": c["seconds"], "message_s": m["seconds"],
            "card_status": c["status"], "message_status": m["status"], "ok": ok,
            "body": m["body"][:600]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=10)
    args = ap.parse_args()

    arn, region = worker()
    url, card = runtime_url(arn, region), card_url(arn, region)
    session = assume("speedrun-caller-invoke", region)
    auth = signer(session, region)

    cold = [one(url, card, auth, new_session_id()) for _ in range(args.runs)]
    warm_id = new_session_id()
    one(url, card, auth, warm_id)  # start the session; not counted
    warm = [one(url, card, auth, warm_id) for _ in range(args.runs)]

    report = {
        "question": QUESTION,
        "runs": args.runs,
        "cold": {"ok": sum(r["ok"] for r in cold),
                 "card_s": summary([r["card_s"] for r in cold]),
                 "message_s": summary([r["message_s"] for r in cold])},
        "warm": {"ok": sum(r["ok"] for r in warm),
                 "card_s": summary([r["card_s"] for r in warm]),
                 "message_s": summary([r["message_s"] for r in warm])},
        "sign_ms": summary([1000 * s for s in auth.sign_seconds]),
    }
    path = write_result("latency", {**report, "runtime_arn": arn,
                                    "raw": {"cold": cold, "warm": warm}})
    print(json.dumps(report, indent=2))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
