#!/usr/bin/env bash
# Launch the whole multi-region benchmark from a disposable EC2 orchestrator host
# instead of from a laptop.
#
# WHY THIS EXISTS
# ---------------
# The first multi-region attempt ran the orchestrator on a Mac. The Mac slept
# ~33 minutes into the first load level. Three things then went wrong at once:
#   1. the in-cluster benchmark jobs were killed mid-ingest, so ZERO results,
#   2. `terraform destroy` in the teardown trap failed DNS resolution, so four
#      EKS clusters sat orphaned for 8.5 hours, and
#   3. the ~1h `ada` session credentials expired, so nothing could be cleaned up
#      afterwards without a human re-running mwinit.
#
# Running on EC2 fixes all three by construction:
#   * the host does not sleep and does not lose its network,
#   * an IAM *instance profile* supplies credentials that refresh forever, so a
#     long run can never run out of permissions mid-teardown,
#   * results stream to S3 as they are produced, so the data survives even if
#     the host, the operator's laptop, or the run itself dies partway through.
#
# A deadman timer force-destroys everything after DEADMAN_HOURS no matter what
# state the run is in, so a hang can no longer bill indefinitely.
#
# Usage:
#   bash scripts/launch-remote.sh                      # launch and detach
#   REGIONS=us-west-2,eu-central-1 bash scripts/launch-remote.sh
#   DEADMAN_HOURS=8 bash scripts/launch-remote.sh
#   BENCH_LOADS=saturate bash scripts/launch-remote.sh   # one load level only
#
# BENCH_* variables are forwarded to the orchestrator host (see BENCH_ENV below),
# because generate.py reads its matrix from the environment. Without forwarding,
# a run launched with BENCH_LOADS=saturate would silently execute all four load
# levels on the host and there would be no way to tell from the outside.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

HOST_REGION="${HOST_REGION:-us-west-2}"        # where the orchestrator host runs
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.large}"
DEADMAN_HOURS="${DEADMAN_HOURS:-7}"
REGIONS="${REGIONS:-}"                          # empty => auto-detect in run-all.sh
STACK="osb-bench-orchestrator"

# Forwarded verbatim into the host bootstrap as `export K=V` lines. Only the
# variables that are actually set are emitted, so an unset BENCH_LOADS leaves
# generate.py on its own default rather than exporting an empty string (which
# generate.py would split into a single empty load key and reject).
BENCH_ENV=""
for v in BENCH_LOADS BENCH_FAMILIES BENCH_REGIONS_OVERRIDE BENCH_LOADGEN_TYPE MIN_PERMS; do
  if [[ -n "${!v:-}" ]]; then
    BENCH_ENV+="export ${v}='${!v}'"$'\n'
    echo "forwarding ${v}=${!v}"
  fi
done

log() { echo; echo "=== $1"; }

command -v aws >/dev/null || { echo "aws CLI is required."; exit 1; }

ACCOUNT=$(aws sts get-caller-identity --query Account --output text) || {
  echo "Cannot reach STS. Credentials are expired -- run 'mwinit' then retry."
  exit 1
}
BUCKET="osb-bench-results-${ACCOUNT}"
RUN_ID="run-$(date -u '+%Y%m%dT%H%M%SZ')"

