# Breadth 最终增量独立审查

本轮独立复核发现一个真实的 transition 参考包围缺陷，现已由 `ce67a7524476dd8a70b935e0ccff4c4fbd0d205f` 修复并通过独立复测。已审的其余增量未发现新的 P1/P2。另定位了旧观察计划的重复舍入问题，其后续生成器修订尚未纳入本报告。F07 实际 Spectre 数值一致，但正式资格仍为 I，不能沿用旧 native qualified 标签。

## 范围与固定身份

初始比较为 `cec42221e0b52e95689c8de77c61445a65bb184b..5fce77d6926794331a5beebfa16151cf18485e06`，覆盖 core `934cd1fa`、composition `db36c834` / `a6a6c71e` / `f17face9`、runner `7ba9d2a2`，以及配套事件手册修订。增量追加审阅 runner `fb9d222d12a3d1199ef7a111a0a140e691220150` 和 composition `ce67a7524476dd8a70b935e0ccff4c4fbd0d205f`。

使用 vaevas-review-pr / evas-validate，以代码、调用路径、独立数学控制和实际 collected raw 作判断。没有启动远端，没有写 tracked 文件、修改旧结果或操作 PR #131。

## P2：已完成的 transition 错误缩窄不确定目标，已修复

受影响位置为旧 `precision_breadth_composition.py:436–437` 的 `_transition.val`。原式用同一对 `min(start.lo,target.lo)` / `max(start.hi,target.hi)` 同时钳制 `v.lo` 和 `v.hi`。当上升边沿已经完成、target 是区间时，低端也被钳到 target.hi。

最小复现：80 位 Decimal 下调用 `_transition(_I(10), [_I(0)], [_I(1,2)], 0, 0, _I(1), _I(1))`，旧结果约为 `[2,2]`，必须包围 `[1,2]`。真实 EC01 卡的每个 callback 盒取 `[nominal, nominal+late]`，在 stop=9T 时，旧参考 q 为 `[1.1999999999999997,1.20002097152]`，out 却为 `[1.2000209715199996,1.20002097152]`。盒内所有 callback 均取 nominal 是合法全局历史，它的独立答案约为 1.2 V，被 out 参考排除。这可能把正确后端误判为数值错误。

此缺陷已存在于上一检查点，不是 f17face9 的 return-answer 改动新引入；本轮按要求检查 transition 全路径时独立发现。修复分别对下端和上端使用各自 start/target 端点，保留已完成目标的区间。新回归包含上/下已完成目标、中途目标、EC01 全路径以及错误值拒绝。

独立复测脚本为 `review/astra-transition-fraction-probe.py`。它用完全标量的 Fraction 状态机重放 EC01/EC02，每组 62 个查询，覆盖 callback+delay 附近及 nextafter、升/降完成端点、stop。每个 callback 取合法盒的 0、0.5、1 分位，查询取序列化时间盒两端，共 40,176 个精确有理数答案均被修复参考包围。相同探针在修前 EC01 stop 失败。此控制是开发校准，不是科学实测或全域形式证明。

## 其余判据与设置

- core 对尚未证明 exact input identity 的相关输出保留 conditional_error 和原始行，将无条件 numerical 分类保持 unknown；按输出声明义务时，不相关输出的独立错误仍判 numerical_error。卡片自填 verified 不会取代实际证据。
- EC16 的零点时间盒同时包围 DC 的 d=y=0 与瞬态右值 d=1、y=1-exp(-x/2)/2，2 ps 的右侧义务保留。相位及导数/拓扑证据未证时仍为 I。没有把零点改成 undefined 或删除初始行。
- f17face9 在后续未到事件处返回已保存的 answer，保留前一个事件两侧分支的 hull。其修复必要，但不能替代上述 val 的独立修复。
- EC05 仅将保留字 edge 端口改为 edge_v，仍是 support_probe_only，不取得伪造的精度参考。必须新输入身份执行，不能把旧编译失败改写成成功。
- runner 唯一匹配使用预先固定的 `16*ulp(stop)`，以 Fraction 差验证边界；原始时刻不改，两个请求不允许共用一条实际行，一个请求存在两条候选实际行时也不通过。没有增加时间预算。
- fb9d222d 只在新冻结输入中把 Spectre Q3 的候选映射为 deep_bound，step_units=0.0004，其他容差继承 deep；各后端映射、来源 SHA 和 PROFILE_BINDINGS 纳入 manifest。Q 预算与其他后端候选不变，旧计划仍可按原身份执行。候选设置不等于实际读回证明。对 dyadic unit=2^-20，其 maxstep 仍是 3.814697265625e-10，实际日志若截断仍可能保持 I；本审查不宣称该候选解决所有回显问题。
- 事件手册现已说明有限非零系数自身仿射更新，上一轮“仅系数 1”的文档不一致已修。

