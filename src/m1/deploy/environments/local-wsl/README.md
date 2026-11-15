# E01-01：本机测试集群

本机使用独立 `DeerMind-M1` WSL，安装在 `D:\wsl\DeerMind-M1`，不替换旧 Ubuntu，不修改 `.wslconfig`。这是低并发功能测试环境，尚未验证 100 人试用容量。

应用骨架的部署和复核见[E01-03](application.md)；基础组件见[E01-02](components.md)；下方保留E01-01的环境记录。

本轮编程规范整改与回归结果见[自检记录](../../../quality/README.md#本轮自检)，不覆盖下方原始交付记录。

## 已安装的环境

| 项目 | 值 |
| :--- | :--- |
| 系统 | Ubuntu 24.04.5 LTS / WSL 2，systemd 已启用 |
| 集群 | K3s `v1.37.2+k3s1`，单节点 `deermind-m1` |
| 工具 | 使用 K3s 自带 kubectl；Helm 4.3.2已在E01-02安装 |
| 命名空间 / context | `deermind-m1` / `deermind-m1` |
| 本机管理 kubeconfig | WSL 内 `/root/.kube/deermind-m1.yaml`，权限 0600 |
| 基础镜像 | 同版本官方离线包；保留默认 CoreDNS、local-path、Traefik、metrics-server |

凭据不放进仓库或测试报告。上述 kubeconfig 仅供本机部署管理，不是应用 Pod 的身份。镜像、安装脚本与二进制校验值见[版本清单](../../components/manifest.yaml)。

## 直接复核

PowerShell 进入新环境：

```powershell
wsl -d DeerMind-M1 -u root
```

随后在 WSL 执行：

```bash
cd /mnt/d/code/deermind/deermind/src/m1
bash scripts/check-target.sh \
  --kubeconfig /root/.kube/deermind-m1.yaml \
  --context deermind-m1 --namespace deermind-m1

M1_KUBECONFIG=/root/.kube/deermind-m1.yaml \
M1_CONTEXT=deermind-m1 M1_NAMESPACE=deermind-m1 \
python3 tests/deployment/test_target.py
```

检查脚本必须取得 API 就绪信息、命名空间和节点读取权限；不创建资源、不切换 context、不输出证书或 token。每次 kubectl 调用最多 15 秒，API 请求最多 10 秒；失败返回非零退出码。它只检查部署目标，不代替后续组件健康检查。

测试覆盖重复成功、缺少/重复参数、非法命名空间、不存在的 context/namespace、API 不可达、命名空间退出中及节点未就绪。真实测试只读集群，只在临时 kubeconfig 副本中制造错误地址，并核对原文件和默认配置不变。未传三个测试环境变量时，真实测试明确跳过，不能据此宣称集群验证通过。

其他集群直接换三个显式参数；脚本不要求目标使用 K3s。不得用 `kubectl config use-context` 改全局目标，也不自动新建远程 namespace。

## 从空环境安装

仅在尚无 `DeerMind-M1` 时执行；已有环境直接复核，不重装。

```powershell
wsl --install Ubuntu-24.04 --name DeerMind-M1 --location D:\wsl\DeerMind-M1 --no-launch --web-download
wsl -d DeerMind-M1 -u root
```

新环境确认 `ps -p 1 -o comm=` 输出 `systemd`。本次安装镜像已默认启用，不需要更改旧发行版或重启全部 WSL。

在可联网的宿主机下载本清单版本的 `k3s`、`sha256sum-amd64.txt`、`k3s-airgap-images-amd64.tar.zst` 及安装脚本。二进制和镜像均从[官方发布](https://github.com/k3s-io/k3s/releases/tag/v1.37.2%2Bk3s1)取得；脚本从清单地址取得。先比较官方校验文件与版本清单，再校验实际下载文件。脚本地址可能更新，hash 不同则停止并核对，不直接执行新脚本。

本机下载缓存放在仓库 `.tmp/e01-01/`。网络失败时可按用户提供的地址，为本次下载设置 `HTTPS_PROXY=http://192.168.1.186:7890`（需要 HTTP 时同设 `HTTP_PROXY`）；不修改全局代理。K3s 使用官方[离线安装方式](https://docs.k3s.io/installation/airgap)，无需第三方镜像源。

确认校验值后，在新 WSL 中执行：

```bash
set -e
cache=/mnt/d/code/deermind/deermind/.tmp/e01-01
cd "$cache"
sha256sum --check --ignore-missing sha256sum-amd64.txt
# install-k3s.sh 的 hash 另与 manifest.yaml 核对后再执行。
install -m 0755 k3s /usr/local/bin/k3s
install -d /var/lib/rancher/k3s/agent/images
install -m 0644 k3s-airgap-images-amd64.tar.zst /var/lib/rancher/k3s/agent/images/
INSTALL_K3S_SKIP_DOWNLOAD=true INSTALL_K3S_VERSION=v1.37.2+k3s1 \
  K3S_NODE_NAME=deermind-m1 sh install-k3s.sh

install -d -m 0700 /root/.kube
test ! -e /root/.kube/deermind-m1.yaml
install -m 0600 /etc/rancher/k3s/k3s.yaml /root/.kube/deermind-m1.yaml
kubectl --kubeconfig=/root/.kube/deermind-m1.yaml --context=default --namespace=default \
  config rename-context default deermind-m1
kubectl --kubeconfig=/root/.kube/deermind-m1.yaml --context=deermind-m1 --namespace=deermind-m1 \
  create namespace deermind-m1
```

安装会修改新发行版内的服务和网络；目标检查脚本没有这些权限操作。原始 `/etc/rancher/k3s/k3s.yaml` 不改名，默认 context 保持不变。不要把 WSL 虚拟磁盘显示的约 1TB 当作宿主实际可用空间。

## 运行与故障定位

进入新发行版时 systemd 启动 K3s。测试期间保留一个该发行版的终端；仅有 systemd 服务[不会阻止 WSL 自动退出](https://learn.microsoft.com/en-us/windows/wsl/systemd#how-does-enabling-systemd-affect-wsl-architecture)。本次已启动一个隐藏的保活进程，未增加开机自启任务。需要重新启动时可在 PowerShell 执行一次：

```powershell
Start-Process wsl.exe -ArgumentList '-d','DeerMind-M1','-u','root','--exec','sleep','infinity' -WindowStyle Hidden
```

检查 `systemctl status k3s` 与 `journalctl -u k3s`；组件问题用显式 kubeconfig/context/namespace 查询 Pod 和事件。离线镜像补齐只解决内置组件，后续应用镜像的联网/导入仍须在对应增量验证。

本机暂不使用时，在 PowerShell 执行 `wsl --terminate DeerMind-M1` 释放资源；恢复仍用前述进入命令。不要执行 `wsl --shutdown` 停掉旧环境，也不要执行 `--unregister` 删除发行版。

E01-01 原始自检输出保存在 `src/m1/.artifacts/e01-01-20261115/`；评审摘要由[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md)的 E01-01 状态引用。

## E01-01 自检记录

2026-11-15，运行编号 `e01-01-20261115`。基线提交 `c932737`；本次交付为其上的工作区改动，尚未提交 Git。源文件 hash 随原始证据保存，不把基线提交冒充本次实现提交。

| 检查 | 实际结果 | 证据 |
| :--- | :--- | :--- |
| 文件完整性 | K3s 二进制和离线镜像均通过官方 SHA-256 核对；安装脚本 hash 已登记 | `manifest.yaml`、下载记录 |
| 脚本与目标测试 | Bash 语法检查通过；4 个测试方法全部通过，无跳过，包含真实集群测试 | `target-tests.txt` |
| 正确目标与重复检查 | 返回 PASS；原 kubeconfig、默认配置内容不变 | `target-tests.txt`、`cluster-final.txt` |
| 错误输入与错误目标 | 参数缺失/重复、context/namespace 不存在、不可达地址均返回非零；节点不就绪等状态以受控替身验证 | `target-tests.txt` |
| 集群组件 | 节点 Ready；CoreDNS、local-path、metrics-server、Traefik 均可用；安装 Job 已完成 | `cluster-final.txt` |
| 工作负载与 DNS | 测试 Pod 成功运行，解析 `kubernetes.default.svc.cluster.local` 为 `10.43.0.1`；随后清理该测试 Pod | `cluster-initial.txt`、`cluster-ready.txt` |
| 本机运行条件 | WSL 总内存约 7.6GiB；本次检查可用约 4.9GiB，Linux 已用磁盘约 2.7GiB | `cluster-final.txt` |

初次启动遇到两项环境问题：Docker Hub 访问失败，已导入官方同版离线镜像；WSL 空闲退出导致组件重启，已保持一个 WSL 前台进程。最后两次检查服务启动时间相同、组件均已恢复；历史重启次数保留，不包装成从未失败。

本次未验证远程集群、长期稳定性、100 人容量或应用组件；真实用例只针对本机新集群。local-path 已就绪，同卷读写留到 E01-02。当前交付等待用户评审，不能据此标记 E01 或 M1 已完成。
