---
name: teardown
description: Remove the deployed AgentCore worker stack in us-east-1, delete the three speedrun-caller-* IAM roles and the speedrun-operator IAM user and AWS profile.
disable-model-invocation: true
---

Tear down everything a speed-run pass created. Show the user what will be deleted and get a yes before step 2.

1. Inventory:
   - `cd strandsiam && agentcore status --region us-east-1`
   - `aws iam get-role --role-name <role>` for `speedrun-caller-invoke`, `speedrun-caller-runtime-only`, `speedrun-caller-none`.
2. Remove the stack. The CLI deletes the target's stack when the project declares nothing to deploy, so empty the project, deploy, then restore the tracked config:
   ```
   cd strandsiam
   agentcore remove all --yes
   agentcore deploy --yes --region us-east-1
   git checkout -- agentcore/agentcore.json
   ```
   Then confirm `git status` shows no other changes under `strandsiam/` (restore any the remove touched).
3. Delete the roles (each inline policy first; `setup_roles.sh` names it `invoke-worker`, and `speedrun-caller-none` has none):
   ```
   for r in speedrun-caller-invoke speedrun-caller-runtime-only; do
     aws iam delete-role-policy --role-name "$r" --policy-name invoke-worker
   done
   for r in speedrun-caller-invoke speedrun-caller-runtime-only speedrun-caller-none; do
     aws iam delete-role --role-name "$r"
   done
   ```
4. Delete the operator user and its profile:
   ```
   u=speedrun-operator
   for k in $(aws iam list-access-keys --user-name $u --query 'AccessKeyMetadata[].AccessKeyId' --output text); do
     aws iam delete-access-key --user-name $u --access-key-id "$k"
   done
   aws iam delete-user-policy --user-name $u --policy-name assume-speedrun-callers
   aws iam delete-user --user-name $u
   ```
   Then remove the `[speedrun-operator]` sections from `~/.aws/credentials` and `~/.aws/config`.
5. Re-run the step-1 inventory (plus `aws iam get-user --user-name speedrun-operator`) and report what remains.
