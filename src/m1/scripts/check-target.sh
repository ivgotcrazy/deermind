#!/usr/bin/env bash
# 只读检查指定集群、命名空间及节点，不修改任何 kubeconfig 或默认 context。
# 用法：check-target.sh --kubeconfig FILE --context NAME --namespace NAME
# 依赖：kubectl、GNU timeout。失败写 stderr 并以非零状态退出。
set -euo pipefail

usage() {
  echo 'Usage: check-target.sh --kubeconfig FILE --context NAME --namespace NAME'
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

# 使用显式目标执行只读查询；外层时限也覆盖 kubectl 本地配置处理。
# 参数：kubeconfig、context、namespace，随后为 kubectl 子命令。
# 输出：透传 kubectl 的 stdout/stderr；返回其退出码或 timeout 的退出码。
kube() {
  local kubeconfig="$1"
  local context="$2"
  local namespace="$3"
  shift 3

  timeout 15s kubectl \
    --kubeconfig="$kubeconfig" \
    --context="$context" \
    --namespace="$namespace" \
    --request-timeout=10s \
    "$@"
}

# 按“解析参数 → 本地校验 → 远端检查 → 汇总”执行；不做自动修复。
main() {
  local kubeconfig=''
  local context=''
  local namespace=''

  # 先拒绝缺值和重复参数，避免悄悄覆盖用户指定的目标。
  while (($#)); do
    case "$1" in
      --help)
        usage
        return 0
        ;;
      --kubeconfig | --context | --namespace)
        if (($# < 2)) || [[ -z "$2" || "$2" == --* ]]; then
          fail "Missing value for $1"
        fi

        case "$1" in
          --kubeconfig)
            [[ -z "$kubeconfig" ]] || fail 'Duplicate --kubeconfig'
            kubeconfig="$2"
            ;;
          --context)
            [[ -z "$context" ]] || fail 'Duplicate --context'
            context="$2"
            ;;
          --namespace)
            [[ -z "$namespace" ]] || fail 'Duplicate --namespace'
            namespace="$2"
            ;;
        esac
        shift 2
        ;;
      *)
        usage >&2
        fail "Unknown argument: $1"
        ;;
    esac
  done

  # 本地校验必须全部通过后，才能访问集群。
  if [[ -z "$kubeconfig" || -z "$context" || -z "$namespace" ]]; then
    fail 'Explicit kubeconfig, context and namespace are required'
  fi
  if [[ ! -f "$kubeconfig" || ! -r "$kubeconfig" ]]; then
    fail 'Kubeconfig is not a readable file'
  fi
  if [[ ${#namespace} -gt 63 || ! "$namespace" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
    fail 'Invalid namespace name'
  fi
  command -v kubectl >/dev/null || fail 'kubectl is required'
  command -v timeout >/dev/null || fail 'GNU timeout is required'

  local target=("$kubeconfig" "$context" "$namespace")
  local server
  local ready
  local phase
  local nodes
  local name
  local status
  local node_query='{range .items[*]}{.metadata.name}{"\t"}'
  node_query+='{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}'

  # 不使用 current-context；先确认指定 context 能解析到 API 地址。
  server=$(kube "${target[@]}" config view --minify \
    -o 'jsonpath={.clusters[0].cluster.server}' 2>/dev/null) ||
    fail 'Cannot resolve the requested context from kubeconfig'
  [[ -n "$server" ]] || fail 'The selected context has no API server'

  ready=$(kube "${target[@]}" get --raw=/readyz 2>/dev/null) ||
    fail 'API server is unavailable, not ready, or access is denied'
  [[ "$ready" == ok ]] || fail 'API server is not ready'

  phase=$(kube "${target[@]}" get namespace "$namespace" \
    -o 'jsonpath={.status.phase}' 2>/dev/null) ||
    fail 'Namespace does not exist or access is denied'
  [[ "$phase" == Active ]] || fail 'Namespace is not active'

  # API 可达不代表节点可用；所有已返回节点均须 Ready。
  nodes=$(kube "${target[@]}" get nodes -o "jsonpath=$node_query" 2>/dev/null) ||
    fail 'Cannot read node readiness with this deployment identity'
  [[ -n "$nodes" ]] || fail 'Cluster has no nodes'

  while IFS=$'\t' read -r name status; do
    [[ "$status" == True ]] || fail "Node is not ready: $name"
  done <<<"$nodes"

  printf 'PASS: target is reachable and ready\ncontext=%s\nnamespace=%s\nserver=%s\n%s\n' \
    "$context" "$namespace" "$server" "$nodes"
}

main "$@"
