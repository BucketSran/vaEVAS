# benchmark v4：PFD 低有效复位修复素材

材料身份：[本地 v4 资料入口](../../reference/README.md)，原迁入快照 `7b5616dc52195ec275ec6d21c71d7763613702cd`。本轮按 vaEVAS `c81b8c7c17535bd5267f5bc1d7abe80b3087a9a9` 中的保存字节核对。来源组登记为 `v4-family-249`，属于人工注错素材，未发现可将其称为真实用户工程 bug 的记录。

2026-10-10 重读 [r53 题面](../../reference/v4/release/benchmarkv4-r53/tasks/1249-pfd-active-low-reset-bugfix/public/instruction.md)、[starter](../../reference/v4/release/benchmarkv4-r53/tasks/1249-pfd-active-low-reset-bugfix/public/buggy_bundle/pfd_active_low_reset.va)、[参考实现](../../reference/v4/release/benchmarkv4-r53/tasks/1249-pfd-active-low-reset-bugfix/evaluator/solution/pfd_active_low_reset.va)、[checker profile](../../reference/v4/release/benchmarkv4-r53/tasks/1249-pfd-active-low-reset-bugfix/evaluator/checker_profile.json)、[derivation manifest](../../reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2/249-pfd-active-low-reset/evaluator/derivation_manifest.json)，重新对起始文件与两个 mutation 计算 SHA-256。

## 确认的故障与身份差异

接口为 ref、fb、rstb、up、down。starter 对 ref/fb 上升沿置位并延迟互复位，完全没有使用 rstb，缺少公开的 tr 参数且写死平滑时间。它不满足公开的外部低有效复位要求。

| 文件身份 | SHA-256 |
| --- | --- |
| r53 starter | `41023069a21d873c92ddd874ec7600edf1417db35f8a0cda642a0aa046b6415c` |
| neg_002_ignore_reset | `41023069a21d873c92ddd874ec7600edf1417db35f8a0cda642a0aa046b6415c` |
| manifest 所指 neg_005_metric_scale_low | `56a0405a932acad9f314815a4e5ee9c0da7bc0c63d7c2d6c0aac29b578d6fee7` |

这证实起始字节与故障标签不一致，尚未解释差异形成过程。新卡按实际字节记录“忽略复位”，不继承错误标签或历史认证。profile 声明 private checker backend，不是已经取得和审计的评分代码。

## 改编条件

允许整体重写，保留必要接口与公开行为。需要重写重复的机器生成规格，定义同时事件、复位释放、挂起互复位的取消及参数边界，独立用输入边沿事件队列生成期望。旧包的语言限制、工具链和通过标签不自动沿用。

本地持有不代表已有整包公开分发授权；这里只登记与链接素材，不复制原代码进入新题。许可、真实 starter 身份和独立 checker 均需核验后再决定是否实现。详细历史分析见 [修复研究](../../research/diagnosis-repair.md#2-v4-1249pfd-的外部低有效复位)。
