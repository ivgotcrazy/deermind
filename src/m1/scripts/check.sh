#!/usr/bin/env bash
# 从 M1 根目录运行静态检查；不安装工具、不自动修复源码、不连接集群。
# 用法：check.sh（不接受参数）。工具安装方式见 quality/README.md。
# 任一步失败即非零退出；正式应用尚不存在的检查明确标为 PENDING。
set -euo pipefail

# 检查现有 Python、Shell 和工具配置；调用前须切到 M1 根目录并设置 PATH。
check_sources() {
  ruff check scripts tests quality
  ruff format --check scripts tests quality
  pyright --project pyrightconfig.json
  python3 quality/check_boundaries.py

  if [[ -d server/src ]]; then
    ruff check server/src server/tests
    ruff format --check server/src server/tests
    pyright --project server/pyrightconfig.json
  fi

  local shells=()
  mapfile -d '' shells < <(find scripts -type f -name '*.sh' -print0)
  shellcheck --shell=bash "${shells[@]}"
  shfmt -d -i 2 -ci "${shells[@]}"

  prettier --check '**/*.{json,yaml,yml,mjs,ts,vue,css,html}'
  eslint --config quality/eslint.config.mjs quality --max-warnings 0

  # Helm 模板不是普通 YAML；此处跳过，渲染后再检查。
  local file
  while IFS= read -r -d '' file; do
    yamllint -s -c quality/yamllint.yaml "$file"
  done < <(find deploy quality \
    -type d \( -name node_modules -o -name templates \) -prune -o \
    -type f \( -name '*.yaml' -o -name '*.yml' \) -print0)
}

# 校验固定 Chart 缓存，再离线渲染四个部署入口；参数为 M1 根目录。
# M1_CHART_CACHE 可覆盖缓存位置，不自动下载或更换版本。
check_charts() {
  local root="$1"
  local cache=${M1_CHART_CACHE:-"$root/../../.tmp/e01-02/charts"}
  if [[ ! -f "$cache/temporal-1.8.0.tgz" || ! -f "$cache/nats-2.15.2.tgz" ]]; then
    echo 'Missing upstream chart archives; see deploy/environments/local-wsl/components.md' >&2
    return 1
  fi

  printf '%s  %s\n' \
    e65b454d620129f3d7da2c16611a7f754e2d89b20b7a135dc5f0916a062f3a9e "$cache/temporal-1.8.0.tgz" \
    a7e829a5cfa06591b02534ee76e2acaaab8fd0bfd2e8a4785629e8df5a6b8427 "$cache/nats-2.15.2.tgz" |
    sha256sum -c -

  # 使用不存在的 context，防止离线检查误用操作者的默认集群。
  local helm_command=(
    helm --kubeconfig=/dev/null --kube-context=offline-check --namespace=deermind-check
  )
  local component
  local chart
  local extra=()
  for component in postgres temporal nats temporal-schema; do
    chart="deploy/helm/$component"
    case "$component" in
      temporal)
        chart="$cache/temporal-1.8.0.tgz"
        ;;
      nats)
        chart="$cache/nats-2.15.2.tgz"
        ;;
    esac

    extra=()
    if [[ "$component" == temporal-schema ]]; then
      extra=(--set runId=quality-check)
    fi

    "${helm_command[@]}" lint "$chart" \
      -f "deploy/environments/local-wsl/$component.values.yaml" "${extra[@]}"
    "${helm_command[@]}" template "deermind-$component" "$chart" \
      -f "deploy/environments/local-wsl/$component.values.yaml" \
      --no-hooks --skip-tests "${extra[@]}" |
      yamllint -s -d '{rules: {key-duplicates: enable}}' -
  done

  if [[ -d deploy/helm/application ]]; then
    "${helm_command[@]}" lint deploy/helm/application \
      -f deploy/environments/local-wsl/application.values.yaml
    "${helm_command[@]}" template deermind-app deploy/helm/application \
      -f deploy/environments/local-wsl/application.values.yaml |
      yamllint -s -d '{rules: {key-duplicates: enable}}' -
  fi
}

# 存在客户端时必须有真实 tsconfig；不能静默跳过已建立的应用。
check_client() {
  if [[ ! -d clients ]]; then
    echo 'PENDING: 正式客户端未建立；Vue/TypeScript规则由正反样例检验。'
    return 0
  fi
  if [[ ! -f clients/tsconfig.json ]]; then
    echo 'clients/tsconfig.json is required' >&2
    return 1
  fi

  eslint --config quality/eslint.config.mjs clients --max-warnings 0
  vue-tsc --project clients/tsconfig.json
}

# 统一工作目录与工具入口，然后依次执行检查；不提供自动修复模式。
main() {
  if (($# != 0)); then
    echo 'Usage: check.sh (read-only; no arguments)' >&2
    return 1
  fi

  local root
  root=$(cd "$(dirname "$0")/.." && pwd)
  cd "$root"
  export PATH="$root/quality/node_modules/.bin:$PATH"

  local tool
  for tool in python3 node ruff pyright prettier eslint vue-tsc shellcheck shfmt yamllint helm; do
    if ! command -v "$tool" >/dev/null; then
      echo "Missing tool: $tool (see quality/README.md)" >&2
      return 1
    fi
  done

  check_sources
  check_charts "$root"
  check_client
  echo 'PASS: 现有源码与配置检查完成；待接入项不计为产品验证通过。'
}

main "$@"
