# 最终交付独立审查（固定 762a 收据与 52 条决策）

最终结论：已对固定最终 852 收据、新 249 槽实际证据、603 个复用槽的科学不变性、44 组人类可读表和 52 条 canonical 决策完成本轮范围内审查，未发现新的 P1/P2 或错误授予 ✓。可按下列精确身份交付；这不批准真实 open proof、不等于全量行为对齐或 merge 授权。原始大文件仍只在本地，固定历史审查链接尚待归档后补入。未启动远端、修改 tracked 文件或改写原 trail。

## 实际增量与证据边界

EVAS 复用 `astra-final-v3-evidence.md` 全 213 独立审查：186 waveform、17 execution_failed、10 timeout；最终 105 P / 81 I / 27 X；numeric 108 P / 96 unknown / 9 insufficient / 0 N。五个 Q3 从拒绝转为波形仍全部 I，EC21 Q3 的超时回退没有被净改善掩盖。`astra-ec21-runtime-identities.json` 与 worker 已落盘的 `ec21-q3-runtime-diagnosis.md` 在原 90 秒边界、单次计时不能归因、无 phase 模型仍有 wrapper 扫描与可能无收益 retry 等限制上一致；没有根据未知根因更改生产。

新 NG36 固定源 `d6ac5ae34c228ac49dd381817b2d8e721f324cd3` 的 149 源文件逐一与 Git blob 和 SOURCE_MANIFEST 核验。5,117 输入 manifest 成员全核；归档 SHA `aea811f2a437590748c86c654345e15d09a2e620cf84345c9f85b910f56b2edd` 与实际 tar 相符，1,123 普通 tar 成员逐一与解包 bytes 比较；1,110 原 FILE_MANIFEST、168 ANALYSIS_MANIFEST 成员 SHA/长度全符。36 槽每个 DUT/condition/请求时间/设置/观测计划及 OSDI 都与旧原槽逐字节相同；deck 恰为四个 lt/le/gt/ge 的 wrdata 引号变更。原 36 个失败文件保留，没有挑选单档成功。另五个保留节点名仍只有源码/本地测试证据，没有被本次 F03 实测覆盖。

36 个原执行均 waveform_available，但最终全 I。冻结配置读回器全部保留 `ReadbackError('unsupported/mutable control command: wrdata ...')`，因其严格 grammar 尚未允许 quoted 引用。这是配置读取器待适配，不应称“36 个无错误完整分析”，更不能把 exporter 修复当配置或 native/runtime 资格。

独立直接解析每个 waveform.txt：dc-1 的三档请求 u=0.49999999999999994（0.5 下一个 binary64 邻点），实际所有导出行均 u=0.5：Q1 186/186、Q2 376/376、Q3 2,165/2,165。time=0 的 lt/le/gt/ge 为 0/1/0/1，与实际读回 0.5 相符。dc-2 上邻点实际读回 0.5000000000000001；不能误写成上下邻点都丢失。此证据证明请求和导出不一致，不能定位是输入解析、求解、内部节点还是出口，也不证明比较运算符本身错误。其余 DC 数值吻合也不能替代 exact-input 独立来源资格。

可复核脚本/记录：`astra-final-ng36-audit.py/json`，最终 failures=[]；analysis manifest SHA `f5874d9b0e32e41b0f33d6a8c489a3a60f6ffd56d7b9f3ae927857a02b669a90`。本轮先对“analysis_error 必为 None”的通用检查得到断言失败，查明上述 36 个预期保守拒绝后，改为明确核对该具体错误并将其保存；未把错误删掉或改成通过。

## 固定 diagnostics 与机制草稿

`BREADTH-DIAGNOSTICS.json` SHA `a30f9eff87665fd79c9faf0283a6d07663a3521538b86d816064b1ca764867cc`、17,325 bytes，detail SHA `130fc36739cd50206b369c21579d8c912a439b321c3a818bca3411a87d02c8b4`。绝对 path/hash 引用独立核验，四个诊断归档及 manifest 全部验证：Spectre EC01 30 files、NG 单例 59、NG closure 146、GN closure 153；对应普通 tar 成员 31/60/147/154。

