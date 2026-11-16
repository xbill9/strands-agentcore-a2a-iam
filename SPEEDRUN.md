# CB Speed Run 2 — run list

Submission window: 2026-11-16 to 2026-11-23 (only submissions in this window qualify).
Bar: a new article on AWS Builder Center that teaches how to implement, not just what exists.

#### Step 1 — Fresh run (costs a little in the AWS account)

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
```

- [x] Deploy and export the runtime ARN
- [x] Set up the caller roles
- [x] Run `caller.ask` and `caller.coordinator` once each
- [x] Run `bench.boundary`, which records allowed and refused calls exactly as returned
- [x] Run `bench.latency --runs 10` for cold and warm session latency and signing time
- [x] Confirm `results/` holds the JSON with the account ID redacted, then commit it

Every figure in the article comes from these result files.

#### Step 2 — Draft the article (publishing skill)

- [x] Builder Center format, in the dev.to voice: `Step N —` sections, `🔎 Tip:`, Compare and Contrast, `So, Which One?`, 🟢 ❌ ⚠️ summary, Scope paragraph, closing, `#### References`
- [x] Walk the build step by step: deploy the worker, turn on IAM inbound auth, SigV4 signing (`caller/sigv4.py`), the `A2AAgent` wrapper (`caller/worker.py`), the single-ARN policy (`iam/invoke-policy.json`)
- [x] Results: the access-test table and the latency numbers, taken from `results/`

#### Step 3 — Cover image and preflight

- [x] Make the cover image
- [x] Run the preflight check (it also checks the prose)
- [ ] Optional: post the draft in #cb-speed-run-2 for feedback

#### Step 4 — Qualify and submit (you do these on Builder Center)

- [ ] Builder Center profile complete: name, profile picture, bio
- [ ] One badge unlocked: Conversation Starter, Valued Creator, Meaningful Contributor or Idea Influencer
- [x] Article published on Builder Center
- [ ] Submitted in the Speed Run Space
- [ ] Pulse form completed
