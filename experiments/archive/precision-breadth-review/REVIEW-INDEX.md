# 最终审查索引

这份索引说明“审了哪个版本、结论可以复用到哪里、还缺什么”。静态模型审查不等于执行测试、Spectre 对齐或最终矩阵通过；旧失败、未知、上下文错误与原报告均保留。数据和文档已经固定；发布链接的替换不改变科学结论。

本目录只保存选定报告、规格与决策日志，文件身份见 MANIFEST.json。原 prompts、完整流、原始波形与商业手册留在本地；未归档的相对路径也指原本地任务目录。文件哈希不使这些材料成为公开下载。


## 规格与 checker 数学

- 实现前规格：[Astra](review/astra-spec-math.md)、[GLM原调用收据](review/glm-spec-math/receipt.json)。Astra 基线 `4448253a15ea8cf566d88e62be54c3819060648a`；仅 SPEC/INTERFACE/inventory 与引用合同。原 GLM spec调用900秒超时、无terminal result、review_valid=false，不能计作完整规格审查；后续完整checker/delta审单列。F20 ordinary phase 不能用圆周距离、F16 单位/准入及同方程要求等先前问题，须沿实现审查确认，不能由规格意见直接称实现完成。
- 当前规格快照：[SPEC.md](SPEC.md) SHA `9b4b0cb0f6ebf9c101277145e8a13ee29bd9f3834a8037cc852e819ae4892bb4`；[INTERFACE.md](INTERFACE.md) SHA `ac9e7e5b33610d8d925aa3775370f047c6bb9c2cc1065797484f654c9d7d18dd`。44 组/71 变体/四后端852槽包含 Probe，不能删分母或令 Probe 正式通过。
- Foundation/composition 最终实现：[foundation follow-up](review/astra-foundation-followup.md)、[composition follow-up](review/astra-composition-followup.md)、[GLM checker/reference](review/glm-v2-checker-reference-final/review.md)，GLM 精确受审 `5fce77d6926794331a5beebfa16151cf18485e06`；Astra foundation固定 `fe60e306..1469bda0`，composition固定 `c7c27d79..cb244cb9`；[source identity](review/glm-v2-checker-reference-final/source-identity.json) 逐文件限定覆盖。
- 最后数学 delta：[Astra](review/astra-final-breadth-delta.md)、[GLM](review/glm-v2-delta-final/review.md)，GLM `5fce77d6..4288e9225e8d201a70a589156ed2811c6f975d48`。transition 错缩目标包围已由 `ce67a7524476dd8a70b935e0ccff4c4fbd0d205f` 修复；Astra Fraction 独立40176答案包围控制通过，不是科学模拟或全域证明。
- rational planner、原 operand event 边界、F20 真相邻点、G2手写锚在该 delta 静态范围闭合。D1 冗余 rounded aliases 为信息项；G1/EC21 动态 timer 假设保留可见限制。后续未改字节可复用原数学审，改变输入/数学实现须另定位。
- 冻结执行 runner/checker 基线 `5f73f5016bb44808549ddfbf9b685bc192f2b2d7` 的 [standards](review/standards-5f73.md)、[spec](review/spec-5f73.md) 保留；后续源码、正式重分析身份不可冒充此基线。

## EVAS 三项生产修复

1. **F07 共享自身状态更新。** `55e5f197157bacd2b2cfd282f2547f6ea6b918ab` 扩至有限非零 affine 系数，仍保留结构依赖/同刻 writer 冲突、逐句 local 状态与回滚。见 [Astra](review/astra-latest-and-event-array.md)、[GLM production](review/glm-v2-production-final/review.md)：GLM 比较 `4448253a..cec42221e0b52e95689c8de77c61445a65bb184b`，相关文件与独立提交相同；不代表一般多 writer 顺序仲裁。
2. **F14 实际输入导数。** `13b2f8228dbd82988248b3beea1c8c5a1599ca69` 保留物理 PWL slope；[实际 GLM F14](review/glm-v2-numerical-f14-final/review.md) 固定 `81a8615bf376c4aa562538af79532996a2b76312` 的 source snapshot。审查范围是原输入/严格 strobe 与导数证书，不可扩为任意不连续 DDT 支持。
3. **F20 严格 phase/sine。** 原 `0c7004d54c5d1985437aaf0af8427514e0c51312` / `81a8615b` 数学审 [GLM F20](review/glm-v2-numerical-f20-final/review.md) 保留，但 eager 性能/完成回归使其未作为最终部署方案；旧 timeout、Taylor-only red 不抹掉。最终 `c2542e5b499060db1f047fdb4e9f5de32ced58da` 仅 ordinary voltage refusal 后完整 lazy 重算，见 [Astra c254](review/astra-c2542e5b-and-0e1f91d1.md)。