Spectre 单例独立对比 deck，唯一更改为 digits=17 notation=sci；同一 DUT，20,724 行 time 和所有输出解析为 binary64 后全部相同。它说明本次日志打印精度能够提高，PSF header 仍有六位数字；不回填过去 45 槽的精确设置资格，不把打印值接近请求变成证明，也不替换原科学槽。

closure-v1 manifest SHA `f5912d59cfe867d2d283ff0c8346bf2622867db0e7b910c89aec8c93215e4570` 的 13 成员全部 SHA/长度核验；七份 draft 的所有 claims 均 `not_closed`，reviews 空，原 261 scopes 保留。本轮依明确任务边界仅核封装与 unknown 状态，未重审静态函数链，不批准任何 proof digest、不授任何 backend 科学资格。已审的历史 /work 启动文件、完整 NG native 链、GN 实际 loaded plugin/method 缺口继续保留。

记录在 `astra-final-diagnostics-audit.py/json`；其中 Spectre 行比较由原冻结 parser 加独立相等判断完成，既没有运行 simulator，也没有加入新的 reader 规则。

## 暂核 trail 与旧材料不可变性

本轮可访问 trail 前 39 行的 bytes 仍为上次审核 SHA `2e0bb7c44db435b8a663bfbf693b8158a26623b3330e4340323189a3532a2647`；当前暂审至 51 条、2026-10-11T21:49:48Z，SHA `1bc17421defcb7acf87af71fd9114161c2596e5ed5254c4ac1057b62c16b444c`。新行保留旧 852、exporter 单例/36 重跑分界、错误 GLM 路径的追加纠正、未批准 proofs、GLM 工具身份失败的保留、EC21 回退和 NG dc-1 根因未知。113/90 测试日志尾部确实记录相应全部通过；这些不是本轮重复执行的测试，也不替代实际科学比较。

旧完整 v2 compact 仍为 SHA `7e8e65e7efb74149e25f49436f0d4a2d1fa8d4e6db6c451ac7b156edf1dd99b5`。此处只声称可访问材料和增量审查；不声称取到了整个会话 transcript。待最终文档、最终 trail、包含 NG36 的明确 852 compact 到齐再补最终结论；现有 EVAS-only `public-receipt-complete-v3-baseline-852-v1` 不能误作 NG36 最终版本。


## 最终 852 固定收据审查

最终 aggregate SHA `5d75a8fed454c44885e097d854b5deec1adcca93a757b8c96a14cbe8081da3a3`；选择表 SHA `f06b7ecdc4af2acf7fcb06f32af8f64160046f8e5ec25883f30cdbea4dfd39b1`；compact 为 `public-receipt-final-v3-ng-f03-852-v2/PUBLIC-RECEIPT.json`，SHA `762a6a6bfe754ea773b28f6b511206d1a14c3dfe9bd7361260de4e66a90ca2ab`，1,544,534 bytes；failure inventory SHA `a126da4e813397279125c26c22402735ccaa1658b24b2934679b75c8c5f448a3`。三个目录的 manifest 成员 SHA/长度独立核验通过，curator 固定为 d9f20088。

`astra-final-852-audit.py/json` 独立检查了 852 唯一 backend/variant/Q 键、原固定选择、全部九状态轴、误差和预算、来源/RESULT/tool/kernel 身份、legacy/config/external 去重表还原、设置值、528 个 group 聚合及 4,748 个 reason 引用。新选择 213 EVAS+36 NG 的每槽 RESULT 与已封存重分析再次绑定；其余 603 槽逐字段与原完整 v2 基线对比，科学状态、误差界、预算和原始身份全等。没有把原执行失败改名成缺证，也没有按 Q 串用其他配置成功。所有 probe_only 都没有 P；两个开源后端 native/runtime/integrator 仍全 unknown、零最终 P；external_proofs 为空。

| 后端 | P | I | X | 数值错误 N | 行为错误 B |
| --- | ---: | ---: | ---: | ---: | ---: |
| EVAS | 105 | 81 | 27 | 0 | 0 |
| Spectre | 49 | 160 | 3 | 1 | 0 |
| ngspice + OpenVAF-R | 0 | 118 | 81 | 14 | 0 |
| Gnucap + modelgen | 0 | 151 | 21 | 35 | 6 |
| 合计 | 154 | 510 | 132 | 50 | 6 |

