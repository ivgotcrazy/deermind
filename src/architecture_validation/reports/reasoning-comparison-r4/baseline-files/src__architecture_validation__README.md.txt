# DeerMind Architecture Validation Build

这是 Development Phase 2 的单进程参考实现。它运行 Event → Observation → Evidence → Belief → Policy → 受控浏览器展示确认，并保存来源、精确引用、候选、语义校验、owner 提交、失效依赖及恢复记录。真实生成和审查使用 DeepSeek；`scripted` 模式只用于工程机制检查，不证明模型能力。

G2仍为HOLD。最近完整验收R2为6/6段完成预定路径、14/24轮内容可用，EVAL-02/04未满足。随后R3专项未达到完整复验准入，实验语义Profile已撤回；当前默认恢复R2语义规则，仅保留确定性的审查总评汇总修复，最终81项离线检查通过。这个当前组合没有新的完整G2成绩。详见[统一Validation Report §7](../../doc/system-design/build/DeerMind_Architecture_Validation_Build_Validation_Report_v0.3.md#7-r3专项修复失败边界与默认配置回退)。

## 一键启动与人工复测

在仓库根目录运行（PowerShell 或终端均可，无需手工激活环境）：

```powershell
.\deermind.cmd start
```

脚本自动启动后台服务、创建题目和会话，并用默认浏览器打开前端。默认使用 `.env` 中已配置的真实模型；首次启动自动创建 `.venv`、安装锁定依赖，需要本机安装 Python 3.11+ 并能访问依赖源。以后启动复用环境。前端由同一个服务提供，不需要另外安装或启动前端工程，也不需要安装 Playwright 浏览器。

```powershell
.\deermind.cmd status
.\deermind.cmd stop
```

`status` 查看运行状态、日志位置及人工预算用量；`stop` 停止该实例并保留数据库。再次 `start` 恢复最近会话，页面刷新也会恢复已提交输入和已确认的展示记录。需要重新开始时使用 `-NewSession`，不必清理数据库。

| 参数 | 用途与默认值 |
| --- | --- |
| `-Mode real` / `-Mode scripted` | 真实模型 / 固定响应离线演示；新实例默认 real，既有实例沿用原模式 |
| `-Name demo` | 独立数据实例名，默认 default；切换模式需换 Name，防止混入固定评价数据 |
| `-Port 8766` | 新实例默认8765；端口占用会明确报错，不停止其他进程 |
| `-NewSession` | 新建会话；仍保留同实例历史和累计预算 |
| `-Quantity 8 -Total 56 -Target 13 -Noun 绘画本` | 设置题目，并新建会话；未指定字段沿用上次题目，新实例默认6份练习本42元、求15份价格 |
| `-NoBrowser` | 只启动服务，控制台输出可打开的页面链接 |
| `-MaxCalls 200 -MaxCost 10` | 人工实例累计HTTP尝试与人民币费用上限；默认200次、10元，任一先到即停；修改需先 stop，用量不清零 |

离线试用示例（与默认真实实例隔离）：

```powershell
.\deermind.cmd start -Mode scripted -Name offline -Port 8766
.\deermind.cmd stop -Name offline
```

另开题目或会话：

```powershell
.\deermind.cmd start -NewSession
.\deermind.cmd start -Name example -Port 8767 -Quantity 8 -Total 56 -Target 13
```

启动入口为 [deermind.cmd](../../deermind.cmd)，参数与环境准备见 [PowerShell脚本](../../scripts/deermind.ps1)。也可使用 `deermind.cmd setup` 仅准备依赖。服务只监听 `127.0.0.1`；人工运行数据、`server.log`、本机控制凭据及预算账本位于 `src/architecture_validation/runs/manual/<Name>/`，不进入Git。控制台页面链接包含本机学习者访问令牌，应在本机使用；API key不写入链接或控制文件。

真实模式读取仓库 `.env` 或环境变量中的 `DEERMIND_LLM_API_KEY`、`DEERMIND_LLM_BASE_URL`、`DEERMIND_LLM_MODEL`。新建空实例启动、打开页面及查看状态均不调用模型；旧实例若仍有已提交的排队输入，重启会继续处理这些输入并产生相应调用。提交一次输入通常包含多个生成和审查调用，因此200次调用不等于200轮对话。手工等待不计作实验活跃时间，调用、tokens与费用仍按独立账本累计。人工复测不会写入已完成Build、R1或合同边界检查的实验账本，也不构成G2正式测量。

页面显示真实/离线模式及本轮失败状态。展示确认只代表受控客户端完成渲染，不代表学习者看见、理解或使用。中断按钮先停止当前处理，再停止通道并对账；停止服务时如有未确认展示，重启仍按既有恢复合同处理。

R1的独立账本、源码冻结、原始结果、评分和准入决定在 `reports/revalidation-r1/`。`revalidate dev1` 和 `dev2` 已执行，运行器拒绝覆盖；`revalidate formal` 因 `admission.json` 为 false 而拒绝发起。不要删除目录或改写准入标记来绕过停止条件。复核 R1 不需要 API key，可直接阅读 `assessment.json`、`quality-review.json` 和 `integrity.json`。

## 验证和证据

```powershell
$env:PYTHONPATH = 'src'
.venv\Scripts\python.exe -m pytest src/architecture_validation/tests -q
```

该命令不调用付费模型。24 条机制路径在 `test_mechanisms.py` 中；补充检查覆盖 schema、实际浏览器、精确 ID 映射、输入容量及中断后 worker 迟返。重启测试实际结束并重新启动服务进程。10、100、1000 节点测量是合成依赖图的事务与固定内容重建成本；真实 owner 重算由更正和规范激活路径单独验证。

`fixtures/holdout-v1.json` 保存六段会话、允许分支及四项 Evaluation 对照；`fixtures/probes-v1.json` 保存12个评审探针。测试期望不进入运行时生成上下文。`reports/` 保存冻结清单、来源快照、检查记录、调用账本和阶段结论；`runs/` 保存可重新生成的运行数据库、HTTP 模型记录、浏览器证据和本机控制文件。最终证据包排除密钥及本机控制凭据。

官方离线分词器及其来源 hash 保存在 `fixtures/`。本地估算加25%余量和512个封装 tokens；实际计量以供应商返回 usage 为准。费用保守采用核验时官方高峰、未命中缓存价格，具体依据见 `fixtures/pricing-v1.json`。请求材料超过本地输入预算时明确失败，不静默截断。

当前活动由后端绑定到正式Observation，历史活动在模型上下文标为activity_at_observation；Policy生成schema只允许当前获准动作。LLM仍负责语义判断和动作选择。

当前本地准入为32K估算tokens及200K封装字符；R1最高估算12,421，没有容量阻断。模型仅能选择当前Context列出的短ID，后端绑定精确引用；短编号在同一数据库保持稳定，历史来源不会随下一轮编号排列变化而误指。

## 实现边界

SQLite 是唯一持久化权威，日志不是恢复正式状态的替代品。记录追加后不可改写，head、有效性与队列是事务维护的投影。规范提交和激活分别记账，撤权及版本变化在提交、派发前检查；规范回退形成新的激活事实。有权管理者可以通过 `/admin/recompute` 请求基于原始 Event 的 owner 重算，不伪造新的学习者作答。

同一会话严格串行，本原型也只使用一个全局 worker。多进程部署、跨机恢复、多租户权限和生产级认证不在本次范围内。LLM负责意义判断；模型内容中值完全一致的重复JSON字段由程序合并，原文与位置审计保留，冲突值仍拒绝；按当前schema移除合同禁止的null/空字符串额外字段，并保留原文和位置审计，非空未知字段和已知字段不自动改写。结构、精确身份、权限、时序、依赖和实际提交/展示继续由程序检查。语义审查仍可能误放和误拒；审核 PASS 不构成语义正确的证明。

阶段结果以 `doc/system-design/build/` 下的统一 Build Validation Report 为准；方案中的通过门槛和既有 Spike 否定结论不会因参考实现存在而自动满足。

R2已关闭，结果、逐轮评分和审计在`reports/g2-r2/assessment.json`与`quality-review.json`。`v2/source.zip`保存测量时源码，`v2-evidence.zip`保存运行材料；v1失败单独保留，不合并评分。`assess_g2.py`为运行后离线评分与核对程序，不调用模型，也拒绝覆盖已关闭结论。R2使用`holdout-r1.json`和`probes-r1.json`在当次freeze中保存的输入，不应把更早的`holdout-v1.json`当作本次成绩对应样本。

R3专项结果在`reports/evaluation-repair-r3/`，`admission.json`为false，正式阶段未执行；实验源码及默认配置回退分别留档。当前审查总评由程序对所有必需分项计算，模型原始总评另存审计；任一分项FAIL或UNRESOLVED、缺项、空理由及结构错误均不能提交。语义分项仍可能误判。不要删除冻结清单或改写admission来绕过已关闭批次的停止条件。
