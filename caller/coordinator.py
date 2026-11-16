"""A local Strands agent that delegates currency work to the AgentCore worker.

Both sides are Strands. The coordinator's only credential is the boto3
session it runs under; the same session signs Bedrock calls and A2A calls.

    WORKER_RUNTIME_ARN=... python3 -m caller.coordinator "I have 1200 USD. What is that in EUR and JPY?"
"""

from __future__ import annotations

import asyncio
import os
import sys

from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from caller.worker import remote_worker

SYSTEM_PROMPT = (
    "You help travellers with money questions. For any currency conversion, "
    "call ask_currency_worker and quote its figures exactly."
)


async def run(question: str) -> str:
    worker, http, _ = remote_worker()
    # Strands runs a turn's tool calls concurrently, but an AgentCore runtime
    # session takes one request at a time (a second one gets 409 Conflict).
    one_at_a_time = asyncio.Lock()

    @tool
    async def ask_currency_worker(request: str) -> str:
        """Ask the remote currency worker (Strands on AgentCore, over A2A).

        Args:
            request: A plain-language conversion request with amount and currencies.
        """
        async with one_at_a_time:
            return str(await worker.invoke_async(request))

    coordinator = Agent(
        model=BedrockModel(
            model_id=os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-micro-v1:0")
        ),
        system_prompt=SYSTEM_PROMPT,
        tools=[ask_currency_worker],
        callback_handler=None,
    )
    async with http:
        result = await coordinator.invoke_async(question)
    return str(result)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    print(asyncio.run(run(sys.argv[1])))
