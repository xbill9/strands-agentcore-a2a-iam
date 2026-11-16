"""Two requests at once: on one runtime session, and on two.

    WORKER_RUNTIME_ARN=... python3 -m bench.session --pairs 5

Each pair sends two message/send calls at the same moment, signed as
speedrun-caller-invoke. "same" pairs share one session id; "separate" pairs
use one each. Writes results/<stamp>/session.json with every status and body,
and the status counts per mode.
"""

from __future__ import annotations

import argparse
import threading
from collections import Counter

from bench.common import assume, call, message_body, signer, worker, write_result
from caller.sigv4 import new_session_id, runtime_url

QUESTION = "Convert 100 USD to EUR"


def pair(url: str, auth, session_ids: tuple[str, str]) -> list[dict]:
    start = threading.Barrier(2)
    out: list[dict] = [{}, {}]

    def go(i: int) -> None:
        start.wait()
        r = call("POST", url, auth, session_ids[i], message_body(QUESTION))
        r["body"] = r["body"][:400]
        out[i] = r

    threads = [threading.Thread(target=go, args=(i,)) for i in (0, 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=5)
    args = ap.parse_args()

    arn, region = worker()
    url = runtime_url(arn, region)
    auth = signer(assume("speedrun-caller-invoke", region), region)

    raw: dict[str, list] = {"same": [], "separate": []}
    for _ in range(args.pairs):
        sid = new_session_id()
        raw["same"].append(pair(url, auth, (sid, sid)))
        raw["separate"].append(pair(url, auth, (new_session_id(), new_session_id())))

    counts = {
        mode: dict(Counter(str(r["status"]) for p in pairs for r in p))
        for mode, pairs in raw.items()
    }
    for mode, c in counts.items():
        print(f"{mode:9s} {args.pairs} pairs: {c}")
    conflicts = [r["body"] for p in raw["same"] for r in p if r["status"] == 409]
    if conflicts:
        print(f"409 body: {conflicts[0][:200]!r}")

    path = write_result(
        "session",
        {
            "runtime_arn": arn,
            "region": region,
            "question": QUESTION,
            "pairs": args.pairs,
            "status_counts": counts,
            "raw": raw,
        },
    )
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