log "STEP 1/6: Results bucket s3://${BUCKET}"
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "bucket exists"
else
  if [[ "$HOST_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$BUCKET" --region us-east-1 >/dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$HOST_REGION" \
      --create-bucket-configuration "LocationConstraint=${HOST_REGION}" >/dev/null
  fi
  # Block public access explicitly: benchmark output is not secret, but a public
  # bucket in a shared account is a liability nobody asked for.
  aws s3api put-public-access-block --bucket "$BUCKET" \
    --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" >/dev/null
  echo "bucket created"
fi

log "STEP 2/6: Uploading the repo to S3"
# Ship a tarball rather than cloning from GitHub: the host then needs no git
# credentials, and we benchmark exactly the working tree being reviewed.
TAR="/tmp/${STACK}-src.tgz"
tar --exclude='.git' --exclude='.runs' --exclude='logs' --exclude='.terraform*' \
    --exclude='k8s/generated' -czf "$TAR" -C "$ROOT" .
aws s3 cp "$TAR" "s3://${BUCKET}/${RUN_ID}/src.tgz" >/dev/null
echo "uploaded s3://${BUCKET}/${RUN_ID}/src.tgz ($(du -h "$TAR" | cut -f1))"

log "STEP 3/6: IAM role for the orchestrator"
ROLE="${STACK}-role"
TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
if aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  echo "role exists"
else
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document "$TRUST" >/dev/null
  # PowerUserAccess covers EC2/EKS/VPC/KMS/CloudWatch/S3. IAM is deliberately
  # NOT included by it, so grant only the role operations the EKS module needs,
  # scoped to the osb-bench-* name prefix rather than account-wide.
  aws iam attach-role-policy --role-name "$ROLE" \
    --policy-arn arn:aws:iam::aws:policy/PowerUserAccess >/dev/null
  aws iam attach-role-policy --role-name "$ROLE" \
    --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore >/dev/null
  aws iam put-role-policy --role-name "$ROLE" --policy-name scoped-iam-for-eks \
    --policy-document "{
      \"Version\":\"2012-10-17\",
      \"Statement\":[
        {\"Effect\":\"Allow\",
         \"Action\":[\"iam:CreateRole\",\"iam:DeleteRole\",\"iam:GetRole\",\"iam:PassRole\",
                     \"iam:TagRole\",\"iam:ListRoleTags\",\"iam:AttachRolePolicy\",
                     \"iam:DetachRolePolicy\",\"iam:ListAttachedRolePolicies\",
                     \"iam:PutRolePolicy\",\"iam:DeleteRolePolicy\",\"iam:GetRolePolicy\",
                     \"iam:ListRolePolicies\",\"iam:CreateServiceLinkedRole\",
                     \"iam:ListInstanceProfilesForRole\",\"iam:UpdateAssumeRolePolicy\"],
         \"Resource\":[\"arn:aws:iam::${ACCOUNT}:role/osb-bench-*\",
                       \"arn:aws:iam::${ACCOUNT}:role/aws-service-role/*\"]},
        {\"Effect\":\"Allow\",
         \"Action\":[\"iam:CreatePolicy\",\"iam:DeletePolicy\",\"iam:GetPolicy\",
                     \"iam:GetPolicyVersion\",\"iam:ListPolicyVersions\",
                     \"iam:CreatePolicyVersion\",\"iam:DeletePolicyVersion\",
                     \"iam:TagPolicy\",\"iam:ListPolicyTags\"],
         \"Resource\":\"arn:aws:iam::${ACCOUNT}:policy/osb-bench-*\"},
        {\"Effect\":\"Allow\",\"Action\":[\"iam:ListRoles\",\"iam:ListPolicies\",
                     \"iam:ListOpenIDConnectProviders\",\"iam:GetOpenIDConnectProvider\",
                     \"iam:CreateOpenIDConnectProvider\",\"iam:DeleteOpenIDConnectProvider\",
                     \"iam:TagOpenIDConnectProvider\"],
         \"Resource\":\"*\"}
      ]}" >/dev/null
  echo "role created (PowerUserAccess + SSM + IAM scoped to osb-bench-*)"
fi

PROFILE="${STACK}-profile"
if ! aws iam get-instance-profile --instance-profile-name "$PROFILE" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$PROFILE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE" \
    --role-name "$ROLE" >/dev/null
  echo "instance profile created; waiting 15s for IAM propagation"
  sleep 15
fi

log "STEP 4/6: Building host bootstrap script"
USERDATA="/tmp/${STACK}-userdata.sh"
cat > "$USERDATA" <<USERDATA_EOF
#!/bin/bash
# Orchestrator host bootstrap. Everything it needs comes from the instance
# profile, so there is no credential lifetime to run out.
exec > >(tee -a /var/log/osb-bootstrap.log) 2>&1
set -x

BUCKET="${BUCKET}"
RUN_ID="${RUN_ID}"
REGIONS_ARG="${REGIONS}"
DEADMAN_HOURS="${DEADMAN_HOURS}"
export AWS_REGION="${HOST_REGION}"
export AWS_DEFAULT_REGION="${HOST_REGION}"
export HOME=/root

dnf install -y jq git tar gzip python3-pip unzip at
systemctl enable --now atd
pip3 install --quiet boto3

# terraform
TF_VER=1.9.8
curl -fsSL -o /tmp/tf.zip "https://releases.hashicorp.com/terraform/\${TF_VER}/terraform_\${TF_VER}_linux_amd64.zip"
unzip -o /tmp/tf.zip -d /usr/local/bin
# kubectl
curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/v1.31.0/bin/linux/amd64/kubectl"
chmod +x /usr/local/bin/kubectl
# helm
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

mkdir -p /opt/osb && cd /opt/osb
aws s3 cp "s3://\${BUCKET}/\${RUN_ID}/src.tgz" src.tgz
tar xzf src.tgz
chmod +x scripts/*.sh
# Must exist before the redirect below and before the first sync pass.
mkdir -p /opt/osb/logs /opt/osb/results

# ---- continuous sync: results and logs land in S3 while the run is in flight,
# ---- so partial data is recoverable even if the host dies mid-benchmark.
cat > /usr/local/bin/osb-sync <<'SYNC'
#!/bin/bash
while true; do
  aws s3 sync /opt/osb/results "s3://BUCKET_PLACEHOLDER/RUNID_PLACEHOLDER/results" --only-show-errors
  aws s3 sync /opt/osb/logs    "s3://BUCKET_PLACEHOLDER/RUNID_PLACEHOLDER/logs"    --only-show-errors
  aws s3 cp /var/log/osb-bootstrap.log "s3://BUCKET_PLACEHOLDER/RUNID_PLACEHOLDER/bootstrap.log" --only-show-errors
  sleep 60
done
SYNC
sed -i "s|BUCKET_PLACEHOLDER|\${BUCKET}|g; s|RUNID_PLACEHOLDER|\${RUN_ID}|g" /usr/local/bin/osb-sync
chmod +x /usr/local/bin/osb-sync
nohup /usr/local/bin/osb-sync >/dev/null 2>&1 &

# ---- deadman: force teardown + self-terminate after DEADMAN_HOURS regardless of
# ---- what the run is doing. This is the backstop that makes an orphaned cluster
# ---- impossible rather than merely unlikely.
cat > /usr/local/bin/osb-deadman <<'DEADMAN'
#!/bin/bash
echo "DEADMAN FIRED at \$(date -u)" | tee -a /var/log/osb-bootstrap.log
pkill -f run-all.sh || true
sleep 5
for d in /opt/osb/.runs/*/; do
  rg=\$(basename "\$d")
  [[ "\$rg" == "_warm" ]] && continue
  echo "deadman destroying \$rg"
  ( cd "\$d" && AWS_REGION="\$rg" timeout 3600 terraform destroy -auto-approve -input=false ) || true
done
aws s3 sync /opt/osb/results "s3://BUCKET_PLACEHOLDER/RUNID_PLACEHOLDER/results" --only-show-errors || true
aws s3 sync /opt/osb/logs    "s3://BUCKET_PLACEHOLDER/RUNID_PLACEHOLDER/logs"    --only-show-errors || true
aws s3 cp /var/log/osb-bootstrap.log "s3://BUCKET_PLACEHOLDER/RUNID_PLACEHOLDER/bootstrap.log" || true
TOKEN=\$(curl -sX PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')
IID=\$(curl -s -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --region AWSREGION_PLACEHOLDER --instance-ids "\$IID" || true
DEADMAN
sed -i "s|BUCKET_PLACEHOLDER|\${BUCKET}|g; s|RUNID_PLACEHOLDER|\${RUN_ID}|g; s|AWSREGION_PLACEHOLDER|${HOST_REGION}|g" /usr/local/bin/osb-deadman
chmod +x /usr/local/bin/osb-deadman
echo "/usr/local/bin/osb-deadman" | at now + \${DEADMAN_HOURS} hours

# ---- the run itself
cd /opt/osb
${BENCH_ENV}
REGION_FLAG=""
[[ -n "\${REGIONS_ARG}" ]] && REGION_FLAG="--regions \${REGIONS_ARG}"
nohup bash -c "bash scripts/run-all.sh --yes \${REGION_FLAG} > logs/run-all.log 2>&1; \
  echo RUN_EXIT=\\\$? >> logs/run-all.log; \
  python3 scripts/report.py >> logs/run-all.log 2>&1 || true; \
  /usr/local/bin/osb-deadman" > /var/log/osb-run.log 2>&1 &
USERDATA_EOF

log "STEP 5/6: Launching the orchestrator host in ${HOST_REGION}"
AMI=$(aws ssm get-parameter --region "$HOST_REGION" \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameter.Value' --output text)
VPC=$(aws ec2 describe-vpcs --region "$HOST_REGION" \
  --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
[[ "$VPC" != "None" ]] || { echo "No default VPC in ${HOST_REGION}."; exit 1; }
SUBNET=$(aws ec2 describe-subnets --region "$HOST_REGION" \
  --filters "Name=vpc-id,Values=${VPC}" "Name=map-public-ip-on-launch,Values=true" \
  --query 'Subnets[0].SubnetId' --output text)
[[ "$SUBNET" != "None" ]] || { echo "No public subnet in the default VPC."; exit 1; }

# Egress-only security group: the host needs to reach AWS APIs, nothing needs to
# reach the host (management is via SSM, not SSH).
SG=$(aws ec2 describe-security-groups --region "$HOST_REGION" \
  --filters "Name=group-name,Values=${STACK}-sg" "Name=vpc-id,Values=${VPC}" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo None)
if [[ "$SG" == "None" || -z "$SG" ]]; then
  SG=$(aws ec2 create-security-group --region "$HOST_REGION" \
    --group-name "${STACK}-sg" --description "osb-bench orchestrator: egress only" \
    --vpc-id "$VPC" --query GroupId --output text)
  aws ec2 revoke-security-group-egress --region "$HOST_REGION" --group-id "$SG" \
    --protocol -1 --port -1 --cidr 0.0.0.0/0 >/dev/null 2>&1 || true
  aws ec2 authorize-security-group-egress --region "$HOST_REGION" --group-id "$SG" \
    --protocol tcp --port 443 --cidr 0.0.0.0/0 >/dev/null 2>&1 || true
  aws ec2 authorize-security-group-egress --region "$HOST_REGION" --group-id "$SG" \
    --protocol tcp --port 80 --cidr 0.0.0.0/0 >/dev/null 2>&1 || true
fi

IID=$(aws ec2 run-instances --region "$HOST_REGION" \
  --image-id "$AMI" --instance-type "$INSTANCE_TYPE" \
  --iam-instance-profile "Name=${PROFILE}" \
  --subnet-id "$SUBNET" --security-group-ids "$SG" \
  --associate-public-ip-address \
  --metadata-options "HttpTokens=required,HttpEndpoint=enabled" \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":100,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
  --user-data "file://${USERDATA}" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${STACK}},{Key=osb-bench-run,Value=${RUN_ID}}]" \
  --instance-initiated-shutdown-behavior terminate \
  --query 'Instances[0].InstanceId' --output text)

log "STEP 6/6: Launched"
cat <<SUMMARY

  Orchestrator instance : ${IID}  (${INSTANCE_TYPE} in ${HOST_REGION})
  Run ID                : ${RUN_ID}
  Results (live)        : s3://${BUCKET}/${RUN_ID}/results/
  Logs (live, ~60s lag) : s3://${BUCKET}/${RUN_ID}/logs/
  Deadman               : force-destroy + self-terminate after ${DEADMAN_HOURS}h

  You can close your laptop now. Nothing about the run depends on it.

  Watch progress:
    aws s3 ls s3://${BUCKET}/${RUN_ID}/logs/
    aws s3 cp s3://${BUCKET}/${RUN_ID}/logs/run-all.log - | tail -40

  Fetch results when done:
    aws s3 sync s3://${BUCKET}/${RUN_ID}/results ./results

  Shell into the host (no SSH key needed):
    aws ssm start-session --region ${HOST_REGION} --target ${IID}

  Kill it early (also tears down every region):
    aws ssm send-command --region ${HOST_REGION} --instance-ids ${IID} \\
      --document-name AWS-RunShellScript \\
      --parameters 'commands=["/usr/local/bin/osb-deadman"]'
SUMMARY
