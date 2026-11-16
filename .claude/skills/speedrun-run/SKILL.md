---
name: speedrun-run
description: Deploy the AgentCore worker to us-east-1, create the caller roles, run ask/coordinator and both benches, check results are redacted, and commit them to main.
disable-model-invocation: true
---

Run one full speed-run pass. Stop and report on the first failing step; quote its output verbatim.

1. Deploy (from `strandsiam/`): `agentcore deploy -y --region us-east-1`. Take the runtime ARN from the output (or `agentcore status --region us-east-1`). Export it as `WORKER_RUNTIME_ARN` for every later command.
2. From the repo root: `iam/setup_roles.sh`.
3. Smoke tests:
   - `python3 -m caller.ask "Convert 250 USD to EUR and JPY"`
   - `python3 -m caller.coordinator "I have 1200 USD. What is that in EUR and JPY?"`
4. Benches: `python3 -m bench.boundary`, then `python3 -m bench.latency --runs ${ARGUMENTS:-10}`.
5. Redaction check — must print nothing:
   `grep -rEn '\b[0-9]{12}\b' results/ | grep -v ACCOUNT_ID`
   If anything prints, do not commit; report the file and line.
6. Commit the new `results/<stamp>/` directory straight to `main` and push.

Report the figures by quoting the result JSON, not by recomputing them.
