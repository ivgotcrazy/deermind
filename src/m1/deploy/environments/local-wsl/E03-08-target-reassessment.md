# E03-08 目标采用与重评

Worker 接收 `LearningTargetApplied`。读取固定采用，生成目标计算及结果事实，保存时检查空间当前目标依据。迟到结果保留历史。重复投递复用原结果。

[集群数据库回归](../../../tests/migrations/test_domain.py)先交付新版事实，再交付旧版及重复通知，检查新结果保持当前、旧结果留痕。课程改名与方法要求变更的比较见 [浏览器复验](../../../tests/browser/evaluation/course-spaces.cjs)。
