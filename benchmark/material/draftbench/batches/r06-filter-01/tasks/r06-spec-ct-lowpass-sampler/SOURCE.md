# 来源与验收状态

## 行为依据

规划候选身份：`task_id` C260-S1，`unit_id` C260，来源 `src-4875a83af6fa`，`primary_ref` C260，动作 S（spec-modeling），家族 FILTER，优先级 P0，建设成本 M。登记见规划登记（`benchmark/material/draftbench/planning/history-candidates/register.json`）中的 C260-S1 条目，来源身份见同目录 sources.json（`benchmark/material/draftbench/planning/history-candidates/sources.json`），规划说明见候选说明（`benchmark/material/draftbench/planning/history-candidates/CANDIDATES.md`）。author_work 要求：把指定的 laplace 调用改成传递函数与状态行为合同，补初态和误差，保留连续历史，不给实现放置骨架。

主来源是 v3:437 `437-laplace-nd-lowpass-filter` 的 `instruction.md`，sha256 `9e3ac167fbac2ffa65bbbd167cae0606874a633f7eb1c09b88ca8acc5810b191`。它在规划登记中标为 local-only，本机副本位于 `legacy/behavioral-veriloga-eval/benchmark-vabench-release-v3/tasks/437-laplace-nd-lowpass-filter/`。同一文件也在公开仓库 [Arcadia-1/behavioral-veriloga-eval@7b5616dc](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd/benchmark-vabench-release-v3/tasks/437-laplace-nd-lowpass-filter) 中，本地副本与公开 blob 的 git 对象一致（instruction `515e52a6`，gold `a32ad014`）。该仓库没有 LICENSE 文件。

原题沿用的事实如下：
- 滤波器是 100 ns 一阶低通，原文指定的写法是 `laplace_nd(V(vin), {1.0}, {1.0, 100n})`，即 `H(s)=1/(1+s*100ns)`，DC 增益 1；
- 每个 `clk` 上升沿把滤波值复制到输出；
- 采样时若 `rst` 高于 `vth`，只清采样输出；
- 阈值 `vth=0.45 V`，输出过渡 `tr=200 ps`；
- 原 starter 在 `initial_step` 把采样状态置 0。

v3:438 `laplace-np-pole-filter` 用 `laplace_np(..., {-1e7, 0})` 写同一个 100 ns 实极点。两者只差算子语法，按规划归入同一单元，不另计题。

原 checker 见本机 `legacy/behavioral-veriloga-eval/runners/simulate_evas.py` 的 `check_v3_437_laplace_nd_lowpass_filter`。它只在前两个时钟沿后 8 ns 各取一个点，按 max(12 mV, 2%) 判定。原有两份台架的 `rst` 都恒为 0，所以“复位不清连续历史”原先没有被检查。本题不继承它的判据和成绩。

历史数值依据：本机 legacy 结果缓存里有原 gold 在原 hidden 台架上的一次 Spectre 21.1.0.509.isr12 运行（2026-07-09，`+preset=ax`，reltol 1e-3，maxstep 10 ns）。用本题 checker 的滤波公式对该波形逐沿复核，两个采样值的误差分别为 0.08 mV 和 0.15 mV，记录见 historical-spectre-crosscheck.json（`runs/t3-p0-pilot-20261027/r06-spec-ct-lowpass-sampler/historical-spectre-crosscheck.json`）。这次运行不属于本题包，只说明 laplace_nd 采样在 Spectre 下的数值误差量级，也说明 `{...}` 数组写法在该版 Spectre 上可用。

