# E01-08 按范围重建

> **版本**：v0.1<br>
> **日期**：2026-11-22<br>
> **进度**：见[实施计划](../../../../../doc/mvp/m1/engineering/Delivery_Plan.md#13-e01基础运行)

[公共运行合同](../../../../../doc/mvp/m1/engineering/System_Foundation_Design.md#26-历史补读实时接续与重建) · [原职责补修记录](E01-08-ownership.md)

## 1. 操作

在维护窗口暂停业务写入。使用维护账号、已配置的数据库及文件存储连接，按获准范围执行。每个`--scope`指定一个账号 UUID，可重复传入；每批覆盖所选账号的全部事实及必要关联。共享监护人的来源账号缺失时，重新审批包含该依赖的范围。重建持有全局事件表的共享锁和迁移维护锁，同一时刻只执行一批。

```bash
deermind-rebuild run \
  --rebuild-id "$REBUILD_ID" --generation "$GENERATION" \
  --scope "$ACCOUNT_ID" \
  --operator "$OPERATOR" --authorization "$AUTHORIZATION_REF" \
  --maintenance-confirmed

deermind-rebuild status \
  --rebuild-id "$REBUILD_ID" \
  --operator "$OPERATOR" --authorization "$AUTHORIZATION_REF" \
  --maintenance-confirmed
```

每批预分配唯一重建 UUID，并选用该投影器尚未使用的大于 1 的代次。成功时，正式五表替换、在线应用收据、扫描覆盖位置及成功记录共同提交。每次重建使用本批隔离副本，成功时删除副本，失败时随事务回滚。其他已提交批次继续有效。

处理中断或提交回执丢失时，先用原 UUID 查结果。查到 `completed` 即已提交；在数据库正常可访问、原事务已结束的前提下，查到 `failed` 或确定无记录时，修复问题后用新 UUID 和代次从头重建该批。相同参数重发已登记批次只返回旧结果。历史未完成记录可供查阅。

## 2. 自检

验证证据见 `src/m1/.artifacts/e01-08-single-run-20261122/`。

| 检查 | 结果 | 证据 |
| :--- | :--- | :--- |
| PostgreSQL 重建 | 19 项通过，覆盖分批隔离、成功记录写入失败、中断回滚、从头重做、权限与历史记录查询 | `rebuild-tests.txt` |
| 账号与登录回归 | 14 项通过，含重建后保留当前资料、不恢复旧密码或已注销会话 | `account-tests.txt`、`account-terminal-test.txt` |
| 工程检查 | `scripts/check.sh` 通过，含严格类型、依赖边界、OpenAPI、Vue 和部署配置 | `native-check.txt` |
| 本地测试 | 58 项通过，含质量、部署目标和后端单元测试 | `native-local-tests.txt` |
| 文档 | 版本与新增链接一致，旧命令只保留在历史交付记录 | `docs-check.json` |

首次测试连接转发中断，改为直连测试集群的 PostgreSQL 服务后重跑通过。账号命令的终端用例初次等待输入超时，在独立终端会话重跑通过。上述测试只写随机测试库。

工程检查在 WSL 本地磁盘的源码副本运行，重建代码和测试逐字节核对一致。原有迁移、维护记录字段及结果事件结构保留。实时投影的收据和扫描进度仍按原合同维护。

## 3. 修订记录

| 版本 | 日期 | 修改 |
| :--- | :--- | :--- |
| v0.1 | 2026-11-22 | 登记单批重建命令、失败重做及验证 |
