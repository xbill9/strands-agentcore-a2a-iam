"""Strands currency worker served over A2A on Bedrock AgentCore Runtime.

The runtime's inbound auth is IAM (SigV4). The tool does the arithmetic in
code with Decimal; the model only picks the arguments and relays the result.
"""

import json
import urllib.request
from decimal import Decimal

from bedrock_agentcore.runtime import serve_a2a
from strands import Agent, tool
from strands.multiagent.a2a.executor import StrandsA2AExecutor

from model.load import load_model

FRANKFURTER = "https://api.frankfurter.dev/v1/latest"

SYSTEM_PROMPT = (
    "You convert currency amounts. Always call convert_currency and copy its "
    "JSON result into your answer exactly. Do no arithmetic yourself."
)


@tool
def convert_currency(amount: str, source: str, targets: list[str]) -> str:
    """Convert an amount from one ISO 4217 currency to one or more others.

    Args:
        amount: Decimal amount as a string, for example "250.00".
        source: Source currency code, for example "USD".
        targets: Target currency codes, for example ["EUR", "JPY"].
    """
    src = source.upper()
    symbols = ",".join(t.upper() for t in targets)
    url = f"{FRANKFURTER}?base={src}&symbols={symbols}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
    value = Decimal(amount)
    return json.dumps(
        {
            "source": src,
            "amount": str(value),
            "rate_date": data["date"],
            "quotes": {
                code: {
                    "rate": str(rate),
                    "converted": str((value * Decimal(str(rate))).quantize(Decimal("0.01"))),
                }
                for code, rate in data["rates"].items()
            },
        }
    )


def create_agent(context_id: str) -> Agent:
    return Agent(
        name="currency-worker",
        description="Converts currency amounts with live ECB reference rates.",
        model=load_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[convert_currency],
        callback_handler=None,
    )


# serve_a2a binds port 9000 (the AgentCore A2A contract) and serves the card at
# /.well-known/agent-card.json. The card's "url" comes from AGENTCORE_RUNTIME_URL
# when it is set, and from http://localhost:9000/ otherwise.
if __name__ == "__main__":
    serve_a2a(StrandsA2AExecutor(agent_factory=create_agent))