GLM lazy F1 确认同帧已认证输出与恢复 ordinary nominal 可不同；完整调用者复审未发现当前可达错误接受/拒绝，将原 medium 降为条件性文档限制。见 [Astra裁决](review/astra-glm-lazy-F1-adjudication.md)、[GLM最终裁决](review/glm-v2-lazy-f1-complete-callers/final-adjudication-and-history-calendar.md)。固定 production c254 / test `fd79b59fa90070ef536c812d5b0aa20d918c5a11`；`6986959e`、`a8446fcc` 公共负控与 `519d5e28` 说明补条件。phase/sin-phase guard、连续依赖仍拒；未来放开须重审。discarded_trials=1 不能独立归因 lazy retry；首次截断 transient 的 GLM 复审不作完整闭合依据。

Astra 在固定 c254 独立 Rust238通过/1ignored、生命周期1项、F14/F20原请求数学复核及VCO完成证据，范围见其报告。它们不代替正式 v3 全213条及实际 Spectre 配对验收。

## 运行与取证工具

- 冻结 runner：[实际 GLM](review/glm-v2-runner-native-final/review.md)，受审 `5f73f5016bb44808549ddfbf9b685bc192f2b2d7`，含 deferred analysis、身份/原生行/设置控制。原四候选意见按 [GLM索引](review/glm-v2-index.md) 限作用域，未证实际 false-qualified 或删分母；不覆盖新最终 raw。
- 重分析/聚合 D1–D3：[Astra](review/astra-c2542e5b-and-0e1f91d1.md)、[实际 GLM](review/glm-v2-tool-hardening-final/review.md)，`6f2f9dfc..0e1f91d116820f74a560b21d5a20b9c25b69e71e` 已闭合。不可把工具审当新 aggregate 科学通过。
- Open adapter：[Astra d844](review/astra-open-adapter-d844b795.md)、[实际 GLM disposition](review/glm-v2-open-adapter-final-d844/disposition.md)，固定 `d844b79584b8a42d361e340ce918658f3609d9a9`，源码SHA `0a0ee2537eb5aee65d77d0c07f80b1f4fcc2c8b4b809540309f3bdc9244db1fb`。旧 grammar/env/scope P2、JSON F5、argv N1均经红绿和独立负控关闭；repr/放宽cap/stop建议未采纳，原门槛未变。
- Caller：[Astra](review/astra-open-caller-be30.md)、[实际 GLM](review/glm-v2-open-caller-f125/disposition.md)，`0e1f91d1..f12598d2d0636ebb5329761afaa865c1cb03650f` 含be30；source/原数学结果不变、独立seal、外部exact审批与各轴合取已审。真实无proof analysis保持 unknown，合成正控不构成真实批准。
- 最终元数据工具：[Astra](review/astra-final-tools-aa7-d9f2.md)、[实际 GLM](review/glm-v2-curation-final-tools-aa-d9/disposition.md)，aggregate `aa7cb13d2c9a08c95aca24d10250060249f5c4fc`，curator SHA `d9f20088929e7fe1e5ef18ddfa77fbb5ca69b4b8a0c3f21d0b6d255f3b0e773b`；READY SHA `848707ce3ce67750dbdb134455cedcbd8a47cb5f821d799d14cc4d00e2c3c787`。cards信任入口、来源字段、integrator独立轴通过固定静态审；低健壮性建议保留，未证当前放行错误。
- NG quoted exporter：[Astra](review/astra-ng-quoted-export-inputs.md)、[实际 GLM](review/glm-v2-open-ngquote-current/review.md)。供审 inputs.py SHA `aa2f181b2332d04a3c95b3ae9b6920abf653ac8a28f5b94546d7c6c2911d4426`，与 `d6ac5ae3` 对应blob一致；只改九保留节点wrdata引用。最初实际探针是四名称/一槽/186行，最终 F03 四名称的全36槽已执行，五名称仍仅源码+本地测试；d844 bare grammar仍保守拒quoted，未授新资格。

