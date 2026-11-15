#!/usr/bin/env bash
# 向显式指定的集群部署一个 Helm release；不代办数据库初始化或迁移。
# 用法：deploy.sh --kubeconfig FILE --context NAME --namespace NAME \
#                 --release NAME --chart LOCAL_PATH --values FILE
# 依赖：Helm 及 check-target.sh。部署失败非零退出，不自动卸载或接管资源。
set -euo pipefail

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

# 校验输入和目标后才执行 Helm；错误由工具输出并沿原退出码返回。
main() {
  local kubeconfig=''
  local context=''
  local namespace=''
  local release=''
  local chart=''
  local values=''

  # 每个参数只能出现一次；不接受后一个参数覆盖前一个参数。
  while (($#)); do
    if (($# < 2)) || [[ -z "$2" || "$2" == --* ]]; then
      fail "Missing value for $1"
    fi

    case "$1" in
      --kubeconfig)
        [[ -z "$kubeconfig" ]] || fail 'Duplicate kubeconfig'
        kubeconfig="$2"
        ;;
      --context)
        [[ -z "$context" ]] || fail 'Duplicate context'
        context="$2"
        ;;
      --namespace)
        [[ -z "$namespace" ]] || fail 'Duplicate namespace'
        namespace="$2"
        ;;
      --release)
        [[ -z "$release" ]] || fail 'Duplicate release'
        release="$2"
        ;;
      --chart)
        [[ -z "$chart" ]] || fail 'Duplicate chart'
        chart="$2"
        ;;
      --values)
        [[ -z "$values" ]] || fail 'Duplicate values'
        values="$2"
        ;;
      *)
        fail "Unknown argument: $1"
        ;;
    esac
    shift 2
  done

  if [[ -z "$release" || ! -e "$chart" || ! -f "$values" ]]; then
    fail 'Explicit release, local chart and values file are required'
  fi
  if [[ ${#release} -gt 53 || ! "$release" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]]; then
    fail 'Invalid release name'
  fi
  command -v helm >/dev/null || fail 'helm is required'

  # 复用只读预检，避免各部署入口对目标就绪产生不同判断。
  bash "$(dirname "$0")/check-target.sh" \
    --kubeconfig "$kubeconfig" \
    --context "$context" \
    --namespace "$namespace"

  local target=(
    --kubeconfig="$kubeconfig"
    --kube-context="$context"
    --namespace="$namespace"
  )
  echo "release=$release chart=$chart values=$values"

  # 先检查 Chart；禁止上游 schema hooks，初始化必须由独立步骤明确执行。
  helm "${target[@]}" lint "$chart" -f "$values"
  helm "${target[@]}" upgrade --install "$release" "$chart" -f "$values" \
    --no-hooks --wait --timeout 5m
}

main "$@"
