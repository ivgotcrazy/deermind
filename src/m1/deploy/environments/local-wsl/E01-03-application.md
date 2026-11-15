# E01-03：应用可启动

[环境目录](README.md) · [实施计划 E01](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

E01-04起应用依赖数据库版本，当前升级顺序与复核见[数据库交付](E01-04-database.md)。本文保留E01-03的构建和验收记录；新环境不能跳过数据库迁移直接启动当前应用。

本增量交付一个Python安装包、独立API和共享Worker进程，以及Vue管理员／学生双入口。旧原型没有复制到正式源码。进度由[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md)维护，用户评审通过后才标完成。

## 1. 范围与制品

| 交付物 | 位置／用途 |
| :--- | :--- |
| 后端安装包 | `server/pyproject.toml`、`server/uv.lock`；Hatchling构建wheel，API与Worker共用 |
| 入口 | `deermind-api`、`deermind-worker`；分别启动，启动时检查配置和文件目录 |
| 双入口前端 | `clients/admin/`、`clients/student/`；共享组件与样式，没有业务假数据 |
| HTTP合同 | `contracts/generated/http/openapi.json`，由实际FastAPI代码离线导出 |
| 构建与部署 | `scripts/build-app.sh`、`deploy/images/`、`deploy/helm/application/` |
| 本地与集群测试 | `server/tests/test_startup.py`、`tests/deployment/test_application.py` |

API仅有存活和文件目录就绪检查。Worker仅注册`runtime.storage_probe`部署测试Workflow及其文件Activity；它不是AI Operation。没有实现登录、业务数据库、事件订阅、AI调用或业务恢复。

### 固定版本

| 项目 | 版本 |
| :--- | :--- |
| Python／uv／Hatchling | 3.14.10／0.13.8／1.33.0 |
| FastAPI／Uvicorn／Pydantic | 0.163.0／0.54.0／2.14.3 |
| Temporal Python SDK | 1.36.1 |
| Node／npm | 24.22.3／11.19.1 |
| Vue／TypeScript／Vite／Vue插件 | 3.5.43／5.9.3／7.3.7／6.0.9 |
| Nginx／BuildKit | 1.30.6／0.35.0 |

后端完整传递依赖及hash在`uv.lock`，前端在`package-lock.json`。检查工具仍使用独立quality清单；不把它们装进运行镜像。

| 制品 | SHA-256 |
| :--- | :--- |
| Python官方基础镜像索引 | `3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b` |
| Nginx官方基础镜像索引 | `901e593c95dc85f5a729f5765516321366ef4ac401821431d408897e95287d0a` |
| BuildKit Linux amd64压缩包 | `37b3befbed28fb72a44d72bf42362c268610386c42feafa27cb45ee0b531369c` |
| 本轮server镜像manifest（e01-03-r2） | `cb679b536f82b5ec6b5d235fd37f83845e4be8f5eec3ea7f50fa1b969cebe70e` |
| 本轮client镜像manifest（e01-03-r2） | `f29fedd26404196380cb822e1de2d48b26e061a3d625359a618b15add8aaccf8` |

基础镜像已在Dockerfile固定tag及digest。BuildKit来自[官方发布](https://github.com/moby/buildkit/releases/tag/v0.35.0)，下载后按发布元数据的digest核验；本机安装在`/root/.local/share/deermind-buildkit/`，不替换系统容器运行时。应用镜像tag不得复用于不同代码；本轮部署使用`e01-03-r2`。

## 2. 安装、检查与构建

在WSL的`src/m1`执行。`uv`、Node和检查工具须先按固定版本准备，命令不会安装系统服务。

```bash
export PATH="/root/.venvs/deermind-quality/bin:/root/.local/share/deermind-quality/node-v24.22.3-linux-x64/bin:$PATH"
uv sync --project server --locked
npm --prefix clients ci --ignore-scripts --no-audit --no-fund
bash scripts/check.sh
bash scripts/test.sh local
server/.venv/bin/python scripts/export-openapi.py --check
```

OpenAPI有变化时，显式执行不带`--check`的导出命令，再审阅差异。当前只导出健康检查，不预填尚未实现的业务路由。`check.sh`只读，不能在检查过程中修改被检查的脚本。

BuildKit按需启动，串行构建，完成后停止。以下为本机入口；代理仅在网络需要时按用户提供的地址设置在本次进程，不写进镜像或版本文件。

```bash
systemd-run --unit=deermind-buildkit --collect --property=MemoryMax=1G \
  --setenv=PATH=/root/.local/share/deermind-buildkit/bin:/usr/local/bin:/usr/bin:/bin \
  /root/.local/share/deermind-buildkit/bin/buildkitd \
  --root /var/lib/deermind-buildkit --addr unix:///run/deermind-buildkit.sock \
  --oci-worker=true \
  --oci-worker-binary /root/.local/share/deermind-buildkit/bin/buildkit-runc \
  --oci-max-parallelism=1 --containerd-worker=false

export PATH="/root/.local/share/deermind-buildkit/bin:$PATH"
export BUILDKIT_HOST=unix:///run/deermind-buildkit.sock
buildctl debug workers
bash scripts/build-app.sh deermind/server:e01-03-r2 deermind/client:e01-03-r2 \
  .artifacts/e01-03-20261115/images-r2
systemctl stop deermind-buildkit
```

`build-app.sh`不连接集群、不推送镜像；只将wheel、带hash的依赖清单和前端产物复制到临时构建目录。后端镜像从wheel安装，不挂载仓库源码。缺工具、锁文件不匹配或构建失败时返回非零。

## 3. 本机部署与访问

配置取`application.values.yaml`；API和Worker共享既有`deermind-files` PVC，并固定到同一节点。三个应用容器都非root运行、根文件系统只读，不挂载Kubernetes凭据。Nginx临时文件写`/tmp`，同源`/api/`转发到API，未知静态资源返回404。

先检查目标并导入镜像。`k3s ctr`只适用于本机；远程集群使用其镜像仓库并替换values中的镜像地址，不把镜像导入其他节点当作已完成远程部署。

```bash
bash scripts/check-target.sh --kubeconfig /root/.kube/deermind-m1.yaml \
  --context deermind-m1 --namespace deermind-m1
k3s ctr images import .artifacts/e01-03-20261115/images-r2/server.tar
k3s ctr images import .artifacts/e01-03-20261115/images-r2/client.tar
```

首次部署前显式创建Temporal应用namespace，保留执行历史30天。已有namespace只核对、不修改。初始化Job独立于服务启动；失败先查看Job日志，不自动删除或重试已有Job。

```bash
helm --kubeconfig=/root/.kube/deermind-m1.yaml --kube-context=deermind-m1 \
  --namespace=deermind-m1 upgrade --install deermind-app-init \
  deploy/helm/application -f deploy/environments/local-wsl/application.values.yaml \
  --set initializeNamespace=true --no-hooks --wait --wait-for-jobs --timeout 2m

bash scripts/deploy.sh --kubeconfig /root/.kube/deermind-m1.yaml \
  --context deermind-m1 --namespace deermind-m1 --release deermind-app \
  --chart deploy/helm/application \
  --values deploy/environments/local-wsl/application.values.yaml
```

后续应用版本只升级`deermind-app`，不重装已完成的初始化Job。改namespace时先审阅配置，再用新的初始化release显式创建。部署入口不改变默认context，不安装或升级PG、Temporal、NATS。

```bash
kubectl --kubeconfig=/root/.kube/deermind-m1.yaml --context=deermind-m1 \
  --namespace=deermind-m1 port-forward service/deermind-app-client 5184:8080 \
  --address=127.0.0.1
```

保持该终端运行，打开`http://127.0.0.1:5184/student/`或`/admin/`。本轮仅启动页，不代表学习或管理功能完成；不复用原型的5182端口。

Worker配置：namespace=`dm-local-wsl`，队列=`dm.local-wsl.application`，执行并发2／4；拉取各2、缓存8、线程池2／4按W02候选接线，随本增量评审。就绪文件只表示启动校验通过，持续执行能力仍须通过探测与后续运行机制验证。

## 4. 复核

```bash
export M1_KUBECONFIG=/root/.kube/deermind-m1.yaml
export M1_CONTEXT=deermind-m1 M1_NAMESPACE=deermind-m1
export M1_APPLICATION_RELEASE=deermind-app
bash scripts/test.sh application
```

实际运行五项：配置缺失时Chart拒绝、wheel安装与启动拒绝、页面及API转发、真实SDK重复注册拒绝、Worker执行与共享卷双向读写。测试只产生临时探测文件和一条技术Workflow历史，不写业务库。

API／Worker日志已按公共运行设计输出单行JSON到容器stdout。现场可用显式目标的`kubectl logs deployment/deermind-app-api`或`deermind-app-worker`查看；不新增采集器。原始测试输出在`src/m1/.artifacts/e01-03-20261115/`，截图在其`output/playwright/`，这些本机产物不提交Git。

## 5. 本轮自检与评审

运行编号`e01-03-20261115`，基线`d44684c`及本轮工作区改动。最终运行镜像为上表`e01-03-r2`，没有把基线提交冒充本轮源码提交。源码hash、原始输出和截图保存在本机证据目录。

| 检查 | 实际结果 | 证据 |
| :--- | :--- | :--- |
| 完整静态检查 | Python、严格类型、Vue/TS、Shell、格式、模块边界及5个Chart检查通过 | `check-accepted.txt` |
| 本地测试 | 7项检查器样例、4项目标／部署测试、5项后端测试全部通过，无跳过 | `local-final.txt` |
| 集群应用测试 | 5项全部通过；从wheel运行，真实SDK拒绝重复注册，任务执行和共享卷双向读写通过 | `application-final.txt` |
| 镜像构建 | 两份OCI镜像成功；基础镜像及运行依赖固定，临时构建目录退出时清理 | `build-r2.txt` |
| 重复部署 | 普通部署入口成功升级到revision 4；三个应用Pod均Ready，最终Pod无重启 | `redeploy.txt`、`cluster-final.txt` |
| 浏览器 | 两端实际加载、点击／键盘切换、820px窗口无横向溢出；截图人工查看 | `browser-review.txt`、`output/playwright/` |
| 最后局部复核 | 补齐公开端口导入允许项、固定构建临时路径后，Ruff／Shell检查和模块边界测试通过；OpenAPI快照一致 | `final-delta.txt` |
| 文档 | 相关版本、交付范围及新增链接已核对；保留各文档原换行风格 | 文档diff、链接核对 |

人工review逐项检查了：设置缺失和依赖故障不能报就绪；文件探测只操作UUID测试文件；Workflow不做文件I/O；API和Worker共用安装包；前端共享层不导入两端业务；构建上下文不包含源码、凭据或缓存；部署不修改默认集群、不升级基础组件；测试失败不改成跳过。未发现本增量剩余阻断项。

过程问题如实保留：

- BuildKit首次未发现runc，已显式指定OCI worker及工具路径。构建上下文改为产物暂存目录；退出清理的局部变量问题已修复，最终构建退出码为0。
- Nginx首次因默认临时目录与只读根目录冲突退出，已将临时目录统一放到`/tmp`。临时配置修复造成的Helm字段归属冲突已在本轮应用资源上一次性协调；普通部署入口没有增加强制接管选项，随后不带强制参数的重复部署成功。
- 首轮SDK单元测试错误使用懒连接，已改为本地拒绝检查及真实集群注册检查。首轮完整检查期间改动脚本、检查器超时及一处YAML换行格式失败均保留；最终冻结代码后串行复测通过，没有扩大测试时限或移除断言。
- 浏览器首次缺favicon产生404，现配置明确返回204；页面脚本没有运行异常。后台转发重启命令被自动策略拒绝后，浏览器验证使用前台临时转发完成。

本轮未验证100人容量、长时间稳定性、远程集群实际部署或业务恢复。E01-02曾出现的NATS握手异常没有在本轮修复或宣称消失。下一项为E01-04数据库schema与迁移，须在本增量评审后推进。
