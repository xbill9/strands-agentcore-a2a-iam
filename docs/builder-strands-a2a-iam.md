# Strands to Strands over A2A on Bedrock AgentCore, With IAM as the Only Credential

This article provides a step by step guide to connecting two Strands agents over the Agent2Agent (A2A) protocol on Amazon Bedrock AgentCore Runtime, with AWS IAM as the only credential. The worker runs on AgentCore with IAM inbound auth, the caller signs every request with SigV4, and one IAM policy decides who may call it.

Repository: https://github.com/xbill9/strands-agentcore-a2a-iam

---

#### What Is A2A on AgentCore?

A2A is an open protocol for one agent to call another: the caller reads the other agent's card from `/.well-known/agent-card.json`, then sends JSON-RPC messages to it. AgentCore Runtime can host an A2A server and put it behind the AWS API front door.

With IAM inbound auth turned on, every request to the agent, the card included, has to carry a SigV4 signature from an IAM identity that is allowed to call that runtime. No API key, no OAuth client and no shared secret is involved.

---

#### At This Point You Should Have

- An AWS account with Amazon Bedrock model access to Amazon Nova Micro in `us-east-1`
- The AWS CLI, version 2, signed in
- `python3` and `node` with `npm`
- The AgentCore CLI: `npm install -g @aws/agentcore`
- The Python packages for the caller: `pip install 'strands-agents[a2a]' 'bedrock-agentcore[a2a]' boto3 httpx`

The benchmarks assume IAM roles. AWS does not let the root user assume a role, so they need an IAM user or an IAM Identity Center role. Step 6 covers it.

---

#### How It Fits Together

```text
local machine                                      AWS, us-east-1
-------------                                      --------------
caller.ask / caller.coordinator (Strands)
  A2AAgent  -- httpx + SigV4 (bedrock-agentcore) -->  AgentCore Runtime, IAM inbound auth
                                                        Strands worker, serve_a2a :9000
                                                          convert_currency tool --> frankfurter.dev
  BedrockModel (coordinator only) ----------------->  Amazon Bedrock, Nova Micro
```

One IAM identity signs both kinds of call. The coordinator's model call and its call to the worker use the same boto3 session.

---

#### Step 1 — Scaffold the Worker With IAM Inbound Auth

The AgentCore CLI has a template for a Strands agent served over A2A. The project file declares the runtime, its protocol and its authorizer:

```json
{
  "name": "agent",
  "build": "CodeZip",
  "entrypoint": "main.py",
  "codeLocation": "app/agent",
  "runtimeVersion": "PYTHON_3_14",
  "protocol": "A2A",
  "envVars": [{ "name": "BEDROCK_MODEL_ID", "value": "us.amazon.nova-micro-v1:0" }],
  "authorizerType": "AWS_IAM"
}
```

`"authorizerType": "AWS_IAM"` is the whole of the inbound auth setup. `BEDROCK_MODEL_ID` has to be an inference profile ID, with the `us.` or `global.` prefix.

---

#### Step 2 — Do the Arithmetic in the Tool

The worker is one Strands agent with one tool. The tool fetches European Central Bank reference rates and does the multiplication with `Decimal`. The model picks the arguments and copies the tool's JSON into its answer.

```python
@tool
def convert_currency(amount: str, source: str, targets: list[str]) -> str:
    """Convert an amount from one ISO 4217 currency to one or more others."""
    src = source.upper()
    symbols = ",".join(t.upper() for t in targets)
    url = f"{FRANKFURTER}?base={src}&symbols={symbols}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
    value = Decimal(amount)
    return json.dumps({
        "source": src, "amount": str(value), "rate_date": data["date"],
        "quotes": {
            code: {"rate": str(rate),
                   "converted": str((value * Decimal(str(rate))).quantize(Decimal("0.01")))}
            for code, rate in data["rates"].items()
        },
    })
```

`serve_a2a` from `bedrock_agentcore.runtime` serves it on port 9000, which is the AgentCore A2A contract:

```python
serve_a2a(StrandsA2AExecutor(agent_factory=create_agent))
```

---

#### Step 3 — Deploy and Read Back the Runtime ARN

The CDK app under `agentcore/cdk` needs its packages once per clone. Then deploy, and read the ARN from `status`:

```bash
cd strandsiam/agentcore/cdk && npm ci && cd ../..
agentcore deploy --yes --region us-east-1
agentcore status --region us-east-1 --json
```

