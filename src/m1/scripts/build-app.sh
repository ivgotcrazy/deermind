#!/usr/bin/env bash
# 构建 wheel、双入口前端和 OCI 镜像；不连接集群、不推送镜像、不启动守护进程。
# 用法：build-app.sh SERVER_IMAGE CLIENT_IMAGE OUTPUT_DIRECTORY
# 需要已运行的 BuildKit（BUILDKIT_HOST）、uv、npm、buildctl 和已安装的前端依赖。
set -euo pipefail

main() {
  if (($# != 3)) || [[ -z "$1" || -z "$2" || -z "$3" ]]; then
    echo 'Usage: build-app.sh SERVER_IMAGE CLIENT_IMAGE OUTPUT_DIRECTORY' >&2
    return 1
  fi
  : "${BUILDKIT_HOST:?Explicit BuildKit address required}"
  local server_image="$1"
  local client_image="$2"
  local output
  mkdir -p "$3"
  output=$(cd "$3" && pwd)
  local root
  root=$(cd "$(dirname "$0")/.." && pwd)
  cd "$root"

  # 锁文件发生漂移则停止；不能在构建中悄悄更新依赖版本。
  mkdir -p .artifacts/build
  uv build --project server --wheel
  uv export --project server --locked --no-dev --no-emit-project \
    --format requirements-txt --output-file .artifacts/build/requirements.txt
  npm --prefix clients run build

  # 仅向构建器传入产物；避免扫描仓库、依赖缓存或带入本机文件。
  local context
  context=$(mktemp -d /tmp/deermind-build.XXXXXXXX)
  # 此处固定 mktemp 返回的路径；退出时局部变量已经离开作用域。
  # shellcheck disable=SC2064
  trap "rm -rf -- '$context'" EXIT
  mkdir -p "$context/wheels"
  cp server/dist/*.whl "$context/wheels/"
  cp .artifacts/build/requirements.txt "$context/requirements.txt"
  cp -R clients/dist "$context/dist"

  # 串行构建以控制本机峰值；本地导入或远程仓库交付由部署步骤负责。
  local component
  local image
  for component in server client; do
    image="$server_image"
    if [[ "$component" == client ]]; then
      image="$client_image"
    fi
    buildctl build --frontend dockerfile.v0 \
      --local context="$context" --local dockerfile="$root/deploy/images" \
      --opt "filename=$component.Dockerfile" \
      --opt "build-arg:HTTP_PROXY=${HTTP_PROXY:-}" \
      --opt "build-arg:HTTPS_PROXY=${HTTPS_PROXY:-}" \
      --output "type=oci,name=$image,dest=$output/$component.tar"
  done
}

main "$@"
