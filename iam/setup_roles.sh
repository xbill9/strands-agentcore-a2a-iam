#!/usr/bin/env bash
# Create the caller roles used by the boundary test, each scoped to one runtime.
#
#   WORKER_RUNTIME_ARN=arn:aws:bedrock-agentcore:REGION:ACCT:runtime/ID iam/setup_roles.sh
#
# speedrun-caller-invoke        InvokeAgentRuntime on the runtime and its endpoints,
#                               plus Bedrock InvokeModel for the coordinator's own model
# speedrun-caller-runtime-only  InvokeAgentRuntime on the runtime ARN alone
# speedrun-caller-none          no permissions
#
# The trust policy names the IAM role you are running as, so only you can assume them.
set -euo pipefail
: "${WORKER_RUNTIME_ARN:?set WORKER_RUNTIME_ARN}"
here="$(cd "$(dirname "$0")" && pwd)"
region="$(cut -d: -f4 <<<"$WORKER_RUNTIME_ARN")"
account="$(cut -d: -f5 <<<"$WORKER_RUNTIME_ARN")"

me="$(aws sts get-caller-identity --query Arn --output text)"
if [[ "$me" == arn:aws:sts::*:assumed-role/* ]]; then
  role_name="$(cut -d/ -f2 <<<"$me")"
  principal="$(aws iam get-role --role-name "$role_name" --query Role.Arn --output text)"
else
  principal="$me"
fi
echo "trusting $principal"

trust="$(sed "s|__PRINCIPAL__|$principal|" "$here/trust.json")"
render() { sed -e "s|__RUNTIME_ARN__|$WORKER_RUNTIME_ARN|g" -e "s|__REGION__|$region|g" \
               -e "s|__ACCOUNT__|$account|g" "$here/$1"; }

for role in speedrun-caller-invoke speedrun-caller-runtime-only speedrun-caller-none; do
  aws iam get-role --role-name "$role" >/dev/null 2>&1 ||
    aws iam create-role --role-name "$role" --assume-role-policy-document "$trust" \
      --max-session-duration 3600 --query Role.Arn --output text
done

aws iam put-role-policy --role-name speedrun-caller-invoke \
  --policy-name invoke-worker --policy-document "$(render invoke-policy.json)"
aws iam put-role-policy --role-name speedrun-caller-runtime-only \
  --policy-name invoke-worker --policy-document "$(render runtime-only-policy.json)"
echo "roles ready; IAM changes can take a few seconds to apply"