```text
deploying AgentCore-strandsiam-default (usually takes a few minutes)
deployed project 'strandsiam' to target 'default'
{
  "resourceType": "runtime",
  "name": "agent",
  "deploymentState": "deployed",
  "arn": "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/strandsiam_default_agent-lv6O7Y6g5b"
}
```

Everything after this step reads that ARN from one environment variable:

```bash
export WORKER_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/strandsiam_default_agent-lv6O7Y6g5b
```

---

#### Step 4 — Sign Every Request With SigV4

The A2A endpoint is a regular AWS API endpoint, so the caller signs each HTTP request for the `bedrock-agentcore` service. `caller/sigv4.py` is an `httpx.Auth` that does it with botocore's signer:

```python
SERVICE = "bedrock-agentcore"
SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"
_SIGNED = {"host", "content-type", SESSION_HEADER.lower()}

class SigV4(httpx.Auth):
    requires_request_body = True

    def auth_flow(self, request: httpx.Request):
        creds = self._session.get_credentials().get_frozen_credentials()
        headers = {k: v for k, v in request.headers.items() if k.lower() in _SIGNED}
        aws_request = AWSRequest(method=request.method, url=str(request.url),
                                 data=request.content, headers=headers)
        _BotoSigV4(creds, self._service, self._region).add_auth(aws_request)
        for name in ("Authorization", "X-Amz-Date", "X-Amz-Security-Token"):
            if name in aws_request.headers:
                request.headers[name] = aws_request.headers[name]
        yield request
```

Three details decide whether a signature is accepted:

- **Sign only stable headers.** httpx adds and rewrites headers after the auth hook runs, so the signer covers `host`, `content-type` and the session header.
- **`requires_request_body = True`**, so the JSON body is available to hash.
- **The URL holds the whole ARN, percent-encoded, with a trailing slash:**

```python
def runtime_url(runtime_arn: str, region: str) -> str:
    return (
        f"https://bedrock-agentcore.{region}.amazonaws.com"
        f"/runtimes/{quote(runtime_arn, safe='')}/invocations/"
    )
```

The session header picks the runtime session. AgentCore requires at least 33 characters, and a UUID4 has 36.

---

#### Step 5 — Wrap the Worker as a Strands A2AAgent

Strands has an `A2AAgent` that speaks A2A to a remote agent. Hand it the signed httpx client and the remote worker looks like any other agent:

```python
def remote_worker(session: boto3.Session | None = None, session_id: str | None = None):
    arn, region = settings()
    session = session or boto3.Session(region_name=region)
    http, signer = signed_client(session, region, session_id)
    agent = A2AAgent(
        endpoint=runtime_url(arn, region),
        client_config=ClientConfig(httpx_client=http),
    )
    return agent, http, signer
```

`signed_client` pins one session ID on the client, so every call from one `A2AAgent` lands in the same runtime session.

---

#### Step 6 — Write the Policy: Two Actions, Two Resources

The caller needs two actions. `bedrock-agentcore:InvokeAgentRuntime` sends a message, and `bedrock-agentcore:GetAgentCard` reads the card. `A2AAgent` reads the card before its first message, so a policy without `GetAgentCard` stops the caller before it sends anything.

```json
{
  "Sid": "InvokeTheWorker",
  "Effect": "Allow",
  "Action": "bedrock-agentcore:InvokeAgentRuntime",
  "Resource": ["__RUNTIME_ARN__", "__RUNTIME_ARN__/runtime-endpoint/*"]
},
{
  "Sid": "ReadTheWorkerCard",
  "Effect": "Allow",
  "Action": "bedrock-agentcore:GetAgentCard",
  "Resource": ["__RUNTIME_ARN__", "__RUNTIME_ARN__/runtime-endpoint/*"]
}
```

`iam/setup_roles.sh` fills in the ARN and creates three roles from it: `speedrun-caller-invoke` with the policy above plus Bedrock `InvokeModel` for Nova Micro, `speedrun-caller-runtime-only` with both actions on the bare runtime ARN only, and `speedrun-caller-none` with no permissions.

```bash
iam/setup_roles.sh
```

The trust policy names the identity that ran the script. AWS answers the root user with this:

```text
An error occurred (AccessDenied) when calling the AssumeRole operation: Roles may not be assumed by root accounts.
```

From a root login, create an IAM user that may only assume these roles and point the trust at it:

```bash
CALLER_PRINCIPAL=arn:aws:iam::ACCOUNT_ID:user/speedrun-operator iam/setup_roles.sh
```

---

####  Tip: The Endpoint Is a Resource Too

A policy that names only the runtime ARN looks complete and is refused. The runtime-only role has both actions on the bare ARN, and AWS checks each action against the runtime's `DEFAULT` endpoint as well:

