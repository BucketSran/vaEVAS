# 最终外部证据元数据工具增量审查

**没有发现 P1/P2；可放行这两个固定工具增量用于新的本地收据。** 此结论不批准七份真实 mechanism draft，不提升数值或资格，不替换原 guarded selection，也不构成 merge 授权。

## 固定范围

- core：`aa7cb13d2c9a08c95aca24d10250060249f5c4fc` 相对父提交；仅 precision_breadth_aggregate.py/test。独立使用干净 precision-core checkout。
- ignored curator：旧 `e4830d7c87bcf9e2ecf341d4196317c91eb19a74775622ac7b78ca2ee69e94ef` → 固定副本 `review/curation-external-fixed/curate_public_receipt.py` SHA `d9f20088929e7fe1e5ef18ddfa77fbb5ca69b4b8a0c3f21d0b6d255f3b0e773b`；测试 SHA `2f3a21a28edca565ad01c4c8ef2c8927fe4d91fb434d59d97bea3f42726d46b8`。
- 复用此前 e483/完整 v2 852 科学审计与 f125 caller、d844 adapter 审查；本轮只审新来源字段、cards 信任入口和对应负控。无远端、无 simulator、无 tracked 写入。

## 审查结果

aggregate 在读官方 cards 时要求 cards.json 属于原输入 MANIFEST 且实际 hash 匹配，再把 official_cards_sha256 写入新收据。外部 identity 必须既在完整 ANALYSIS_MANIFEST 中，又由 ANALYSIS_IDENTITY 精确绑定；adapter/proof/sealed attachments 各自 hash 必须属于该 seal。proof metadata 保留指定原字段，不把 claims/reviews 文本当成批准结果。精确批准摘要、实际摘要和缺批准 null 分开保存。

逐槽 integrator 是独立来源轴，实际 record 与 external integrator 不一致会拒绝；external configuration 若完整 qualified，必须 identity/config/integrator 都 qualified。非 open 后端是 not_applicable，旧 open 缺证是 unknown。legacy 配置 readback 被单独保留；requested 来自 profile binding，actual 来自原 legacy configuration，不因组合资格对象缺 actual 字段而丢失读回。

curator 对有 external identity 的 analysis 独立检查完整文件库存、hash/bytes、symlink/路径、ANALYSIS_IDENTITY/OPEN_EVIDENCE_IDENTITY 与原 proof metadata/附件的关系；去重表只去重相同信息，不删槽。公开内容保留外部 proof、逐槽外部 qualification、legacy configuration、设置来源及 integrator evidence，counts 和 groups 增加独立 integrator 轴。原 final/数值/行为/证据逻辑未改。

cards 不再是任意 CLI 文件：新 aggregate 的已封存 official_cards_sha256 是主信任入口；旧 aggregate 兼容需显式 expected digest，同时核已有 sealed analysis 的 OFFICIAL_CARDS 与逐槽 source hash。这个 expected digest 必须来自既有冻结/批准身份，不是把待测文件现算 hash 当成外部审批。新 cards source/probe 元数据不可独立替换。

## 独立验证

- core 全部 breadth support 34 项通过（19 aggregate + 15 caller），日志 `astra-aggregate-aa7-tests.log`。
- 固定 curator 28 项通过，日志 `astra-curator-d9f2-tests.log`。
- `astra-final-tools-delta-probes.py/.json` 保留7个独立增量控制/对照：实际852基线复制 cards，仅替换一模型 source，旧 e483 CLI 接受并创建输出；d9f2 在原冻结 digest 下拒绝且未创建输出。真实无proof external analysis 是正控；单改批准 proof digest、proof claims metadata 或 adapter hash 均拒绝。新 aggregate 对照与配置降级另单列。
- 新 actual aggregate `official-draft-complete-v2-external-no-proof-v1/OFFICIAL-DRAFT.json` SHA `8298a85d604eee70d5d3506ff69f1469c594ca9a563f8f93c592903aca43edf0`，对旧 guarded 852逐槽核 final/numeric/behavior/evidence/native/runtime/执行、误差界/预算、原 RESULT/kernel/source、selected_batch 全等。

**不能写“全部资格轴不变”：** NG EC16/EC17/EC18 的 Q1/Q2/Q3 共9槽，组合 configuration 从 qualified 降为 unknown，因为新 caller 合取无 proof；其 legacy_configuration.status 仍为 qualified。这是预期保守行为，没有分数或资格提升。最初独立对照把 config 也要求全等而报这9槽，随后查明原因并将这个真实差异单列，没有放宽最终成绩的相等检查。

为验证真实 compact 接线，本 reviewer 用固定 d9f2 在上述 actual aggregate/failure inventory 上生成独立目录 `review/astra-curator-d9f2-actual-preview`，收据 SHA `6ba65cacca44828d0790b586accbded9b890f6bf9f28bbdefd6199d5d5de33e3`，1,540,742 bytes，852槽。所有九轴、integrator evidence、三张逐槽去重表与 aggregate 逐项相同；唯一外部 proof metadata 对象也原样相同、仍未批准。counts 独立重计一致。该 preview 是审查产物，不替代 root 的正式输出和 guarded 基线。

## 放行边界

允许以固定工具生成新的公开来源收据；后续正式收据仍须记录其具体 SHA，并与本次 preview 或同一 sealed aggregate 比对。七份真实 proof draft 继续不批准，历史 startup/native/actual-method 缺口照旧。声明元数据只说明来源和范围，不是新的数值证明。最终 EVAS v3、quoted F03新36槽以及正式机制补件仍要另审，旧失败、未知和852分母保留。
