#!/usr/bin/env bash
# Read-only preflight. Never select or modify a global Kubernetes context.
set -euo pipefail

usage() {
  echo 'Usage: check-target.sh --kubeconfig FILE --context NAME --namespace NAME'
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

kubeconfig=''
context=''
namespace=''
while (($#)); do
  case "$1" in
    --help) usage; exit 0 ;;
    --kubeconfig|--context|--namespace)
      (($# >= 2)) && [[ -n "$2" && "$2" != --* ]] || fail "Missing value for $1"
      case "$1" in
        --kubeconfig) [[ -z "$kubeconfig" ]] || fail 'Duplicate --kubeconfig'; kubeconfig="$2" ;;
        --context) [[ -z "$context" ]] || fail 'Duplicate --context'; context="$2" ;;
        --namespace) [[ -z "$namespace" ]] || fail 'Duplicate --namespace'; namespace="$2" ;;
      esac
      shift 2 ;;
    *) usage >&2; fail "Unknown argument: $1" ;;
  esac
done

[[ -n "$kubeconfig" && -n "$context" && -n "$namespace" ]] || fail 'Explicit kubeconfig, context and namespace are required'
[[ -f "$kubeconfig" && -r "$kubeconfig" ]] || fail 'Kubeconfig is not a readable file'
[[ ${#namespace} -le 63 && "$namespace" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] || fail 'Invalid namespace name'
command -v kubectl >/dev/null || fail 'kubectl is required'
command -v timeout >/dev/null || fail 'GNU timeout is required'

kube() {
  timeout 15s kubectl --kubeconfig="$kubeconfig" --context="$context" \
    --namespace="$namespace" --request-timeout=10s "$@"
}

server=$(kube config view --minify -o 'jsonpath={.clusters[0].cluster.server}' 2>/dev/null) \
  || fail 'Cannot resolve the requested context from kubeconfig'
[[ -n "$server" ]] || fail 'The selected context has no API server'
ready=$(kube get --raw=/readyz 2>/dev/null) || fail 'API server is unavailable, not ready, or access is denied'
[[ "$ready" == ok ]] || fail 'API server is not ready'
phase=$(kube get namespace "$namespace" -o 'jsonpath={.status.phase}' 2>/dev/null) \
  || fail 'Namespace does not exist or access is denied'
[[ "$phase" == Active ]] || fail 'Namespace is not active'
nodes=$(kube get nodes -o 'jsonpath={range .items[*]}{.metadata.name}{"\t"}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' 2>/dev/null) \
  || fail 'Cannot read node readiness with this deployment identity'
[[ -n "$nodes" ]] || fail 'Cluster has no nodes'
while IFS=$'\t' read -r name status; do
  [[ "$status" == True ]] || fail "Node is not ready: $name"
done <<< "$nodes"

printf 'PASS: target is reachable and ready\ncontext=%s\nnamespace=%s\nserver=%s\n%s\n' \
  "$context" "$namespace" "$server" "$nodes"