外部规范：[Accellera Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（2014-05-30）。
- §4.5.11.4 定义 laplace_nd 的分子、分母为 s 的升幂系数。
- 表 4-20 规定这些系数是常量表达式，参数属于常量表达式。
- §4.5.15 规定模拟算子在 t=0 前没有状态历史。

本题只引用这些定义，没有复制 LRM 文字或代码。外部来源与许可证另列在 sources.json（`runs/t3-p0-pilot-20261027/r06-spec-ct-lowpass-sampler/sources.json`）。

同源与职责，均不重复计数：
- 首批30题：
  - [v3-filter-programmable-lp](../../../v3-01/tasks/v3-filter-programmable-lp/instruction.md)（v4-334）是连续一阶低通扩展为码控截止。其 reset 期间把 `y` 置为 `initval`，即复位会清滤波状态，也没有时钟采样。本题刚好相反：复位只清采样值。
  - [v3-filter-ctle](../../../v3-01/tasks/v3-filter-ctle/instruction.md) 是一零两极连续均衡器，没有采样。
  - [v2-spec-024-clocked-sample-and-hold](../../../v2-01/tasks/v2-spec-024-clocked-sample-and-hold/instruction.md) 在时钟沿采输入本身，没有连续滤波历史。
- 第二批草稿：
  - [v3-filter-envelope](../../../v3-01/tasks/v3-filter-envelope/instruction.md)（v4-336）是能量状态的连续包络，reset 期间清状态，没有时钟采样。
  - [v2-spec-071-acquisition-limited-sample-and-hold](../../../v2-01/tasks/v2-spec-071-acquisition-limited-sample-and-hold/instruction.md) 是跟踪相按 tick 逐步逼近输入的有限采集。本题的滤波器不受采样控制门控，始终连续运行。
- 原56题：除上述各题外，没有其他题以 v3:437/438 为来源。本题 `source_group` 取新组名 `v3-437`，SOURCE_GROUPS 中原无此组。
- R01：[r01-sampling-01](../../../r01-sampling-01/README.md) 的 ideal 与有限采集、r01-sampling-02 的孔径延迟（P0 试点 A 在建）都是采样输入本身，属于 R01 家族。本题属于 FILTER 家族，采样的是连续滤波状态。
- 规划中的同家族候选都尚未建题，与本题不按语法版本重复计题：
  - C264-S1：离散一阶低通，内部 100 ns 更新，外部采样；
  - C250-S1：500 ps 离散一阶低通；
  - C261-S1：连续高通加采样。

## 建模选择

每条决定都附理由。标“待用户确认”的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目。

1. 模块名由 `laplace_nd_lowpass_filter` 改为 `ct_lowpass_sampler`。理由：author_work 要把“指定 laplace 调用”改成行为合同，旧名直接点出算子。题包约定也要求顶层模块用电路功能名。
2. 用传递函数与状态方程 `tau*dy/dt = V(vin) - y` 写合同，不再指定算子。Deliverable 写明任何满足接口与外部行为的实现都可以，不要求特定算子、状态变量或事件组织。starter 只有 include、模块与端口声明和 TODO。理由：author_work 要求“不给实现放置骨架”。原 starter 里含状态变量和 cross 事件骨架，已去掉。
3. 【待用户确认 1】初态：滤波器在 t=0 与输入平衡，`y(0)=V(vin)`，并加入 `dc-start` 用例（`vin(0)=0.6 V`、首个采样在 6 ns）来检验。理由：原 gold 的 laplace_nd 在 Spectre 中从 DC 工作点起步，DC 增益为 1，所以 `y(0)=vin(0)`，与 LRM §4.5.15 一致。原两份台架 `vin(0)=0`，初态从未被区分。另一种读法是零初态（如 `idt(...,0)`），在 `dc-start` 中会失败（合成控制误差 565 mV）。推荐采用平衡初态并保留该用例。
4. 【待用户确认 2】把时间常数暴露为参数 `tau`，默认 100 ns，合法范围 20 ns 到 1 us，终评 `tau-override` 用例取 250 ns。理由：传递函数合同的自然形式带具名时间常数，终评改参数可以发现写死 100 ns 的实现。合成控制中写死 100 ns 只在该用例失败；旧版 EVAS 用常数 100n 的探针变体也只在该用例失败。另一种读法是照原题固定 100 ns、不设参数。推荐设参数。代价：旧版 EVAS 0.8.7 不能降低带参数系数的 laplace_nd，见下文第 11 条。
5. 【待用户确认 3】删去原接口中的 `mode` 端口、`vhi` 参数和 `metric` 输出，接口改为 `(vin, clk, rst, out)`。理由：原文说明 `mode` 和 `vhi` 只为旧 harness 兼容，不改变行为；`metric` 与 `out` 恒等。保留它们只增加无行为的接口。另一种读法是为了可追溯而原样保留。推荐删去。
6. 采样语义沿用原文：上升沿过 `vth` 为采样事件；采样时 `rst` 高则采样值为 0 V，否则为该时刻的 `y`；两次采样之间采样值不变；第一次采样前为 0 V（原 starter 的初值）。`rst` 只在采样事件被读取。异步清零属于错误，`base` 中 `rst` 在两沿之间上升，以及 853–867 ns 不跨沿的短脉冲，都用来检验这一点。
7. 输出：采样后 `tr` 内到达新值，`tr` 内的波形不作规定（smoothstep 形状的合成控制通过）；采样事件后 `1.25*tr` 内的点不评分，其余所有保存点都评分；误差上限 2 mV；评分波形步长不粗于 `tr/4`。理由：
   - 2 mV 与首批同类规格一致；
   - 历史 Spectre 的滤波误差为 0.15 mV，旧版 EVAS 常数探针最大为 0.29 mV；
   - 合成错误模型中最小的误差也大于 50 mV，例外是只在 `tau-override` 才区分的写死 τ（440 mV）。
   原 checker 只取 2 个点、按 12 mV/2% 判定，过宽，不沿用。
   - 用户已确认（2026-10-28）：评分起点与到达期限（fix-r1，审核 F01）。现状：题面写 `out` “在 `tr` 内到达”，checker 从事件后 `1.25*tr` 起评分；只把输出斜坡拉长到 `1.2*tr` 的模型通过全部终评（审核 R01：默认 `tr` = 200 ps 时 240 ps 才到达，`dc-start` 首次 0→0.6 V 更新在 `tr` 截止时还差 0.1 V）。fix-r1 列了两种读法：(A) 到达期限就是 `tr`，checker 应在 `tr` 截止处起观察，另定有依据的时间误差预算，并加刚好到达与超时 20 % 的对照；(B) 观察从 `1.25*tr` 开始，即晚于 `tr`、早于 `1.25*tr` 到达不区分，题面写明这一点。用户 2026-10-28 经总协调答复“全部按推荐”，采用本条的 (B)。总协调转问时把这一读法编为选项 A，与首批、第二批的 F01 同一决定。题面已写明实际观察起点（“Every saved point is scored except points less than `1.25*tr` after a sample event.”），checker 不动。迟到负例保留：输出 `1.3*tr` 才到达的模型必须被拒（合成控制 `late-1.3tr`、校准候选 `late_arrival_1p3tr`）。新用例 `vth-tr-override` 在每个事件后 127.5 ps（`tr` = 100 ps）留有评分行，正落在 `(1.25*tr, 1.3*tr)` 内，这个负例在该用例上稳定被拒；其余用例的事件在网格上，唯一的评分行恰在 `1.25*tr` 处，判定取决于舍入，不作预期。
8. 合法域（原题没有）：
   - `vin` 连续，范围 -1 V 到 +1 V。台架含负值段，可检验无夹位；
   - 控制电平 0/0.9 V，边沿不长于 200 ps，`vth` 在两电平之间；
   - 相邻上升沿至少 5 ns，高低电平各至少 2 ns，`rst` 跨阈值离任何采样事件至少 1 ns；
   - `tr` 范围 10 ps 到 1 ns，使 `1.25*tr` 小于最短高低时间。
9. 台架：四个用例，其中 `vth-tr-override` 是 fix-r1 新增的私有用例，公开用例与台架未变。前三个用 50 ps 输出网格，`maxstep=50p strobeperiod=50p`；所有 PWL 拐点落在各自的网格上，checker 从行数据重建 `vin` 时没有插值误差。
   - `base`（公开兼终评）：20 ns 规则时钟；两沿之间的阶跃、慢斜坡、负值段；跨 3 个采样的复位期间 `vin` 阶跃；不跨沿的短 `rst` 脉冲。
   - `dc-start`：不规则时钟，周期 7.5–38 ns；平衡初态；跨 4 个采样的复位落在斜坡上；单沿复位脉冲；结尾复位保持。
   - `tau-override`：`tau=250n`；25 ns 时钟；跨 6 个采样的复位期间满幅阶跃。
   - `vth-tr-override`（F08）：`vth` = 0.8 V、`tr` = 100 ps，`clk` 沿 180 ps、周期 20 ns，0.8 V 穿越在 `10.0225+20k` ns，网格 25 ps（`tr/4`）。按 0.45 V 门限采样的模型早 70 ps 移动，写死 200 ps 过渡的模型在评分起点仍在过渡，都被拒；`vin(0)` = 0.5 V，零初态被拒；`vin` 在两次采样之间阶跃与斜坡，含跨 2 个采样的复位和不跨沿的短 `rst` 脉冲。`tau` 取默认 100 ns，所以旧版的常数系数探针也能跑这个用例。
   前三个用例由 build_cases.py（`runs/t3-p0-pilot-20261027/r06-spec-ct-lowpass-sampler/build_cases.py`） 生成，`vth-tr-override` 由 power_filter_cases.py（`runs/t3-p0-pilot-20261027/fix-r1/scripts/power_filter_cases.py`） 追加，前三条记录逐字节不变。
10. checker（[ct_lowpass_check.py](tests/ct_lowpass_check.py)）不读候选源码或参考解：
    - 按记录的 `vin`（相邻行间线性）用闭式解算出 `y`，在记录的上升沿时刻取值；
    - 台架义务出错时抛出异常（无判决，不记候选失败），包括分辨率、`vin` 超域、时钟间距和 `rst` 与采样沿间距；
    - 不依赖任何仿真器特有行。
    共用的 `harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、Dockerfile 和公开入口与首批逐字节相同。
11. 参考解按 LRM 与 Spectre 语义写：`laplace_nd(V(vin), {1.0}, {1.0, tau})` 在连续上下文中逐步计算，cross 事件只读取它的值，`transition` 驱动输出。参考解没有为任何 EVAS 版本改写。`{...}` 数组写法有历史 Spectre 运行证明可用。
    - EVAS 02dee32b 在 stage a 拒绝 `{`；探针变体改用 LRM 2.4 的 `'{...}` 后，stage c 报 `kernel.unsupported_source_uncertainty`。
    - 旧版 EVAS 0.8.7 对带参数系数报 `continuous_body_not_lowered`；改用常数系数的探针变体能跑通并通过 checker。
    这些都是开发证据，不改合同。
12. 参考解是作者按新合同自写的，没有复制公开代码。但它的结构（laplace_nd、cross 采样、transition 输出）与公开仓库中原 v3:437 gold 相同，这是这类模型最常见的写法。原 gold 自 2026-07 起在公开 GitHub 上，评测时应考虑记忆污染。新合同改了模块名、接口、τ 参数和初态规则，原 gold 原样提交不能通过，但核心写法容易改编。
13. 作者校准候选（fix-r1，F12；fix-r2，R2-03）：[tests/calibration/](tests/calibration/README.md) 的 `mutants.py` 由参考解生成 16 个错误候选和 3 个正确替代实现，被拒矩阵存为 [expected.json](tests/calibration/expected.json)（格式照 C264-S1，条目都是待 Spectre 校准的预期），README 用中文列出各候选的应拒用例。正确替代实现是 `ddt` 内部节点、`laplace_np` 零极点形式和 `0.2*tr` 的快速输出。
    - fix-r1 还把一个只用标量状态的 25 ps 逐步精确递推登记为正确候选。它只在 25 ps 格点和采样时刻读 `vin`，两次读数之间按直线处理；合同允许 `vin` 在读数之间任意变化，锁定在格点上的三角波输入能让它的误差达到 47.6 mV（审核 R2-03）。fix-r2 把它改为 `probe/probe_step_recursion_25p.va`：只对固定台架有效的数值诊断探针，不是校准候选，不进 `expected.json` 的候选表，单独记账。
    - 与滤波状态有关的错误候选（零初态、复位清滤波、复位冻结滤波）仍建立在这个递推上，旧版 EVAS 能直接运行。固定用例的 `vin` 拐点都在 25 ps 格点上，递推在这些用例上精确，被拒只来自各自的缺陷；零初态候选的接受预期依赖这一点，写在 `expected.json` 的 `conditions`。
    - 样板要求 `correct/` 至少有一个旧版 EVAS 能运行的正确替代实现，本题找不到这样的实现（试点 r3 审核 R3-01 后改准的说法：correct 组里的连续算子版本本身只用标量 real，问题在于旧版不支持这些算子，不在状态类型）。只在事件语句里更新的标量状态只在有限个时刻读 `vin`，会漏掉读数之间的变化；在连续语句里逐步更新又依赖仿真器何时、按什么次序求值模拟块，LRM 不保证。满足连续滤波合同的写法都要用模拟算子或内部节点，旧版 EVAS 0.8.7 都不能降低，所以本题的正确候选都没有旧版结果。

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，没有执行任何 Spectre 电路仿真，也没有运行模型解题。

本轮做了下列开发检查，命令、退出码与结果见 checks.json（`runs/t3-p0-pilot-20261027/r06-spec-ct-lowpass-sampler/checks.json`）：
- 包装检查与阶段静态检查；
- 官方 Harbor 配置解析；
- checker 合成波形控制；
- EVAS 02dee32b 阶段 a–c；
- Docker 引用首批同类检查；
- 旧版 EVAS 0.8.7 冒烟（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）。

EVAS 结果只是开发证据，不是 EVAS 能力验收或校准。旧版只给点值，结果可能不准也不报错。

待办：
- Spectre 校准：参考解在全部用例上通过 checker，并记录误差余量与 `{...}` 写法；
- 作者校准：在 Spectre 上跑 `tests/calibration` 的候选（正确替代实现含 `ddt` 内部节点和 `laplace_np`，错误模型与合成控制对应：离散更新、复位清滤波、零初态、异步复位、写死 τ、迟到 `1.3*tr`、写死门限与过渡等），结果与 `expected.json` 比对；`probe/` 的标量递推探针另跑、单独记账，不计入矩阵；
- 用户确认上面三个“待用户确认”选择（第 7 条的评分起点已于 2026-10-28 确认）；
- 记录 `results/reference.json` 与 `results/calibration.json`。

fix-r1 的检查（审核 `review-pilot-r1` 的 F01、F08、F12；证据目录 `runs/t3-p0-pilot-20261027/fix-r1/`）：
- Python 合成轨迹（未仿真）：建题时的 17 个模型在 4 个用例上的总判定都与预期一致；fix-r1 的 4 个控制都符合事先写下的预期：`late-1.2tr` 全部通过（复现审核 R01；按 2026-10-28 的用户确认，这是题面写明不区分的区间），`late-1.3tr`、写死 0.45 V 门限、写死 200 ps 过渡在 `vth-tr-override` 被拒。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：参考解在旧版上仍不能降低（带参数系数的 `laplace_nd`），4 个用例都停在仿真前。诊断用的常数系数探针（`tau` 换成 100n）不是参考解本身的结果，它在 `base`、`dc-start`、`vth-tr-override` 和公开用例上通过、在 `tau-override` 上按预期失败，换成 250n 的探针在 `tau-override` 上通过；只用网格行重判结论不变，前三个用例的结论与建题时相同。能直接运行的 6 个校准候选的 24 次判定都与 `expected.json` 一致；其余 14 个候选含带参数系数的算子或 `ddt` 内部节点，旧版不能运行，常数系数探针的 36 次判定中 34 次与矩阵一致，另 2 次是不设预期的网格边界用例。
- Docker：环境镜像与评分镜像各实际构建一次（`runs/t3-p0-pilot-20261027/fix-r1/scripts/docker_check.py`，照 C264-S1 的脚本，镜像标签 `vabench-p0-fix:`），7 项检查通过：评分镜像 `/app` 为空，缺交付物判 0 分，环境镜像 `/app` 等于 starter 且不含 `/tests`、`/solution`，参考解安装逐字节一致，缺后端时公开自测退出码 2，独立评分记 `infrastructure_error` 并给 Harbor 0 分。建题时只引用首批同类检查，这是本题第一次实际构建；本轮 `environment/` 未改。未执行电路。

fix-r2 的检查（审核 `review-pilot-r2` 的 R2-03；证据目录 `runs/t3-p0-pilot-20261027/fix-r2/`）：
- Python 合成轨迹（未仿真）：探针 `probe_step_recursion_25p` 的逐行移植在 4 个固定用例上通过，误差约 0；在审核 N04 的 25 ps 三角波上被拒（47.6 mV）。三角波相位移半格、振幅改为 0.1 V、延长到三次采样（52 ns）也都被拒（47.5、4.8、197 mV）；孤立的越格阶跃通过（0.009 mV）。精确滤波在这些输入上都通过。建题时的 17 个模型、fix-r1 的 4 个控制和 3 项证据有效性控制重跑，判定不变。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：在临时题包上加了三个越格输入控制，不进本题用例。探针 VA 在两个三角波控制上被拒（三次采样为 47.6、129.6、196.7 mV），在孤立阶跃控制上通过；常数系数参考探针（`tau` 换成 100n，不是参考解）三个都通过。候选源码与 fix-r1 逐字节相同，fix-r1 的旧版结果按新矩阵重比：能直接运行的 5 个候选 20 次判定一致，探针在 4 个固定用例上被接受，单独记账；常数系数探针 34 次一致、2 次不设预期。
- 本轮 `environment/`、用例、checker 与参考解都未改，未重建 Docker。