## 实际 Spectre F07 复核

读取目录 `batch/collected/foundation-spectre-part1/outputs/foundation-spectre-part1/runs/F07-base--Q1` 至 Q3。逐档核对 PSF 和 dut.va 的 SHA 与原 RESULT 一致，再通过既有原始解析器读取全部记录。行数分别为 259、476、2260。每条记录按实测 count 独立核对 `(first,last,y)`，全部精确等于 `(0,1,1)`、`(1,12,13)` 或 `(11,122,133)`。三档发生记录均依次为 t=0 的 count=0、t=2.499e-7 的 count=1、t=5e-7 的 count=2。

当前 checker 重分析的输出误差上界均为 `3.410605131648481e-13 V`。完整 callback 盒仍为 timer `[2.498999805825209e-7,2.4990000000000337e-7]`、cross `[4.999979999999966e-7,5.000000000000034e-7]`，两者都未完整落在合法窗口内，behavior 为 unknown，Q1/Q2/Q3 总资格均 evidence_insufficient。没有裁剪盒或改实测时刻。

新版 runner 重放还发现独立的请求覆盖缺口。三档 PSF 行都通过了逐条 accepted annotation 对应阶段，unknown 出现在其后的 requested strobe 覆盖阶段，因此不能把“原始记录的 accepted 来源已匹配”和“所有请求都有唯一覆盖”混成一个事实：

- Q1/Q2 的请求 `5.000019999999999e-7` 与 `5.00002e-7` 共用同一实际行，唯一覆盖失败。
- Q3 在请求 `4.375e-7` 就没有半径内实际行，最近记录是 `4.375000000000038e-7`，相差 `18*ulp(stop)`，超过固定 16，必须保留 unknown。

原 RESULT 中的 native qualified 是旧判据结果，保留作历史；不能直接用于新版结论。本轮没有改写 RESULT 或 ASSESSMENT。修复后 EVAS 的新远端配对尚未由本报告读取，不能把先前本地回归替代实际新执行。

## 观察计划重复的生成根因与待办

F07 第一个重复请求来自 `critical:4` / `array-cross:nominal` / `array-cross:early` 的 `5e-7+2e-12`，结果为 `5.000019999999999e-7`。另一请求是 array-cross dense grid 的第 2/52 点。生成器先用 float 得到 a=`4.99998e-7`、b=`5.001019999999999e-7`，再转 Fraction 插值，得到 `5.00002e-7`，出现二次舍入。

直接从原始 nominal/early/late/padding 建立 Fraction 后，第 2/52 点最终单次舍入会与上述 padded 请求相同；精确区间宽度/spacing 的 ceil 则应为 53，原浮点预舍入得到 52。建议生成器从原始字段起全程使用 Fraction，仅在输出时一次转 float，并沿用精确 float set 去重；不能用近邻聚类删除 EC20 的独立 near-clock 或不同关键左右边界。修订需要新输入身份和重跑。此建议已交协调者，但后续具体补丁还未由本报告复核。Q3 的 18 ulp 实际覆盖缺口与该重复生成问题不同，不能据此抹去。

## 验证与限制

- 5fce77d6 的 core/foundation/composition/runner 联合校准：100 tests PASS。
- fb9d222d 固定 runner 工作区：13 tests PASS。
- ce67a752 固定 composition 工作区的 composition/core：62 tests PASS。
- 独立 Fraction 全路径包围：40,176 checks PASS。
- `git diff --check cec42221 5fce77d6` PASS。
- 三档真实 F07 的源码/波形 SHA、逐行状态序列、当前数学分类和新 strobe 规则已独立重放。

保留 44 组、71 变体及原 Q/B/100/B/10 预算。没有把校准次数加入通过分母，也没有删掉原始失败或未知结果。当前日志的新增条目区分原 F07 拒绝、修复、旧 raw 和待新执行；本轮只审阅可见日志和证据，没有完整历史会话，不是全夜间审计。后续生成器补丁、实际新批次和最终汇总需分别绑定身份复核。


## 最终追加：5f73f501 的冻结前复核

