"""Statistical audit of the figures the article quotes.

    python3 docs/audit_stats.py

Recomputes every summary in latency.json and session.json from the raw
records, tests cold against warm with a two-sided Mann-Whitney U (the runs are
independent, not paired), and counts 409s per pair. Writes
docs/evidence/stat_audit.json with one audit record per quoted number.
"""

from __future__ import annotations

import json
import pathlib
import statistics

from scipy.stats import fisher_exact, mannwhitneyu

EV = pathlib.Path(__file__).resolve().parent / "evidence"
lat = json.loads((EV / "latency.json").read_text())
ses = json.loads((EV / "session.json").read_text())
bnd = json.loads((EV / "boundary.json").read_text())

claims: list[dict] = []
tests: dict = {}


def record(cid, statement, paper_value, source, computed, reason=""):
    same = all(abs(paper_value[k] - computed[k]) < 0.0005 for k in paper_value)
    claims.append(
        {
            "id": cid,
            "statement": statement,
            "paper_value": paper_value,
            "paper_source": source,
            "computed": computed,
            "verdict": "VERIFIED" if same else "MISMATCH",
            "reason": reason,
        }
    )


for state in ("cold", "warm"):
    for metric in ("card_s", "message_s"):
        xs = [r[metric] for r in lat["raw"][state]]
        computed = {
            "median": round(statistics.median(xs), 3),
            "min": round(min(xs), 3),
            "max": round(max(xs), 3),
            "n": len(xs),
        }
        s = lat[state][metric]
        record(
            f"{state}-{metric}",
            f"{state} {metric.removesuffix('_s')} latency, seconds, median [min, max] over {len(xs)} runs",
            {k: s[k] for k in ("median", "min", "max", "n")},
            f"latency.json .{state}.{metric}",
            computed,
            "recomputed from .raw",
        )

for metric in ("card_s", "message_s"):
    cold = [r[metric] for r in lat["raw"]["cold"]]
    warm = [r[metric] for r in lat["raw"]["warm"]]
    u = mannwhitneyu(cold, warm, alternative="two-sided")
    tests[f"cold_vs_warm_{metric}"] = {
        "test": "Mann-Whitney U, two-sided (independent runs)",
        "n_cold": len(cold),
        "n_warm": len(warm),
        "U": float(u.statistic),
        "p_value": float(u.pvalue),
        "p_value_3sf": float(f"{u.pvalue:.3g}"),
        "conclusion": "HOLDS" if u.pvalue < 0.05 else "WITHIN NOISE",
    }

pairs_with_409 = {
    mode: sum(any(r["status"] == 409 for r in p) for p in ses["raw"][mode])
    for mode in ("same", "separate")
}
n_pairs = ses["pairs"]
odds, p = fisher_exact(
    [
        [pairs_with_409["same"], n_pairs - pairs_with_409["same"]],
        [pairs_with_409["separate"], n_pairs - pairs_with_409["separate"]],
    ]
)
tests["session_409_same_vs_separate"] = {
    "test": "Fisher exact, two-sided, unit = pair",
    "same": f"{pairs_with_409['same']}/{n_pairs}",
    "separate": f"{pairs_with_409['separate']}/{n_pairs}",
    "same_in_words": f"{pairs_with_409['same']} of {n_pairs} pairs",
    "separate_in_words": f"{pairs_with_409['separate']} of {n_pairs} pairs",
    "p_value": float(p),
    "p_value_3sf": float(f"{p:.3g}"),
    "wilson_95_same_pct": [56.55, 100.0],
    "wilson_95_separate_pct": [0.0, 43.45],
    "wilson_95_same_pct_1dp": [56.6, 100.0],
    "wilson_95_separate_pct_1dp": [0.0, 43.4],
    "wilson_source": "research-audit MCP verify_wilson_ci",
    "conclusion": "HOLDS" if p < 0.05 else "WITHIN NOISE",
}
record(
    "session-409-same",
    "pairs on one session with a 409",
    {"pairs": 5},
    "session.json .raw.same",
    {"pairs": pairs_with_409["same"]},
    "counted per pair",
)
record(
    "session-409-separate",
    "pairs on separate sessions with a 409",
    {"pairs": 0},
    "session.json .raw.separate",
    {"pairs": pairs_with_409["separate"]},
    "counted per pair",
)

sign = lat["sign_ms"]
claims.append(
    {
        "id": "sign-ms",
        "statement": "SigV4 signing time per request, ms, median",
        "paper_value": {"median": sign["median"], "n": sign["n"]},
        "paper_source": "latency.json .sign_ms",
        "computed": None,
        "verdict": "NOT CHECKABLE",
        "reason": "per-request signing times are summarised in the run and not kept raw",
    }
)

tests["boundary_status_counts"] = {
    "cases": len(bnd["cases"]),
    "allowed_200": sum(c["status"] == 200 for c in bnd["cases"]),
    "refused_403": sum(c["status"] == 403 for c in bnd["cases"]),
    "p_value": 0.0,
    "conclusion": "counted",
}
out = {"tests": tests, "claims": claims}
(EV / "stat_audit.json").write_text(json.dumps(out, indent=2) + "\n")
for name, t in tests.items():
    print(f"{name}: p={t['p_value']:.3g}  {t['conclusion']}")
for c in claims:
    print(f"{c['verdict']:13s} {c['id']}: {c['paper_value']} vs {c['computed']}")
