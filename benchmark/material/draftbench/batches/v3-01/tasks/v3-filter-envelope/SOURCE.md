# 来源与迁移记录

2026-10-27 第二批 B 组迁移，只改 Harbor 包装、题面与本页。阶段保持 implementation。评分数值代码、私有用例、公开台架激励和参考解行为都没有改。**未仿真**：本次没有运行 Spectre，Harbor 包的参考运行和校准都没有做；EVAS 与旧版 EVAS 的阶段结果只是开发证据，记录在本地运行目录 `runs/t3-batch2-20261027/migration-b/v3-filter-envelope/checks.json`（不入库）。迁移后的审核修正（2026-10-28，fix-b-r1）见“建模选择”中 contract.md 一段。

## 行为依据

迁移前公开合同是 [c485de86 题面](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v3-01/tasks/v3-filter-envelope/instruction.md)，blob `7ddf3f5cb270ef88ba7dbdd4b181fd4a3d55794d`，以及同文的 [environment/public/contract.md](environment/public/contract.md)（blob `7b898d7f70e7b1e7ba06deefa8e74b159c6f3c33`）。原来源页是 [c485de86 SOURCE](https://github.com/BucketSran/vaEVAS/blob/c485de860c6005f451133e8cdc05fe923da29206/benchmark/material/draftbench/batches/v3-01/tasks/v3-filter-envelope/SOURCE.md)，blob `c30c6acd0f75c493fbb63317237097f5f4411bcd`。提交时间 2026-10-15T13:29:47+08:00（`fae1bac209650fcd1ba8fe6f1b1214d258aecbfd`）。

规格 #149 单元 C3b，同源组 `v4-336`。来源身份、许可和改编见 [路线来源](../../../../../../../experiments/benchmark_next/filter/SOURCES.md)：来源 v4 336 只提供包络动态主题；独立能量低通与平方根输出、禁用衰减、复位和初态是本仓库原创重建，不是旧逐采样 attack/release 模型，未把旧源码当成答案。

已保留：模块 `envelope(i,q,en,reset,env)`；连续能量状态 `e'=2π·bandwidth·(P-e)`，`env=sqrt(max(e,0))`；`P=i²+q²`（`en>0.5`），禁用时 `P=0`，包络指数衰减而非保持或瞬间归零；bandwidth 为 100–300 Hz；`e(0)=initval`，initval 为 0–0.02 V²；`reset>0.5` 时 `e=initval`，释放后继续积分；输入 I、Q 在 ±0.5 V；误差上限 0.01 V，复位切换模拟过渡区除外；保持模块名、端口和参数；后端固定 Spectre，不限制合法 Verilog-A 写法；自测不能代替独立终评；权重 1。迁移前壳的默认值 `bandwidth=200`、`initval=0` 写入 Spec。

同源关系：首批 30 题中 v3-filter-ctle、v3-filter-iq-conversion、v3-filter-programmable-lp、v3-filter-sweep-measurement 与本题机制不同。原题面写明“本题为包络动力学的独立交付，与混频题不构成完整接收机计数”。规划池 C266-S1（v3:324 slew-limited envelope：峰值保持/主动释放加连续限速）来源与机制都不同，不重复；同 v4-336 来源的 C262 为组件或变体，没有候选。R01 两题无同源。

## 建模选择

新建连续模型。接口壳只留端口，参数由求解者按 Spec 声明；原公开壳的端口全为 `inout`，壳照原样保留，Spec 按合同角色写 `i`、`q`、`en`、`reset` 为输入、`env` 为输出。状态方程是行为合同，不是必须使用的变量名或算子。原题面“本题为包络动力学的独立交付，与混频题不构成完整接收机计数”是计数说明，移到本页，不写进求解者题面。

按 B 组迁移要求更正两处题面文字。其一，原题面把参数 initval 误写为“initial为0–0.02 V²”，英文 Spec 写作 `initval`。其二，原题面“复位切换模拟过渡区除外”没有量化；固定 checker 有确定的排除区：`compare(..., skip=lambda r: abs(r['reset']-.5)<.49)`，即不比较 `V(reset)` 严格位于 0.01 V 与 0.99 V 之间的输出采样点（`tests/v2_next_filter.py:84`）。英文 Spec 照此写入，并照实写公开台架的 reset 与 en 在 0 V 与 1 V 之间切换。两处都是使题面与 checker 一致的文字更正，不改判据。checker 的期望模型在每个子步中点 `reset>0.5` 时把状态置回 initval（`tests/v2_next_filter.py:33`），与题面阈值 0.5 一致。

`/app/testbench/contract.md` 来自原 `environment/public/contract.md`。迁移时它是原字节副本，仍含“initial”笔误与未量化的过渡区，英文 Spec 写明了这两处差异。2026-10-28 审核修正（fix-b-r1，B11）把新部署副本中的“initial为0–0.02 V²”改为“initval为0–0.02 V²”，其余字节不变；`environment/public/contract.md` 与包根 `public/contract.md` 是 HEAD 中的历史副本，未动。英文 Spec 相应改为只说明该文本没有量化复位过渡区。数值、用例、checker 与参考解都未改；本题在旧版 EVAS 上不能运行（`no_event_transition_ir`），本次没有新的仿真证据。`feedback.scs` 在 `/app/testbench/`，其 `ahdl_include "dut.va"` 改为 `"/app/circuit.va"`。原 `public/dut.va` 是候选壳，现只在 `/app/circuit.va`，不留在 testbench。没有固定 DUT。公开用例取原私有 `tests/cases.json` 的第一个用例 `dynamics-0`，其网表与 `feedback.scs` 原字节相同；`dynamics-1` 只在终评使用。

包根目录的 `public/`（`contract.md`、`dut.va`、`feedback.scs`）与 `environment/public/` 逐字节相同，是旧布局残留。首批四道 v3-filter 题都保留了同样的根目录副本，本题照首批布局原样保留、不改不删。它不在任一 Docker 构建上下文内，不进入求解或终评镜像。

现行题面写已执行失败记 0、原因另记。历史题面只写自测不能代替终评，没有失败分数句。历史路线写 Spectre 扩展集，未证明 ngspice 复验。缺 Spectre 不是语义错误。

## 待定项

`grading` 和 `runtime` 待定。当前未仿真。旧校准只作为 filter 路线记录中的历史身份，本次不运行模型实验。未正式录取或发布。开源复验资格未证明。

现行规则：已执行失败记 0，原因单独记录；未执行不编造 0。打包失败可以由 Harbor 边界记 0，原因另记。没有 Spectre 不是语义错误。

开发证据（记录见文首本地目录）：EVAS 02dee32b 上参考解私有 2 个用例与公开台架在 stage b 报 `compile_error`（decision expressions are only supported in stateless ordinary analog expressions），位置参考解 `dut.va:10:60`，即 `idt` 的复位参数 `V(reset)>0.5`（`routes.json` 记 `va-idt-reset-dependency` #6）。旧版 EVAS 0.8.7（legacy/EVAS 提交 6cb6fa7a）上参考解私有 2 个、公开 1 个用例都在降级阶段失败：`ERROR [rust_lowering]: model:0:envelope_Model:no_event_transition_ir`，没有波形。参考解是只含 `idt` 与连续表达式的纯连续模型，旧版 rust 降级要求事件或 transition 中间表示，这是旧版局限，不是参考解、台架或 checker 的问题。因此本题在本机没有任何仿真器波形证据。旧版只给点值，不做可信证明，结果可能不准也不报错；这些结果待 Spectre 复跑，不是校准或录取依据。

未决：合同把 bandwidth 写成“100–300Hz”、把 initval 写成 V²，checker 用同样的单位；无新的状态方程冲突。
