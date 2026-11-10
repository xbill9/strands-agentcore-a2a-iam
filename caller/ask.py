"""One question to the AgentCore worker over A2A, signed with SigV4.

    WORKER_RUNTIME_ARN=arn:aws:bedrock-agentcore:... python3 -m caller.ask "Convert 250 USD to EUR"
"""

from __future__ import annotations

import asyncio
import sys
import time

from caller.worker import remote_worker


async def main(question: str) -> int:
    agent, http, signer = remote_worker()
    async with http:
        t0 = time.perf_counter()
        card = await agent.get_agent_card()
        t1 = time.perf_counter()
        print(f"card: name={card.name!r} url={card.url}  ({t1 - t0:.2f} s)")
        result = await agent.invoke_async(question)
        t2 = time.perf_counter()
    print(f"answer ({t2 - t1:.2f} s):\n{result}")
    print(f"signed {len(signer.sign_seconds)} requests, "
          f"{1000 * sum(signer.sign_seconds):.2f} ms signing in total")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1])))