**七份真实 proof 全部未批准。** [固定4137包](open-evidence-proof-draft/REVIEW_PACKAGE_MANIFEST.json) SHA `4137f4a482c1c6a1a48a0ac4333a820be1cf671e0cf6410e4b873a80b0b5cfa8`；[Astra最终裁决](review/astra-open-claims-4137-final.md) 与 [GLM机制摘要](review/glm-v2-open-origin-summary.md)。Astra已拒当前包批准；[actual GLM 的4137受限边界审](review/glm-v2-open-claims-4137-boundaries/disposition.md)同样不批准任何 proof。任何 reviews字段或 self标记不替代root外部exactSHA批准。

固定安装/mapping子链不等于逐run资格。当前d844 runtime不合取startup；因此不能给含runtime具体mapping而startup未闭的4137包补reviews并批准，避免夸大runtime轴。历史可变/work无法复原就保持证据不足；新absence不证明旧absence。NG helper/出口子链、GN `__va_idt`/方法选择仅按已得材料partial归档，不递归无限抓静态依赖。GN method=trap设置不保证每步梯形：实际filter在首history缺失时强制Euler；动态器件/加载/覆盖仍需适用范围证据。

## 数据与元数据

- 完整v2基线 PUBLIC-RECEIPT SHA `7e8e65e7efb74149e25f49436f0d4a2d1fa8d4e6db6c451ac7b156edf1dd99b5`：四后端各213槽、132组格；[Astra完整852审](review/astra-curator-e483-final-852.md)、[独立原字节审计](review/independent-complete-v2-baseline-byte-audit-v1.json)。本地程序 roundtrip、hash/bytes、计数职责与模型阅读分开。
- GLM四分区收到全receipt字段，但 **没有独立重算852数值/全部hash/全部理由**。EVAS、Spectre、NG三份prompt混用了52ea中间curator与e483旧receipt，只可限为数据阅读，不能验收工具revision。见 [EVAS disposition](review/glm-v2-curation-852-column-evas/disposition.md)、[Spectre](review/glm-v2-curation-852-scoped-spectre/disposition.md)、[NG](review/glm-v2-curation-852-scoped-openvaf_r_ngspice/disposition.md)。Spectre49P对应164非pass，报告154已纠正，原文保留。
- [GN disposition](review/glm-v2-curation-852-scoped-gnucap_modelgen/disposition.md) 使用正确固定e483/c016且READY核验，无finding，但模型仍未逐字段重算，不能转授其余三后端或最终矩阵。
- Curator旧F1 explanatory scope/limit、F2组校验、F3分轴理由在e483修复；[e483 R1 cards seal](review/glm-v2-curation-e483-tool/disposition.md) 由后续aa7/d9固定工具审闭合。真实原数据身份未被证明污染；旧schema没有integrator不是去重丢字段。
- 新无proof external aggregate与852旧基线的final/numeric/behavior/evidence/native/runtime等逐槽相同；NG EC16/17/18三档共9槽configuration保守降unknown，legacy仍qualified，不能写“所有资格轴不变”。Astra独立d9 preview收据 SHA `6ba65cacca44828d0790b586accbded9b890f6bf9f28bbdefd6199d5d5de33e3` 是审查产物，非root正式final。

## 最终执行、数据与交付审查

