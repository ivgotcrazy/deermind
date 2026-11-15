# E01-02：基础组件部署

仅部署 PostgreSQL、Temporal、NATS JetStream 和共享文件卷。应用、前端、业务表、业务消息订阅及 AI 均不在本次范围。版本与制品 SHA-256 见[清单](../../components/manifest.yaml)。

编程规范整改及本轮回归见[自检记录](../../../quality/README.md#本轮自检)。本轮不改变组件版本、资源配额或部署目标。

## 配置与边界

| 组件 | 本次部署 |
| :--- | :--- |
| PostgreSQL | 17.12，1副本，8Gi PVC；80连接，shared_buffers=128MB |
| Temporal | 1.32.2，官方Chart 1.8.0；frontend/history/matching/内部worker各1副本 |
| NATS | 2.15.3，官方Chart 2.15.2；1副本，2Gi PVC，JetStream文件上限1Gi |
| 文件卷 | `deermind-files`，8Gi，local-path，同节点读写 |
| Helm | 4.3.2 |

六个常驻容器内存limit合计2816Mi；实际用量另看测量。全部服务仅ClusterIP，不对宿主暴露数据库或管理端口。测试时port-forward只绑定127.0.0.1。

三个数据库分别为`deermind`、`temporal`、`temporal_visibility`。业务迁移与运行账号分开；Temporal两个账号各访问自己的库。业务库仍为空，Temporal表由官方工具建立。NATS当前token仅用于组件接线；业务发布/订阅权限与stream在E01-12接线，不把同一个维护token直接交给所有业务调用方。

## 部署命令

在新WSL内执行。每次明确指定目标，其他集群复制并调整环境values中的节点、StorageClass、Secret名称等，不能直接套用本机节点。脚本不搬迁数据，不修改默认context，不自动卸载失败release或删除PVC。

```bash
set -euo pipefail
cd /mnt/d/code/deermind/deermind/src/m1
kcfg=/root/.kube/deermind-m1.yaml
ctx=deermind-m1
ns=deermind-m1
envdir=deploy/environments/local-wsl
cache=/mnt/d/code/deermind/deermind/.tmp/e01-02/charts
k=(kubectl --kubeconfig="$kcfg" --context="$ctx" --namespace="$ns")
h=(helm --kubeconfig="$kcfg" --kube-context="$ctx" --namespace="$ns")
target=(--kubeconfig "$kcfg" --context "$ctx" --namespace "$ns")
bash scripts/check-target.sh "${target[@]}"
```

### 1. 工具、Chart与镜像

Helm从清单的官方地址下载，核对SHA-256后解包，将`linux-amd64/helm`安装到`/usr/local/bin/helm`。不使用安装脚本自动追随最新版。

```bash
mkdir -p "$cache"
"${h[@]}" pull temporal --repo https://temporalio.github.io/helm-charts --version 1.8.0 --destination "$cache"
"${h[@]}" pull nats --repo https://nats-io.github.io/k8s/helm/charts --version 2.15.2 --destination "$cache"
printf '%s  %s\n' \
  e65b454d620129f3d7da2c16611a7f754e2d89b20b7a135dc5f0916a062f3a9e "$cache/temporal-1.8.0.tgz" \
  a7e829a5cfa06591b02534ee76e2acaaab8fd0bfd2e8a4785629e8df5a6b8427 "$cache/nats-2.15.2.tgz" | sha256sum -c -
```

下载受阻时，仅为下载进程设置用户提供的`HTTP_PROXY`与`HTTPS_PROXY`。本机镜像已按清单digest导入containerd。重新导入时，使用`k3s ctr images pull --local --platform linux/amd64 <清单完整镜像引用>`；`--local`使下载进程使用当前代理，而不是让后台daemon忽略它。用标签预拉的镜像须核对digest后，为完整的`repo:tag@sha256:…`引用增加containerd标签。values使用digest且`IfNotPresent`；远程节点应能直接访问相同镜像或完成同样的受控导入。

### 2. 凭据

本机凭据在WSL的`/root/.config/deermind-m1/credentials/`，目录0700、文件0600；不输出或提交。已有数据必须沿用对应凭据，丢失时停止并恢复凭据，不能重生成密码后假装初始化成功。

新空环境可用以下方式创建文件；文件存在时保留原值：

```bash
python3 - <<'PY'
from pathlib import Path
import os, secrets
root = Path('/root/.config/deermind-m1/credentials')
root.mkdir(parents=True, exist_ok=True, mode=0o700)
names = ['deermind-postgres-' + key for key in
         ('postgres-password', 'migration-password', 'app-password', 'temporal-password', 'visibility-password')]
names.append('deermind-nats-token')
for name in names:
    path = root / name
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as out:
            out.write(secrets.token_hex(24))
PY
```

仅在目标Secret不存在且确认是新空环境时执行以下创建命令；重复部署跳过本步。命令使用create，不覆盖已有Secret：

```bash
creds=/root/.config/deermind-m1/credentials
args=()
for key in postgres-password migration-password app-password temporal-password visibility-password; do
  args+=(--from-file="$key=$creds/deermind-postgres-$key")
done
"${k[@]}" create secret generic deermind-postgres "${args[@]}"
"${k[@]}" create secret generic deermind-nats --from-file="token=$creds/deermind-nats-token"
```

### 3. PG及显式初始化

```bash
bash scripts/deploy.sh "${target[@]}" --release deermind-postgres \
  --chart deploy/helm/postgres --values "$envdir/postgres.values.yaml"
run_id=$(date -u +%Y%m%d%H%M%S)
"${h[@]}" template deermind-postgres deploy/helm/postgres -f "$envdir/postgres.values.yaml" \
  --set bootstrap.enabled=true --set-string bootstrap.runId="$run_id" | "${k[@]}" create -f -
"${k[@]}" wait --for=condition=Complete "job/deermind-postgres-init-$run_id" --timeout=120s
```

初始化Job只补缺少的账号和库、核对所有权并限制权限；不重置已有密码、不建业务表。数据库所有权或角色权限不符合预期时失败。不要通过删库“修复”失败。

### 4. Temporal Schema与服务

```bash
"${h[@]}" template deermind-schema deploy/helm/temporal-schema \
  -f "$envdir/temporal-schema.values.yaml" --set-string runId="$run_id" | "${k[@]}" create -f -
"${k[@]}" wait --for=condition=Complete "job/deermind-schema-$run_id" --timeout=180s
bash scripts/deploy.sh "${target[@]}" --release deermind-temporal \
  --chart "$cache/temporal-1.8.0.tgz" --values "$envdir/temporal.values.yaml"
bash scripts/deploy.sh "${target[@]}" --release deermind-nats \
  --chart "$cache/nats-2.15.2.tgz" --values "$envdir/nats.values.yaml"
"${k[@]}" apply -f "$envdir/files-pvc.yaml"
```

脚本关闭Helm hooks，Schema只由上述官方工具Job建立。Temporal不另装数据库、Web或常驻管理工具；NATS不安装额外监控和管理Pod。`local-path`按首个使用者绑定共享卷，尚无使用者时PVC为Pending是预期状态。

## 复核与评审证据

测试会重启上述三个release，只在隔离测试集群执行。临时创建测试表、测试stream、工作记录及文件；结束后清理测试表/stream/文件/Pod，Temporal测试执行终止后按已定30天策略保留历史。它不验证应用Worker执行。

```bash
M1_COMPONENT_TESTS=1 M1_KUBECONFIG="$kcfg" M1_CONTEXT="$ctx" M1_NAMESPACE="$ns" \
M1_TEST_NODE=deermind-m1 M1_CHART_CACHE="$cache" \
python3 tests/deployment/test_components.py
```

E01-02进度只在[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)维护。自检结果见下节，原始输出保存在`src/m1/.artifacts/e01-02-20261115/`，不含Secret正文。

## 自检记录

2026-11-15，基线提交`f8ef91f`上的本次工作区改动。运行编号`e01-02-20261115`；源文件hash随原始证据保留，未将基线提交冒充本次实现提交。

| 检查 | 实际结果 | 原始证据 |
| :--- | :--- | :--- |
| 配置与边界 | 三个release部署就绪；6个常驻容器，无附带数据库、管理界面或监控平台；镜像按digest固定 | `cluster-final.txt`、三个`*-rendered.yaml` |
| PG | 重启后测试数据仍在；错误密码、跨库访问、运行账号建表被拒；业务库0表，Temporal执行/检索库40/3表 | `component-tests.txt`、`cluster-final.txt` |
| NATS | 真实发布并取得确认，重启后可读取原消息；错误token被拒；测试stream已清理 | `component-tests.txt` |
| Temporal | 创建测试工作，四个服务重启后工作仍为Running；测试后主动终止。未安装应用Worker，不声称业务执行已验证 | `component-tests.txt`、`temporal-bounded-test.txt` |
| 文件卷 | 两个同节点Pod挂同一PVC，写入后另一Pod可读；写入Pod退出后仍可读，临时文件和Pod已清理 | `component-tests.txt` |
| 错误配置 | 缺镜像配置渲染失败；缺Secret的Pod不能Ready；部署入口5组非法输入全部非零退出 | `component-tests.txt`、`deploy-input-checks.txt` |
| 重复初始化 | PG再次初始化、Temporal同版Schema再次执行均成功；无删库或重置密码 | `postgres-repeat.txt`、`schema-repeat.txt` |
| 回归 | 组件5项全部通过；为CLI加执行时限后单独复验Temporal通过；E01-01目标检查4项全部通过，无跳过 | 三份`*-tests.txt`及`temporal-bounded-test.txt` |

最后一次采样6个容器合计约315Mi内存、WSL可用约4691Mi；这是空载附近的瞬时值，不是容量或长期稳定性结论。共享文件卷和两个数据卷均Bound。未验证远程集群、整机故障、整套备份恢复或100人容量。

首次部署修复两项实际问题：PG初始化的`DO $$`被Kubernetes参数展开，已改为命名分隔符；Temporal缺`connectProtocol: tcp`导致启动失败，补齐后部署及测试通过。镜像下载使用调用进程代理和`ctr --local`，并补齐digest引用。失败记录保留，失败初始化Job清理，不删除数据卷。

PG重启后Temporal短时出现数据库重连错误，恢复后功能检查通过；Pod Ready不代替实际查询验证。Temporal旧表差异已补入数据库字典，未私改官方DDL。

当前提交用户评审，未开始E01-03。
