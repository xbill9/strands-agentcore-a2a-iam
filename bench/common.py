"""Shared helpers: assume a caller role, raw JSON-RPC calls, result files."""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import statistics
import time
import uuid

import boto3
import httpx

from caller.sigv4 import SESSION_HEADER, SigV4, new_session_id, runtime_url

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARD_PATH = ".well-known/agent-card.json"


def worker() -> tuple[str, str]:
    arn = os.environ["WORKER_RUNTIME_ARN"]
    return arn, arn.split(":")[3]


def assume(role_name: str, region: str, tries: int = 10) -> boto3.Session:
    """Session for one of the iam/setup_roles.sh roles (retries while IAM propagates)."""
    sts = boto3.client("sts", region_name=region)
    account = sts.get_caller_identity()["Account"]
    arn = f"arn:aws:iam::{account}:role/{role_name}"
    for attempt in range(tries):
        try:
            c = sts.assume_role(RoleArn=arn, RoleSessionName="speedrun")["Credentials"]
            return boto3.Session(
                aws_access_key_id=c["AccessKeyId"],
                aws_secret_access_key=c["SecretAccessKey"],
                aws_session_token=c["SessionToken"],
                region_name=region,
            )
        except sts.exceptions.ClientError:
            if attempt == tries - 1:
                raise
            time.sleep(3)
    raise AssertionError("unreachable")


def message_body(text: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "parts": [{"kind": "text", "text": text}],
            }
        },
    }


def call(
    method: str,
    url: str,
    auth: httpx.Auth | None,
    session_id: str | None = None,
    body: dict | None = None,
    timeout: float = 180.0,
) -> dict:
    """One raw HTTP call; returns status, seconds and the verbatim body."""
    headers = {SESSION_HEADER: session_id or new_session_id()}
    t0 = time.perf_counter()
    with httpx.Client(auth=auth, timeout=timeout) as http:
        r = http.request(method, url, json=body, headers=headers)
    seconds = time.perf_counter() - t0
    return {
        "status": r.status_code,
        "seconds": round(seconds, 4),
        "request_id": r.headers.get("x-amzn-requestid"),
        "body": r.text[:2000],
    }


def card_url(arn: str, region: str) -> str:
    return runtime_url(arn, region) + CARD_PATH


def signer(session: boto3.Session, region: str, service: str = "bedrock-agentcore") -> SigV4:
    return SigV4(session, region, service)


def summary(values: list[float]) -> dict:
    """Count, median, min and max, computed here so nobody computes them by hand."""
    return {
        "n": len(values),
        "median": round(statistics.median(values), 3) if values else None,
        "min": round(min(values), 3) if values else None,
        "max": round(max(values), 3) if values else None,
    }


def write_result(name: str, payload: dict) -> pathlib.Path:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "results" / stamp
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.json"
    text = json.dumps(payload, indent=2) + "\n"
    account = worker()[0].split(":")[4]
    path.write_text(text.replace(account, "ACCOUNT_ID"))  # results are committed
    return path
