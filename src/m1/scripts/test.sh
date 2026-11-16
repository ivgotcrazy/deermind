#!/usr/bin/env bash
# 显式选择本地、只读目标或组件测试，不把集群写操作混入默认本地验证。
# 用法：test.sh local|target|components|application|database|facts|files|reads|rebuild|auth|usage|receipts|delivery；环境变量见 quality/README.md。
# 任一测试失败即非零退出；不安装依赖、不自动更换目标。
set -euo pipefail

# 按选择的分组执行；环境变量只在真实测试分支要求提供。
main() {
  local root
  root=$(cd "$(dirname "$0")/.." && pwd)
  cd "$root"
  export PATH="$root/quality/node_modules/.bin:$PATH"

  if (($# != 1)); then
    echo 'Usage: test.sh local|target|components|application|database|facts|files|reads|rebuild|auth|usage|receipts|delivery' >&2
    return 1
  fi

  case "$1" in
    local)
      # 本地组只使用替身；不因机器上存在 kubeconfig 而自动跑集群测试。
      python3 -m unittest discover -s tests/quality -v
      python3 tests/deployment/test_target.py TargetTests
      if [[ -d server/tests ]]; then
        server/.venv/bin/python -m unittest discover -s server/tests -v
      fi
      ;;
    target | components | application | database | facts | files | reads | rebuild | auth | usage | receipts | delivery)
      # 真实测试必须显式指定目标；components 还会重启测试 release。
      : "${M1_KUBECONFIG:?Explicit test kubeconfig required}"
      : "${M1_CONTEXT:?Explicit test context required}"
      : "${M1_NAMESPACE:?Explicit test namespace required}"
      if [[ "$1" == target ]]; then
        python3 tests/deployment/test_target.py
      elif [[ "$1" == database || "$1" == facts || "$1" == files || "$1" == reads || "$1" == rebuild || "$1" == auth || "$1" == usage || "$1" == receipts || "$1" == delivery ]]; then
        : "${M1_POSTGRES_RELEASE:?Explicit PostgreSQL release required}"
        : "${M1_DATABASE_SECRET:?Explicit database secret name required}"
        : "${M1_TEST_NODE:?Explicit test node required}"
        : "${M1_DATABASE_TEST_IMAGE:?Built server image required}"
        if [[ "$1" == delivery ]]; then
          : "${M1_TEST_NATS_ADDRESS:?Explicit NATS test address required}"
          : "${M1_MESSAGING_SECRET:?Explicit NATS secret required}"
        fi
        python3 scripts/test-database.py "$1"
      elif [[ "$1" == application ]]; then
        : "${M1_APPLICATION_RELEASE:?Explicit application release required}"
        : "${M1_AUTH_TEST_ORIGIN:?Explicit approved authentication origin required}"
        M1_APPLICATION_TESTS=1 python3 tests/deployment/test_application.py
      else
        : "${M1_TEST_NODE:?Explicit test node required}"
        : "${M1_CHART_CACHE:?Verified upstream chart cache required}"
        M1_COMPONENT_TESTS=1 python3 tests/deployment/test_components.py
      fi
      ;;
    *)
      echo "Unknown test group: $1" >&2
      exit 1
      ;;
  esac
}

main "$@"