```text
not authorized to perform: bedrock-agentcore:GetAgentCard on resource:
  arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/strandsiam_default_agent-lv6O7Y6g5b/runtime-endpoint/DEFAULT
not authorized to perform: bedrock-agentcore:InvokeAgentRuntime on resource:
  arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/strandsiam_default_agent-lv6O7Y6g5b/runtime-endpoint/DEFAULT
```

Grant both actions on `<runtime ARN>` and `<runtime ARN>/runtime-endpoint/*`. The policy still names one runtime and nothing else.

---

#### Step 7 — Ask the Worker

`caller.ask` reads the card, sends one message, and reports how many requests it signed. Run under `speedrun-caller-invoke`:

```bash
python3 -m caller.ask "Convert 250 USD to EUR and JPY"
```

```text
card: name='agent' url=https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/arn%3Aaws%3Abedrock-agentcore%3Aus-east-1%3AACCOUNT_ID%3Aruntime%2Fstrandsiam_default_agent-lv6O7Y6g5b/invocations  (2.21 s)
answer (1.50 s):
Here is the result of your currency conversion:

- **250 USD** converts to **226.98 EUR**
- **250 USD** converts to **39,900.00 JPY**

The conversion rates are based on the date November 16, 2026.

signed 2 requests, 2.27 ms signing in total
```

Two requests, the card and the message, took 2.27 ms of signing between them.

---

#### Step 8 — Let a Strands Coordinator Delegate

`caller.coordinator` is a local Strands agent on Nova Micro with one tool, `ask_currency_worker`, which calls the remote worker through the `A2AAgent` from Step 5:

```python
worker, http, _ = remote_worker()
# Strands runs a turn's tool calls concurrently, but an AgentCore runtime
# session takes one request at a time (a second one gets 409 Conflict).
one_at_a_time = asyncio.Lock()

@tool
async def ask_currency_worker(request: str) -> str:
    """Ask the remote currency worker (Strands on AgentCore, over A2A)."""
    async with one_at_a_time:
        return str(await worker.invoke_async(request))
```

```bash
python3 -m caller.coordinator "I have 1200 USD. What is that in EUR and JPY?"
```

```text
Here is the conversion of your 1200 USD to EUR and JPY:

- **EUR**: 1200 USD is equivalent to **1089.53 EUR**.
- **JPY**: 1200 USD is equivalent to **191,520.00 JPY**.
```

Run under `speedrun-caller-invoke`, the same role signed the Bedrock model calls and the A2A calls.

---

####  Tip: One Request at a Time per Runtime Session

A model that answers "EUR and JPY" with two tool calls makes Strands run both at once. Both reach the worker on the same session ID, and AgentCore runs one request per session at a time. The second one gets HTTP 409:

```json
{"jsonrpc":"2.0","error":{"code":-32054,"message":"Session operation in progress, please retry"}}
```

`bench/session.py` measures it. It sends two messages at the same moment, five times on one shared session and five times on two separate sessions:

```bash
python3 -m bench.session --pairs 5
```

```text
same      5 pairs: {'200': 5, '409': 5}
separate  5 pairs: {'200': 10}
```

Every shared-session pair had one 409. No separate-session pair had one. Counted per pair, that is 5 of 5 against 0 of 5, two-sided Fisher's exact test p = 0.00794, with 95% Wilson intervals of [56.6%, 100.0%] and [0.0%, 43.4%].

The coordinator's lock sends the worker calls one after another on one warm session. A new session per parallel call is the other option, and Step 10 shows what that costs.

---

#### Step 9 — Test the Boundary

`bench.boundary` makes one raw call per identity and request shape, and records the status and body exactly as AWS returned them:

```bash
python3 -m bench.boundary
```

| Caller | Request | Status | AWS says |
|---|---|---|---|
| invoke role | card | 200 | the agent card |
| invoke role | message | 200 | the answer |
| runtime-only role | card | 403 | not authorized: `GetAgentCard` on `.../runtime-endpoint/DEFAULT` |
| runtime-only role | message | 403 | not authorized: `InvokeAgentRuntime` on `.../runtime-endpoint/DEFAULT` |
| no-permission role | card | 403 | not authorized: `GetAgentCard` |
| no-permission role | message | 403 | not authorized: `InvokeAgentRuntime` |
| unsigned | card | 403 | `Missing Authentication Token` |
| unsigned | message | 403 | `Missing Authentication Token` |
| invoke role, signed for `bedrock` | message | 403 | `Credential should be scoped to correct service: 'bedrock-agentcore'.` |
| invoke role, another runtime | message | 403 | not authorized: `InvokeAgentRuntime` |

