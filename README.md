# Strands to Strands over A2A on Bedrock AgentCore, with IAM as the only credential

A Strands currency worker served over A2A on Amazon Bedrock AgentCore Runtime, and a
local Strands coordinator that calls it. Every request is signed with SigV4 from the
caller's IAM role; the access rule is one policy on one runtime ARN: `InvokeAgentRuntime` and
`GetAgentCard` on the runtime and its endpoints (both actions are checked against
`<runtime ARN>/runtime-endpoint/DEFAULT`, so the bare ARN alone is refused).

| Path | What it is |
|---|---|
| `strandsiam/` | AgentCore project (`agentcore create --template a2a-python-strands`, CLI 1.0.2), IAM inbound auth |
| `strandsiam/app/agent/main.py` | the worker: Strands agent, `convert_currency` tool, `serve_a2a` on port 9000 |
| `caller/sigv4.py` | `httpx.Auth` that signs each request for `bedrock-agentcore` |
| `caller/worker.py` | the worker as a Strands `A2AAgent` over the signed client |
| `caller/ask.py`, `caller/coordinator.py` | one direct question; a Strands coordinator that delegates to the worker |
| `iam/` | caller roles and policies, scoped to the runtime ARN |
| `bench/boundary.py` | one call per identity and request shape, status and body recorded verbatim |
| `bench/latency.py` | cold and warm session latency, signing time |
| `bench/session.py` | two requests at once, on one runtime session and on two |
| `docs/` | the article (dev.to and Builder Center), its cover, `evidence/` and `audit_stats.py` |
| `results/` | every run's JSON (account ID redacted) |

## Run

```bash
pip install 'strands-agents[a2a]' 'bedrock-agentcore[a2a]' boto3 httpx
npm install -g @aws/agentcore
(cd strandsiam/agentcore/cdk && npm ci)                # CDK deps, once per clone
(cd strandsiam && agentcore deploy --yes --region us-east-1 && agentcore status --region us-east-1)  # status prints the runtime ARN
export WORKER_RUNTIME_ARN=arn:aws:bedrock-agentcore:...
iam/setup_roles.sh      # trusts you; as root, set CALLER_PRINCIPAL to a non-root user's ARN
python3 -m caller.ask "Convert 250 USD to EUR and JPY"
python3 -m caller.coordinator "I have 1200 USD. What is that in EUR and JPY?"
python3 -m bench.boundary                             # benches assume roles: run as non-root (e.g. AWS_PROFILE=speedrun-operator)
python3 -m bench.latency --runs 10
python3 -m bench.session --pairs 5
python3 docs/audit_stats.py                           # recomputes the article's figures from docs/evidence/
```
