# Astra 固定提交增量审查

2026-10-12。独立审查生产 c2542e5b499060db1f047fdb4e9f5de32ced58da 相对 81a8615b，及支持工具 0e1f91d116820f74a560b21d5a20b9c25b69e71e 相对 6f2f9dfc。追加读取并运行纯生命周期测试 fd79b59fa90070ef536c812d5b0aa20d918c5a11。结论：在本次固定代码、独立重放与可访问证据范围内，无可复现 P1/P2 findings。未运行远端、未修改生产、未合并；这不是完整行为对齐或合并授权。

## 数值与状态生命周期

c254 先运行原 ordinary 流程，只有 waveform_accuracy 且消息来自同刻 forward-error 检查、观察窗为点、events 与 fired_roots 同为空时，才从同一 accepted frame 完整重跑。其他错误、非点窗及真实事件/root 不进入该新增精化。IdtMod 默认恢复普通相位旧 gate，原 wrap 证书仍保留；精化仅在 disposable operator clone 启用。第二次从 advance/evaluation 开始重建代表值、区间、settlement、reset/观察闭包、future history 和 replay；不是只收窄包围。settlement_bounds 对新的代表值使用原 absolute/relative 预算。成功返回前关闭 flag；失败没有将 candidate 提交到 accepted。原源缺失、生成输入误差、proof budget 限制继续 fallback。

独立 git archive 的 726 个 evas 文件逐字匹配 c254，然后离线 debug build。用于原请求的内核 SHA256 为 c6c60ae5647ea702981cc93a630c4b09e95f430221c0c43b6e9a3b61efdf7cf7。完整 Rust：238 passed、1 ignored、0 failed。随后只在审查快照将 transient.rs 替换为固定 fd79 的纯测试版本，独立运行新增生命周期测试：1 passed。它覆盖 ordinary 明确失败→完整重试成功、返回普通 bounds、点事件与 fired-root 禁精化、非点拒绝、过严预算失败、原 frame 不变、同 frame 改正预算重试匹配 clean，以及继续下一时刻。没有宣称独立运行 fd79 全套 Rust。

从原 collected request.json、dut.va、requested_times.json 逐项重放，保持原 stop、max_step、vabstol、reltol 与全部 strobe：

| 原请求 | 点数 | 独立数学结果 |
| --- | ---: | --- |
| F14-base--Q3 | 107 | Fraction 定义的 y 最大误差 0，原预算通过 |
| F20-base--Q3 | 172 | 100 位 Decimal/Fraction 定义的 y 最大误差 1.524081900975693e-15 V，最大误差/原预算 0.1278059933，所有 phase 在半开 [0,1)，原预算通过 |

本次 lazy 数值与早前 eager 的 5.446157e-16 V 不同，不能沿用旧较小值。严格原点集与真实 wrap 邻点未删除。独立数据及所有原输入哈希保存于 `astra-fixed-c2542e5b/independent_joint_probe.json` 和两份 response.json。

独立原 `test_original_vco_source_independent_phase_and_sine` 通过，16 点、max_step=2e-10、stop=8e-6；本次并行构建/测试期间约 40.508 s，不能据此报告一般性能比率。它验证此前超时的原请求可以完成。worker 另有交替 release 5+5 次均完成的日志；此处不将其升级为独立性能测量。旧 eager 超时、Taylor-only red、原 F14/F20 拒绝均保留。

## 支持工具 D1–D3

固定工具快照 38 个 support 文件逐字匹配 0e1f；补齐同提交 validation 依赖后 22 项校准通过。D1 raw_work 检查 runs 容器、候选及祖先符号链接，并拒绝解析到 runs 外或 runs 本身；独立负控 ../outside、../../escape、嵌套 symlink/child、点目录、绝对外部路径均拒绝。D2 PROFILE_BINDINGS 必须列入冻结 MANIFEST 且哈希匹配；独立缺项/错误哈希负控均拒绝。D3 单 lane 缺失绑定保持 original execution 与 numerical assessment，同时将 configuration 和资格降为 unknown/evidence_insufficient；没有把数字失败或原失败改为通过。

用固定 0e1f CLI 和当前固定 selection/catalog 重建 `official-draft-evas-complete-guarded-v1`：整个 OFFICIAL-DRAFT.json 与已交付该 artifact 完全相同。仍为 852 个唯一 backend/variant/Q 槽、44 逻辑组、528 个 backend/group/Q 行；105 pass、46 execution_failed、8 numerical_error、693 evidence_insufficient。48 个 probe 槽没有 PASS。这是该 draft 的记录，不是新 c254 远端全矩阵成绩。

工具哈希：aggregate c016771e651b6d6cfa6c03dc553a91f084710b0388e8754ff3c35c1052971bf3；reanalysis 280842f911dd46cb769017b73254f6ab1819441f609994222320d1479fc57896。重建 OFFICIAL-DRAFT SHA256 13ea9687f3c775903555894269a9d2de87591b8306a83cc120e9c03aa7a0be28。独立遍历全部 291 个已选择实际槽，逐槽检查原 RESULT 状态、RESULT 哈希及表中列出的全部 raw_artifact_hashes，全部一致。CLI 还验证六条 lane 的完整 manifest；原 raw 与旧结果未修改。详见 `astra-fixed-delta-verification.json`、`astra-aggregate-0e1f91d1/`。

测试准备中有两次调用错误：首次工具校准缺少 archive 中 validation 依赖而 ModuleNotFoundError；首次聚合误写 inputs 为 input 而 FileNotFoundError。补齐固定依赖和使用实际 inputs 路径后以上检查通过；这两次不算代码缺陷或有效科学失败，也不掩盖原模拟器失败。

## 限制与保留项

未验证新内核的 Linux/Spectre 最终实际矩阵，F07 full callback bracket 的 unknown 不因本次修改变成通过。EC03/EC13 stop 回调的附加工程合同解释沿用独立补充报告：旧 final=4 判据及成绩保留，单纯末次窗口跨 stop 的未观测不能称语言缺陷。此前 GLM 失败调用、unknown、历史分母及原始冻结均须继续保存。本报告只覆盖可访问的固定代码与证据，不声称 transcript 完整。
