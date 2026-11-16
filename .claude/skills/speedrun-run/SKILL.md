---
name: speedrun-run
description: Deploy the AgentCore worker to us-east-1, create the caller roles, run ask/coordinator and both benches, check results are redacted, and commit them to main.
disable-model-invocation: true
---

Run one full speed-run pass. Stop and report on the first failing step; quote its output verbatim.

1. Deploy (from `strandsiam/`; run `npm ci` in `agentcore/cdk` first on a fresh clone): `agentcore deploy --yes --region us-east-1`, then take the runtime ARN from `agentcore status --region us-east-1`. Export it as `WORKER_RUNTIME_ARN` for every later command.
2. From the repo root, as root: `CALLER_PRINCIPAL=arn:aws:iam::<acct>:user/speedrun-operator iam/setup_roles.sh`. If the `speedrun-operator` user or AWS profile is missing, create it: IAM user with an inline policy allowing only `sts:AssumeRole` on `arn:aws:iam::<acct>:role/speedrun-caller-*`, one access key stored with `aws configure set ... --profile speedrun-operator`, region us-east-1.
3. Smoke tests:
   - `python3 -m caller.ask "Convert 250 USD to EUR and JPY"`
   - `python3 -m caller.coordinator "I have 1200 USD. What is that in EUR and JPY?"`
4. Benches, with `AWS_PROFILE=speedrun-operator` (root can't assume roles): `python3 -m bench.boundary`, then `python3 -m bench.latency --runs ${ARGUMENTS:-10}`.
5. Redaction check — must print nothing:
   `grep -rn "$(cut -d: -f5 <<<"$WORKER_RUNTIME_ARN")" results/`
   If anything prints, do not commit; report the file and line.
6. Commit the new `results/<stamp>/` directory straight to `main` and push.

Report the figures by quoting the result JSON, not by recomputing them.