表格来自独立重新计数，和 compact counts 完全相同。P 与 numeric pass 的分层保留；N/B 表示冻结判据观察到相应错误，不自动归因为语言能力或后端实现缺陷。NG36 的 X→I 是 exporter 实际完成，原配置读取器错误与 input 资格仍保留，没有新增数值/完整通过。

## 最终文档与 trail

只读审了 primary 七个文档 diff（COMPARISON、METHODOLOGY、support README、candidate 与导航/能力入口）和 tracked 三份新 JSON；三份 JSON 分别与最终 compact、原 7e8 基线、a30 diagnostics 逐字节相同。`astra-final-doc-table-audit.json` 保留三个主要文档 SHA。自动独立解析主表：恰 44 组、528 个 group/backend/Q 单元，94 个 ✓ 对应且仅对应 aggregate 的 group pass；同组所有 mandatory variants 已由 group 收据保留，没有把单个好变体变成整组 ✓。

71 个模型的时间单位分布独立数得 42 个 1 µs、29 个 2^-20 s。预算说明 1 V 刻度、10.1 µV/1.01 µV/101 nV，以及 1%/10% 子界并入总预算，与既有固定卡/合同审查一致。候选配置和有效读回有明确区别，Spectre conservative 实际 reltol 缩放、Gnucap 时间量化与首步 Euler、原生和设置两条取证义务有保留。EC03/13 停止时刻 callback 被写为额外卡合同，四个 probe 共 48 个位置仍占分母且无 ✓。F03NG 写明配置读取器待适配及 dc-1 实际输入问题；F14/F20 等五个新波形仍 I，EC21 Q3 原限额回退明确披露。没有根据 NG/GN 缺证或少量超差推断其整体不支持或精度低于 EVAS，也没有性能优越性或公开 raw 可复现宣称。

历史八条件配置、数值与专项结果的表格行仍保留；移除的是旧“下一步范围”表并以本轮问题表重写，不是改写原成绩。原八条件/A0/v1 卡不变。#119/#96 义务和 #131 不动在正文明确保留。support 最末固定审查历史链接的占位将由归档后替换；本结论不声称该链接已公开可用。

trail 最终暂定截止 52 条、`2026-10-11T21:53:05Z`，SHA `d46d49754591919aeadc997e8c9f5cbbd8fa93bbc53c4c377de9d48b6495a2eb`。前 39 条与上次 SHA 完全相同；新增 13 条的实际文件/commit 引用逐一检查，唯一缺失是 21:06 预写的 GLM 路径，已在 21:07 下一行明确纠正并指向真实报告，所以保留历史而非删改。最新 852/NG36/EC21 叙述与本次直接数据一致。`astra-final-trail-audit.json` 固定截止与指针结果。本轮只覆盖可访问文件、当前任务消息和对应提交，不能宣称审核了完整会话 transcript；后续增加的 trail 行需另作增量审。

## 审核操作错误与恢复

我读取冻结 observations/parser 时有一次 Python 调用漏加 `-B`，在 foundation-v3-part1 的 frozen-repo 生成 3 个未列 manifest 的 pyc。这是本次审核引入的派生文件，不是生产运行输入，且违反只读冻结目录的操作要求。core 的完整 inventory 校验正确拒绝该状态。经 root 授权后，core 把三份缓存按原路径、SHA 和 bytes 保存在 `review/derived-pyc-quarantine/QUARANTINE.json` 所列位置；未删除证据或忽略新增文件。

我随后独立核对三个隔离文件 hash/bytes、原路径已不存在，以及该分析目录实际文件集合严格等于原 ANALYSIS_MANIFEST 成员加 manifest 本身；所有原成员 hash 不变。core 另完成完整 17 lane/22,213 raw files/852 slots 的 companion 复验（其执行记在 `independent-final-v3-ng-f03-byte-audit-v2.json`，不是我冒称重跑）。最终 762a 收据未改。后续 Python 一律 -B，封存树不再写入。

本报告没有重复执行仿真或旧数学校准；实际运行的独立核验是上述散列/归档/原始解析/字段一致性/表格与 trail 检查。新增科学成绩与未批准机制资格没有混用。后续只需对归档链接和新追加 trail 作有限增量复核，不应为追求 P 重选原槽。
