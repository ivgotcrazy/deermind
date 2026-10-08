# DeerMind Architecture Spike

唯一现行结论见[Architecture Validation Report](../../doc/system-design/spike/DeerMind_Architecture_Validation_Report_v0.1.md)。当前为Development Phase 1 System Design；内部Phase 5 Spike已按原§17.1完成，交付Phase 6证据评审。E1/X5原范围仍未决，Gate E/F仍OPEN。不自动继续准确率调优，尚未进入Architecture Validation Build。

## 实现与证据

`foundation/`保存共享内存运行骨架，`protocols/`保存显式版本化协议，`fixtures/`保存输入、判据和预算，`review-packages/`保存离线准备及冻结清单，`runs/`保存每次真实执行，`reports/`保存机器评审和历史证据。历史Markdown只用于追溯；旧主报告位置是转向入口。

本轮入口为`run_spike_completion.py`、`run_completion_cognition.py`、`run_completion_direct.py`和`run_completion_x5_context.py`。各自有`prepare`和`run`模式；现有输出目录均拒绝覆盖。它们记录已执行批次，不表示可以直接重开或默认采用实验Profile。新配置应另立版本、预算和输出目录。

本地机制检查从仓库根目录执行：

```powershell
$env:PYTHONPATH='src/spike;src/spike/tests'
python -X utf8 -m unittest test_completion_direct test_boundary test_content_projection test_turn_closure test_semantic_review test_security_campaign test_policy_v2 -q
```

本轮79项针对性检查结果见[测试记录](reports/completion-mechanical-tests-20261008.json)，真实模型结果及作者复核见[统一机器评估](reports/spike-completion-assessment-20261008.json)。脚本或mock检查不证明真实模型质量。

## 配置和历史复现

API凭据由仓库根`.env`或环境变量中的`DEERMIND_LLM_API_KEY`提供；配置名见根`.env.example`。不要把密钥写入日志。真实批次固定实际endpoint、模型、采样、输入/输出上限、调用预算和超时，并只在调用前读取配置。

[原综合Spike设计](../../doc/system-design/spike/DeerMind_Consolidated_Architecture_Spike_Design_v0.1.md)仍为原验收依据，[历史文档](../../doc/system-design/spike/archive/README.md)已经归档。每个旧manifest的路径/hash属于当时的版本；源文件变更或迁移后，按[台账](reports/validation-progress-v1.json)中的historical_source_revisions及保存的原文字节核验，不用当前源码冒充旧运行版本。旧结果文件不重写，不复用旧响应充当新调用。

代码用于有限架构验证；脚本Evaluation、受信fixture grants、模拟显示、线性历史扫描和深拷贝不自动成为生产实现。生产系统的持久化、恢复、身份设施、真实Evaluation质量、独立语义评估和性能在后续正式阶段验证。