EVAS v3 的全部213槽使用生产源码 `519d5e28` 和同一个 Linux release 内核，见 [Astra v3证据审](review/astra-final-v3-evidence.md)。五项严格请求从拒绝变为波形可得，但仍为证据不足。EC21 Q3 从89.8498 s完成变为90.0165 s超时，按原90 s限制保留失败。[只读诊断](review/ec21-q3-runtime-diagnosis.md)没有证明原因，不能称数值修复完成或断言代码性能回退。

[实际 GLM v3审](review/glm-v2-final-v3-evas-213-scoped/review.md)读取全部213精简记录及六项变化证据，但误记EC17 numeric并给出F1；[固定六项增量裁决](review/glm-v2-final-v3-six-axes-adjudication/review.md)明确撤回F1，计数迁移闭合。原报告24组scope误述也保留并由disposition更正。模型没有独立运行仿真或重算全部波形。

最终收据 `762a6a6bfe754ea773b28f6b511206d1a14c3dfe9bd7361260de4e66a90ca2ab` 固定852槽，包含全213个EVAS新执行和全36个ngspice F03导出复测；其余603槽的科学状态和原执行身份不变。154完整通过、510证据不足、132执行失败、50数值超差、6行为不符。数字不是语言覆盖率或性能排名。

NG36全部取得波形；原冻结配置读取器拒绝引号格式，全部分析保留 `ReadbackError`，数值资格未知。dc-1三档实际导出输入为0.5，而请求为其下邻值；不能直接归为比较器缺陷。[独立36槽对照](review/ng-f03-fixed36-before-after-v1.json)和[原字节审计](review/independent-final-v3-ng-f03-byte-audit-v2.json)保留同DUT/OSDI与原失败。

[Astra最终交付审](review/astra-final-delivery.md)确认44行表格全部✓与收据一致，三个仓库JSON为原件逐字节拷贝。root的[文档检查](review/root-doc-check.log)另确认92行历史结果/设置保留。审核中一次Python导入遗漏 `-B`，在封存目录生成3个额外pyc。它们已按哈希和原路径保留到隔离目录，未改原成员；恢复后的17段、22213个原始文件核验通过。这不是仿真运行或成绩修改。

[实际 GLM 最后文档/NG36审](review/glm-v2-final-ng36-docs/review.md)确认运行、未知和计数，但在压缩表引用上误读后端列，提出六条表格错配意见。[平铺固定单元的实际裁决](review/glm-v2-final-flat-cells-adjudication/review.md)排除了这些错配，重要限制仍保留。EC23/EC03 的“拒绝”措辞据此写清，科学状态不变。首次报告的空工作区 diff 不能算完整四导航文件审查，最终改用 `dd33eb9e..6e1f4897` 的非空历史 diff 补审。没有重复模型调用来重算全852结果。

截至最后封存，共48次实际CLI调用、45个已报告模型轮次；50个terminal turns包含零模型context错误。已知报告费用32.570116美元，历史超时未报告部分仍未知。完整返回与正确范围审查分开记录，不把48次调用说成48份有效审查。

## 决策日志与覆盖边界

[decisions.tsv](decisions.tsv) 按时间追加，错误路径和结论通过后续行更正。早期[日志审计](review/astra-decision-trail-audit.md)、[中途审计](review/astra-decision-trail-final-preflight.md)只覆盖各自声明的前缀。最终交付审与[发布前缀审](review/astra-publication-preflight.md)覆盖至第53条，复用原前缀并核后续可访问证据，没有声称获得完整原始对话。最后一条审查收尾及后续发布操作由root依实际工具结果核对，没有将其冒称为更早审查已覆盖。

GLM实际调用 provenance 见[调用索引](review/glm-v2-index.md)。混用上下文、截断、超时、错误finding及纠正均保留；未完整返回的调用不算审查通过。重要数值和checker修改已有Astra与实际GLM报告，模型静态审查不代替实际后端数据。

仍未完成的工程义务见 #96/#119 与支持总表；#131保持不动。本次交付可审查PR，不批准合并或任何未完成的open-backend机制证明。原始大文件与临时工作区仍保留，未退休。最终固定历史链接、提交/推送与CI属于发布操作，不能被上述数值审查提前证明。
