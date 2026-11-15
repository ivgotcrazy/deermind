#!/usr/bin/env bash
# One release per invocation; database provisioning is an explicit separate step.
set -euo pipefail
fail() { echo "ERROR: $*" >&2; exit 1; }
kubeconfig='' context='' namespace='' release='' chart='' values=''
while (($#)); do
  (($# >= 2)) && [[ -n "$2" && "$2" != --* ]] || fail "Missing value for $1"
  case "$1" in
    --kubeconfig) [[ -z "$kubeconfig" ]] || fail 'Duplicate kubeconfig'; kubeconfig="$2" ;;
    --context) [[ -z "$context" ]] || fail 'Duplicate context'; context="$2" ;;
    --namespace) [[ -z "$namespace" ]] || fail 'Duplicate namespace'; namespace="$2" ;;
    --release) [[ -z "$release" ]] || fail 'Duplicate release'; release="$2" ;;
    --chart) [[ -z "$chart" ]] || fail 'Duplicate chart'; chart="$2" ;;
    --values) [[ -z "$values" ]] || fail 'Duplicate values'; values="$2" ;;
    *) fail "Unknown argument: $1" ;;
  esac
  shift 2
done
[[ -n "$release" && -e "$chart" && -f "$values" ]] || fail 'Explicit release, local chart and values file are required'
[[ ${#release} -le 53 && "$release" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] || fail 'Invalid release name'
command -v helm >/dev/null || fail 'helm is required'
bash "$(dirname "$0")/check-target.sh" --kubeconfig "$kubeconfig" --context "$context" --namespace "$namespace"
echo "release=$release chart=$chart values=$values"
target=(--kubeconfig="$kubeconfig" --kube-context="$context" --namespace="$namespace")
# Do not run upstream schema hooks, take ownership, or uninstall on failure.
helm "${target[@]}" lint "$chart" -f "$values"
helm "${target[@]}" upgrade --install "$release" "$chart" -f "$values" \
  --no-hooks --wait --timeout 5m