Of 10 calls, 2 were allowed and 8 were refused. Each refusal names the action and the resource it was checked against, which makes a policy fix a one-line change.

---

#### Step 10 — Measure Session Latency

`bench.latency` times a card read and a message, signed as `speedrun-caller-invoke`, ten times on a new session ID each time (cold) and ten times on one reused session ID (warm):

```bash
python3 -m bench.latency --runs 10
```

| Session | Card, median | Card, range | Message, median | Message, range |
|---|---|---|---|---|
| Cold, new ID per call | 1.758 s | 1.607 to 2.365 s | 1.876 s | 1.668 to 2.065 s |
| Warm, one ID reused | 0.244 s | 0.214 to 0.254 s | 1.687 s | 1.51 to 1.81 s |

Both gaps are bigger than the run-to-run noise. A two-sided Mann-Whitney U test on the ten cold and ten warm runs gives p = 0.000183 for the card and p = 0.00728 for the message.

A new session pays its start-up on the first request, here the card read. The message includes a Nova Micro call and a rates lookup on both sides, so the session start is a smaller share of it.

---

#### Compare and Contrast: One Session or One per Call?

| | One session, calls one at a time | New session per call |
|---|---|---|
| Card read, median |  0.244 s | 1.758 s |
| Message, median |  1.687 s | 1.876 s |
| Two calls at once | 409 on the second, 5 of 5 pairs |  both 200, 5 of 5 pairs |
| Conversation state on the worker |  kept | starts empty |

---

#### So, Which One?

For one conversation, keep one session and send its calls one after another. That is what the coordinator does: a lock around the worker tool, one `A2AAgent`, one session ID.

For independent work that has to run in parallel, give each branch its own session ID and accept the start-up on its first request.

---

#### Teardown

`agentcore deploy --help` says the CLI removes the target's stack when the project declares nothing to deploy. Empty the project, deploy, restore the project file, then delete the roles and their inline policies:

```bash
cd strandsiam && agentcore remove all --yes && agentcore deploy --yes --region us-east-1
git checkout -- agentcore/agentcore.json
for r in speedrun-caller-invoke speedrun-caller-runtime-only; do
  aws iam delete-role-policy --role-name "$r" --policy-name invoke-worker
done
for r in speedrun-caller-invoke speedrun-caller-runtime-only speedrun-caller-none; do
  aws iam delete-role --role-name "$r"
done
```

If you created an IAM user to assume the roles, delete its access keys, its inline policy and the user last.

---

#### Summary

The goal of this article was to connect two Strands agents over A2A on Amazon Bedrock AgentCore Runtime with IAM as the only credential. The key to the solution was a SigV4 `httpx.Auth` handed to Strands' `A2AAgent`, and one IAM policy granting `InvokeAgentRuntime` and `GetAgentCard` on one runtime and its endpoints. The us-east-1 results were:

- One IAM role signed the caller's A2A calls and the coordinator's Bedrock calls, with no other credential anywhere.
- Of 10 boundary calls, 2 were allowed and 8 were refused, each refusal naming the action and resource.
- A reused session read the card in a median 0.244 s against 1.758 s for a new one, p = 0.000183.
- A policy on the bare runtime ARN alone is refused for both actions, at `runtime-endpoint/DEFAULT`.
- Two requests at once on one session returned a 409 in 5 of 5 pairs, and 0 of 5 on separate sessions.
- The root user cannot assume the caller roles; the benchmarks run as an IAM user allowed only to assume them.

Scope: one AgentCore runtime in us-east-1 on 2026-11-16, called from one machine. Latency is 10 cold and 10 warm runs, the session test 5 pairs per mode, and the boundary test one call per case. The worker pins `strands-agents ~= 1.57.2`; the caller ran `strands-agents` 1.64.0, `a2a-sdk` 0.3.26, `botocore` 1.43.118 and `httpx` 0.28.1. The worker and the coordinator both use Amazon Nova Micro through the `us.amazon.nova-micro-v1:0` inference profile.

The strategy for connecting Strands agents over A2A on AgentCore with IAM was validated with an incremental step by step approach.

#### References

- [Repository](https://github.com/xbill9/strands-agentcore-a2a-iam)
- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)
- [Strands Agents](https://strandsagents.com/)
- [Agent2Agent protocol](https://a2a-protocol.org/)
- [Signature Version 4 for API requests](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv.html)
- [Frankfurter exchange rates API](https://frankfurter.dev/)
