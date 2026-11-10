"""SigV4 signing for A2A calls to Bedrock AgentCore Runtime.

AgentCore's A2A endpoint sits behind the AWS API front door, so every request,
the agent-card GET included, carries a SigV4 signature from the caller's IAM
identity. This module is the whole credential story: an httpx.Auth that signs
each request with whatever boto3 session it is given.
"""

from __future__ import annotations

import time
import uuid
from urllib.parse import quote

import boto3
import httpx
from botocore.auth import SigV4Auth as _BotoSigV4
from botocore.awsrequest import AWSRequest

SERVICE = "bedrock-agentcore"
SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"

# Headers that may change between signing and sending, or that httpx sets
# itself. Signing only the stable ones keeps the signature valid.
_SIGNED = {"host", "content-type", SESSION_HEADER.lower()}


def runtime_url(runtime_arn: str, region: str) -> str:
    """Public A2A base URL for a runtime: the ARN is percent-encoded whole."""
    return (
        f"https://bedrock-agentcore.{region}.amazonaws.com"
        f"/runtimes/{quote(runtime_arn, safe='')}/invocations/"
    )


def new_session_id() -> str:
    """Runtime session ids must be at least 33 characters; a UUID4 is 36."""
    return str(uuid.uuid4())


class SigV4(httpx.Auth):
    """Sign each httpx request with SigV4 for the bedrock-agentcore service."""

    requires_request_body = True

    def __init__(self, session: boto3.Session, region: str, service: str = SERVICE):
        self._session = session
        self._region = region
        self._service = service
        self.sign_seconds: list[float] = []  # time spent signing, per request

    def auth_flow(self, request: httpx.Request):
        start = time.perf_counter()
        creds = self._session.get_credentials().get_frozen_credentials()
        headers = {k: v for k, v in request.headers.items() if k.lower() in _SIGNED}
        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers=headers,
        )
        _BotoSigV4(creds, self._service, self._region).add_auth(aws_request)
        for name in ("Authorization", "X-Amz-Date", "X-Amz-Security-Token"):
            if name in aws_request.headers:
                request.headers[name] = aws_request.headers[name]
        self.sign_seconds.append(time.perf_counter() - start)
        yield request


def signed_client(
    session: boto3.Session,
    region: str,
    session_id: str | None = None,
    service: str = SERVICE,
    timeout: float = 120.0,
) -> tuple[httpx.AsyncClient, SigV4]:
    """An httpx client that signs every request and pins one runtime session."""
    auth = SigV4(session, region, service)
    client = httpx.AsyncClient(
        auth=auth,
        timeout=timeout,
        headers={SESSION_HEADER: session_id or new_session_id()},
    )
    return client, auth
