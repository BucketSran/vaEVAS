# 最终整理器 e483 与完整 v2 基线收据独立审查

结论：本轮增量没有发现 P1/P2。新 compact 收据完整保留 852 槽、528 组格及分层状态，没有删失败、把 unknown 改 pass 或把 852 已收集误当 852 通过。它仍是 **v2 完整执行基线**，不是待完成的新 EVAS v3 或 quoted F03 复验结论，也未取得新的 open proof 资格。

固定 revision：ignored 整理器 SHA `e4830d7c87bcf9e2ecf341d4196317c91eb19a74775622ac7b78ca2ee69e94ef`；测试 SHA `d3a4d03a99d6ed16b32cc0864b6cdb76b4666587e8de012d373f62db15faf4ae`。收据为 `public-receipt-complete-v2-baseline-852-v1/PUBLIC-RECEIPT.json`，SHA `7e8e65e7efb74149e25f49436f0d4a2d1fa8d4e6db6c451ac7b156edf1dd99b5`，1,171,958 bytes。此为脚本内容身份，不误称 git commit。

本次复用此前 597 原始取证审计，重点独立检查新 delta。现有19项校准独立通过，日志 `astra-curator-e483-tests.log`。源码新增 gate 确实保留 scope/limit、区分相同文字的 behavior/evidence layer、核 528 唯一组格及 mandatory variants/每轴聚合、核 manifest 声明 bytes/必要 digest，输出目录不能嵌入任一封存输入树。先验证再创建输出；没有把投影器变成重算科学结论的 checker。

独立脚本 `astra-curator-e483-audit.py` 与结构化结果 `.json`：

- compact、aggregate、failure inventory 三个 manifest 的成员 hash/bytes 全通过；收据记录的 aggregate/failure/cards/script hash 与实际文件相符。
- 852 个唯一键严格等于 71 模型 × 4 后端 × Q1/Q2/Q3。所有八轴、selected_batch、误差上下界/预算、原 RESULT/kernel/tool/source 身份、请求/实际设置及 binding 状态逐项等于 sealed aggregate。INPUT_IDENTITY hash 也逐槽相等。
- 528 组格所有字段等于 aggregate；每组 mandatory variant 集合和状态映射与冻结 cards、852 个槽对应。71 模型/44组/每后端213槽不变；Probe 无完整 pass。
- 每后端每层重新 Counter 与 compact counts 相等。核 1,726 条显式 behavior/evidence 理由没有跨层丢失；434 个来自 failure inventory 的 scope/limit 字段逐项保留。
- 不重复旧597原 raw 核查；对新增255槽全部实际 RESULT 与 INPUT_IDENTITY 文件 hash 逐项核验。旧/新之间没有用“最好结果”重新挑槽；此次投影逐项继承 sealed aggregate 的 selected_batch。selection 本身的政策/未来替换需最终矩阵审查单独确认。

本基线 final 轴：EVAS 105 pass / 77 evidence_insufficient / 31 execution_failed；Spectre 49 / 160 / 3，另 numerical_error 1；NG 0 pass / 82 evidence_insufficient / 117 execution_failed / 14 numerical_error；Gnucap 0 pass / 151 evidence_insufficient / 21 execution_failed / 35 numerical_error / 6 behavior_error。以上只说明封存 v2 基线投影一致，不给错误作未经证实的语言归因。

availability 仍明确 raw 与 analysis local-only，源码与历史 binary/raw 可取得性分开。单槽数值通过并不能掩盖 config/native/runtime unknown。停止处末次 timer 工程要求、输入精确性和方法证明的限制通过分层理由继续保留。没有修改 tracked 文件、canonical trail、原 receipt 或任何原执行。

完整 v3、quoted F03 新36槽、正式 open proof 和最终替换 selection 仍须另做增量；本审查不替代那些尚未完成的实际证据。
