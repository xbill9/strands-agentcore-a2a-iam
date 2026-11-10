"""The remote worker as a Strands A2AAgent, reached with SigV4."""

from __future__ import annotations

import os

import boto3
from a2a.client import ClientConfig
from strands.agent.a2a_agent import A2AAgent

from caller.sigv4 import runtime_url, signed_client


def settings() -> tuple[str, str]:
    arn = os.environ.get("WORKER_RUNTIME_ARN")
    if not arn:
        raise SystemExit("set WORKER_RUNTIME_ARN (printed by `agentcore deploy`)")
    region = arn.split(":")[3]
    return arn, region


def remote_worker(session: boto3.Session | None = None, session_id: str | None = None):
    """Return (A2AAgent, httpx client, signer) for the deployed worker."""
    arn, region = settings()
    session = session or boto3.Session(region_name=region)
    http, signer = signed_client(session, region, session_id)
    agent = A2AAgent(
        endpoint=runtime_url(arn, region),
        client_config=ClientConfig(httpx_client=http),
    )
    return agent, http, signer