固定集成身份 `5f73f5016bb44808549ddfbf9b685bc192f2b2d7`，追加审查 core `1fe3ceb0607335f2f7ce7c8f15b27af3e3416d38`、foundation `97e51144c0bcf4ce2ab806816a9ddc19e84b0884`、fixture `aa5650494161672f338db38f89fcac9891542f34` 和 runner `0a54d5ec803c947cb91934173a87e7ad81013ec6`。本段替代前文“观察计划补丁尚未复核”的待办状态，不改写原始诊断和历史结果。

此增量未发现 P1/P2。从本次已审技术范围看，可以开始以新的 source/input/controller 身份冻结，并在既有授权资源范围内执行。这不是 merge 授权，也不是科学通过、GLM 审查完成或实际新批次已执行的声明。

生成器现在从原始 event nominal、early、late、padding 和全局步长组成 Fraction，计算 n 和网格后才单次转换为 binary64；最后仅按完全相同的序列化值去重。没有近邻聚类。foundation 移除的只是同一 event 端点在 critical_times_s 中的预舍入副本，events 原字段和共享 critical_points 生成的中心/边界/左右义务仍在，F07/F19 参考答案没有改变。测试 fixture 相应从 events 原字段建立手写观察义务，未降低实际判据。

独立检查结果：

- F07 保留 `5.000019999999999e-7`，原伪重复 `5.00002e-7` 不再生成；dense 网格 requested_intervals 为 `[103,53]`，总请求数为 202。F07 和 F19 各 18 个 event nominal/early/late 及左右点都由 Fraction 原操作数生成并存在于计划。
- F20 的真实 wrap `2.5e-6` 与全局网格 `2.4999999999999998e-6` 均保留。
- EC20 两个接近 6 us 的 event identity 和 nominal_exact_fraction 保持不同，分别是 `14167099448608935/2361183241434822606848` 与 `1770887431076117/295147905179352825856`。两者都序列化为 6e-6，计划保留该序列化请求；精确物理事件仍是两个，原有次序/观察分辨限制仍须保持 I。不能把“精确身份保留”误述为“导出时间能分辨它们”。

runner 的 `defer_analysis=False` 仍是 API/CLI 默认。显式开启后，waveform_available 只令 analysis_status=pending，资格和各 tier 都为 unknown，不调用数学 checker、设置或原生观察分析，不创建假 assessment。编译/执行失败保留原失败状态，未达到的 frozen slots 保留 not_run，尝试计数、raw 文件、文件 manifest 与执行身份照常写出。后续本地 reanalysis 必须另存身份及结论，不能覆盖旧 RESULT；这与本轮设计一致。

本次在固定集成检查点独立运行 core/foundation/composition/runner：113 tests PASS。`git diff --check 5fce77d6 5f73f501` PASS。另直接遍历上述卡的 event 义务、伪重复点与真实近邻身份，全部满足预期。44 组、71 变体、Q/B/100/B/10、16 ulp(stop) 与资源限制未变。此前旧 F07 Q3 的 18 ulp 实际缺口仍是旧运行的事实；这次生成器修订不抹去它。


## 实际 v2 F07 独立复核

本次读取 `f07-before-after-final-v2.json`、`analysis-foundation-evas-part1-final-v2/` 和新 batch-v2 foundation-evas-part1/part2 收集文件，另对照旧 batch 的 EVAS/Spectre F07 原始文件。未远端执行、未改原 RESULT 或门槛。本段支持执行缺陷修复和有限观测数值一致，不构成完整 Spectre alignment 或 merge 结论。

### 身份和执行事实

- 汇总中六个新旧 EVAS execution 的所有显式 artifact hashes 均匹配原文件。分析 manifest 的 hash 与汇总相符，三份 F07 分析文件及 ANALYSIS_IDENTITY 也匹配该 manifest；汇总 assessment 与独立读取的三份分析内容一致。
- 新 foundation-evas-part1 的 FILE_MANIFEST 覆盖 1495 文件、93 个 RESULT；part2 覆盖 625 文件、39 个 RESULT，全部 SHA256 匹配。这里验证的是收集身份，不是全部 132 个运行的数学正确性。
- 两份 BUILD.json 都记录 release 离线构建成功，source revision 为 `5f73f5016bb44808549ddfbf9b685bc192f2b2d7`，source manifest SHA256 为 `23bc00db689510a8a820d7dd661020303353dd8e1f3fe8060415957c8410b691`，kernel SHA256 为 `a91e466a34136abb5119c61a398c05c4499258ac5c98539e673035c6f85504d3`。TOOL_IDENTITY 报告的执行内核 hash 与构建一致。前段审计已将 149 个源文件逐个对应到固定提交。二进制本身未下载重哈希；此处依据远端构建/执行收据，不把 kernel --version 未内嵌 build_revision 改说成已内嵌。
- 旧/新 EVAS 和旧 Spectre 三档共九份 DUT 的 SHA256 全为 `a7bfa933008404921a2a8001e6a961464444c1e9e1daa6e8d880b9339cc6413c`。每一档的 requested_settings 也相同。新旧 EVAS request.json 完全相同，但 worker 单独读取的 requested_times.json 从 199 点变为 202 点，反映先前审查过的 Fraction planner 修复。因此这是同模型、同求解设置、修订观察网格的前后比较，不应称全输入逐字相同。INPUT_IDENTITY 只覆盖其列出的 DUT/settings/deck；完整观察身份由另外的 frozen manifest 和 original_artifact_hashes 约束。
- 旧 EVAS Q1/Q2/Q3 均为 unsupported_cross 拒绝，原证据仍在。新三档均为 waveform_available。实际回读的 relative、absolute_V、max_step 分别为 Q1 `(1e-5,1e-9,3.125e-8)`，Q2 `(1e-8,1e-12,3.90625e-9)`，Q3 `(1e-10,1e-14,4.8828125e-10)`，stop 都为 1e-6，max_step_applied 为 true。iabstol 和 integration method 继续记录 unsupported/unknown。

### 独立状态核对

直接读三份 CSV，每份 202 行均与 raw-response 的 strobe times/voltages 逐项相等。计数只取精确的 0、1、2，并在 t=2.5e-7 与 t=5e-7 两次改变。由 DUT 本身逐步计算 q0=10*q0+1、q1=10*q1+2，可得：

| count | first | last | y |
|---|---:|---:|---:|
| 0 | 0 | 1 | 1 |
| 1 | 1 | 12 | 13 |
| 2 | 11 | 122 | 133 |

所有新 EVAS 行均符合表中状态，且按其实际时间对应正确阶段，末点 count=2。另独立解析旧 Spectre PSF，Q1/Q2/Q3 分别为 259/476/2260 行，所有行也符合按实际 count 确定的同一状态表。两后端 timer 实际落点不同，新 EVAS 日志 2.5e-7，旧 Spectre 计数首变点 2.499e-7，不能写成逐时刻波形完全相同。

这些输出在每一阶段是常数，精确数值差为零。保留 checker 既定四 ULP 参考导出和八 ULP 观测序列化预算，在最大输出 133 V 处独立重算 `4*ulp(133)+8*ulp(133)=3.410605131648481e-13 V`，与三份报告一致。该量是含预算的上界，不是测得非零误差，也不证明整条轨迹或回调时间。

### 为什么 callback 仍为 I

raw transient.events 明确记录 state_names `[dut:q[0],dut:q[1],dut:n]`，timer 于 2.5e-7 从 `[0,1,0]` 更新为 `[1,12,1]`，cross 于 5e-7 从 `[1,12,1]` 更新为 `[11,122,2]`，guard_value=0。这些事实与预期语义相符。但当前冻结合同通过相邻计数观测推导独立时间包围，并未将内核自报事件日志认证为更窄的 callback bounds。日志没有独立 root enclosure/误差界，不能直接把它替换成零宽区间。

由原始计数行和固定 `16*ulp(stop)=3.3881317890172014e-21 s` 重新计算，三档均得到：

- timer `[2.499990097087345e-7, 2.500000000000034e-7]`，位于允许的 timer 窗口内。
- cross `[4.999999622641475e-7, 5.000000000000034e-7]`。数学根为 5e-7，cross 不允许 early；下界早于根约 3.77358525e-14 s，远大于允许的时间序列化预算。

该 cross 区间包含合法根时刻，并未整体落在非法区域，所以 checker 返回 unknown / evidence_insufficient，而不是 behavior_error。区间伸到根前反映有限观察不能排除更早变化，并不证明实际更早触发；raw 日志反而记录在根处触发。因此当前证据不能把 I 归因为新的 solver bug。也不能将 bracket 与合法窗口求交或只采信日志中心值，使其变成 PASS。

本范围无新的 P1/P2。三档 execution 已修复、有限输出数值一致；完整回调认证仍 I。相关机器核对结果保存在 `review/astra-f07-actual-v2-probe.json`。F14/F20 拒绝和最终全表尚不在本段数学审查范围。
