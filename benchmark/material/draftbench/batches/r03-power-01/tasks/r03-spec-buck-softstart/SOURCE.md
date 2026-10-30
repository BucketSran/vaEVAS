# 来源与验收状态

## 行为依据

规划候选身份：`task_id` U18-S1，`unit_id` U18，来源 `src-32a72c70266b`，`primary_ref` C397，动作 S（spec-modeling），家族 R03，优先级 P0，建设成本 M。登记见[规划登记](../../../../planning/history-candidates/register.json)中的 U18-S1 条目，规划说明见[候选说明](../../../../planning/history-candidates/CANDIDATES.md#u18-s1)。规划中的 author_work 和 spec_plan 要求如下：
- 保留软启动、0.05 占空比步进、模 20 载波和三拍 pgood；
- 补 vfb/vref 合法域、目标下降规则以及 reset/disable 优先级；
- 删除不必要的文件数量约束；
- 写明每拍软参考、误差、duty、载波和 pgood 的计算顺序；
- 区分无量纲 duty 清零与电气输出低电平；
- 承认 duty 可在载波周期中更新。

主来源是仓库内的 [v4:372 buck-converter-controller-macro 公开题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/372-buck-converter-controller-macro/public/instruction.md)（r53，sha256 `7084cc51b138670aa8b34b6891a4e09153e1b5e975122a1f767ae427c8a089bd`）。同一题包也在公开仓库 [Arcadia-1/behavioral-veriloga-eval@7b5616dc](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd/benchmark-vabench-release-v4/release/benchmarkv4-r53/tasks/372-buck-converter-controller-macro) 中，该仓库没有 LICENSE 文件。

沿用的原文事实：
- 端口顺序 `vfb, vref, clk, rst, enable, pwm, duty_metric, soft_ref, pgood`，参数及默认值 `vdd=0.9`、`vss=0`、`vth=0.45`、`duty_min=0.05`、`duty_max=0.95`、`soft_step=25 mV`、`pgood_tol=25 mV`、`tr=200 ps`；
- 每个使能的上升沿，soft_ref 向 vref 移动 soft_step 且不过冲；
- `duty_up` 当且仅当 `vfb < soft_ref`；
- duty 从 0 起每拍 ±0.05，更新后夹在 `[duty_min, duty_max]`；
- 先更新 duty，再 `carrier=(carrier+1)%20`，`pwm=vdd` 当且仅当 `carrier+0.5 < 20*duty`；
- `abs(vfb-vref)<=pgood_tol` 连续三拍置 pgood，失去资格时计数与 pgood 都清零；
- reset 或 disable 把软参考、duty、PWM、载波计数、pgood 计数和 pgood 都清到 vss；
- 只建控制器，不含电感、开关或电流域功率级。

原文没有写清、本题从 [原 gold](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/372-buck-converter-controller-macro/evaluator/solution/buck_ctrl_top.va) 的结构确认的语义如下（见下文建模选择第 2、3、5 条）：
- 原设计中 `error_comparator` 是连续比较器，读的是 `soft_start` 经 transition 的输出；在同一时钟沿，它看到的是本拍更新前的软参考；
- 原设计的清零只在时钟沿生效；
- 原设计的 duty_metric 清零为 0 V，而 soft_ref、pwm、pgood 清到 vss。

原 checker 的五条性质（P_RESET_DISABLE_CLEAR 等）是私有实现，本题没有读取它的源码，也不继承旧验收结果。原公开台架只有一份：vref 恒为 0.62、vss 为 0，没有覆盖 vref 下降、vss 非零或清零后载波相位。

同源与职责，均不重复计数：
- v4 同族的另两种形式在本次都不建：1372 是 bugfix，872 是 testbench。
- 规划中的支撑来源合并进本题，不另成题：C398 是 v4:341 的 buck 软启动坡度，C409 是 PWM 坡度调制前端。
- 规划中的对比项都尚未建题：
  - C403-S1 是 LDO 负载阶跃恢复，处理扰动历史与恢复流程，不含调制载波；
  - C408-S1 是电源与复位排序器，处理多阶段使能次序，不含占空比与反馈资格。
- 首批30题：
  - [v2-repair-uvlo-reset-chain](../../../v2-01/tasks/v2-repair-uvlo-reset-chain/instruction.md) 是修复题，内容为连续迟滞欠压监测、10 ns 复位释放计时、使能门和时钟计数下游。它的 pgood 是电源迟滞比较，没有软启动、duty 或 PWM；
  - [v3-ldo-response-experiment](../../../v3-01/tasks/v3-ldo-response-experiment/SOURCE.md) 与 v3-ldo-startup-measurement 是晶体管 LDO 的测量题，它们的 SOURCE 把 341/372/340 列为“后续控制素材，不形成新计数”。本题不改变那两题的计数。
- 第二批草稿：
  - [v2-repair-reset-sequencer](../../../v2-01/tasks/v2-repair-reset-sequencer/instruction.md)（v4-family-272）是修复题，内容为按 supply_ok/bias_ok 资格逐拍推进的阶段计数与 ready；
  - [v2-repair-uvlo-brownout](../../../v2-01/tasks/v2-repair-uvlo-brownout/instruction.md)（v4-family-046）是修复题，内容为时钟采样的迟滞欠压比较。
  这两题都没有闭环误差积分、调制载波或反馈窗口资格。本题只读引用，不触碰这些正在迁移的题包。
- 原56题中没有以 v4:372 为来源的题。本题 `source_group` 取新组名 `v4-372`，SOURCE_GROUPS 中原无此组。
- R01 是采样家族，与本题无同源关系。

外部检索：
- GitHub 上找到 [Lakshan-D/spacecraft-buck-converter](https://github.com/Lakshan-D/spacecraft-buck-converter)，MIT 许可，有同名的 `rtl/buck_ctrl_top.v`。它是可综合的定点 PID、ADC 码输入和 TMR 设计，与本题行为无关，没有借用。
- 其他命中都是原 v4:372 在公开仓库中各个 release 的副本。

外部来源与许可证列在 sources.json（`runs/t3-p0-pilot-20261027/r03-spec-buck-softstart/sources.json`）。

## 建模选择

每条决定都附理由。标“待用户确认”的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目。原标“待用户确认 1–3”的第 1–3 条（待确认清单第 7–9 项）已定（用户 2026-10-29，决定单第 6 项），都按推荐，2026-10-29 修正 r7b 只改了状态。

1. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 1”，即待确认清单第 7 项】单文件交付，并且不要求模块划分。只收 `/app/circuit.va`，顶层 `buck_ctrl_top`；允许在该文件内自定义辅助模块，但不要求 soft_start、error_comparator、pwm_modulator、power_good 四个公开模块或五个文件。
   - 理由：author_work 要求删除不必要的文件数量约束。本题动作是按规格建模，模块边界不能从输出观察到，checker 也不解析源码。
   - 另一种读法：单文件内仍要求四个具名模块，以保留原题“模块边界有意义”的结构要求。
   - 推荐：不要求模块划分。
   - 代价：原题“多模块系统”的上下文层次降为单模块，`context_level` 取 `single-module`。
2. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 2”，即待确认清单第 8 项】`duty_up` 用本拍更新前的软参考。
   - 理由：原文只写 `vfb < soft_ref`，同拍先后没有写明。原 gold 的连续比较器读 transition 输出，在时钟沿上看到的是旧值；实际电路中参考 DAC 的输出也在时钟沿之后才更新。spec_plan 要求写明计算顺序。
   - 另一种读法：用本拍更新后的软参考。合成控制中该读法在三个用例都失败。
   - 推荐：用更新前的值。
3. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 3”，即待确认清单第 9 项】`rst` 和 `enable` 只在采样事件读取（同步清零），清零优先于本拍全部更新。
   - 理由：原文“On reset or when enable is low, clear …”没有写明同步或异步。原 gold 只在时钟沿判断 rst/enable，author_work 要求补 reset/disable 优先级。
   - 另一种读法：异步清零，例如 EN 拉低立即关断 PWM，这在真实控制器中也常见。合成控制中异步读法在三个用例都失败。
   - 推荐：同步，与原 gold 一致，并在 Spec 中写明“act only at sample events”。
4. 目标下降规则：vref 低于软参考时，每拍下降 soft_step，到 vref 为止不下冲；vref 在运行中可以变化。理由：原文“toward vref … without overshoot”本来就包含两个方向，原 gold 也双向步进；author_work 要求把下降规则补明。`vref-step-down` 用例覆盖 0.7→0.45→0.6 V。
5. 清零电平：soft_ref、pwm、pgood 清到 vss；duty 是无量纲数，清零为 0，duty_metric 以 1 V 每单位输出，所以清零时是 0 V 而不是 vss。理由：这与原 gold 的 transition(duty_state) 一致，也是 spec_plan 要求的区分。`vss-offset` 用例（vss=0.1 V、vdd=1.0 V）检验这一点。
6. 载波：每拍用新 duty 与新载波计数比较，duty 可在 20 拍周期中改变；清零后载波从 0 重新开始，不恢复旧相位。理由：spec_plan 和 acceptance 的原文要求。三个用例中，载波不清零的读法都失败（`base` 中有 8 个事件）。
7. pgood 只看 vfb 与 vref，软启动走到 vref 不等于合格。理由：原文公式本来如此，acceptance 要求“软启动完成不等于输出已合格”。`base` 中软参考在 201 ns 到达 vref，而 vfb 直到 241 ns 才进入窗口；`vss-offset` 中则是 vfb 先合格、软参考仍在爬升。两种方向都有覆盖。
8. 合法域，原题没有：
   - vfb、vref 在 `[vss, vdd]` 内，任何变化都离上升沿至少 1 ns；
   - 每个更新事件上，`|vfb - 更新前软参考|` 与 `||vfb-vref| - pgood_tol|` 都不小于 2 mV，即排除比较平局；
   - 控制电平 0/0.9 V，边沿不长于 200 ps，上升沿间隔至少 5 ns，高低电平各至少 2 ns，rst/enable 跨阈值离任何上升沿至少 1 ns；控制不停在 `vth` 上，到达 `vth` 必定穿过、不触碰后返回（后一句是 2026-10-29 修正 r7b 按决定单第 4 项的 A 收窄版补写的，checker 加对应的台架检查，见该节）；
   - `duty_min`、`duty_max` 必须是 0.05 的倍数，使 duty 始终落在 0.05 的格点上；
   - soft_step、pgood_tol 在 5–100 mV，tr 在 10 ps–1 ns。
   理由：author_work 要求补 vfb/vref 合法域。比较平局按首批惯例排除，不另定平局规则。参数范围以默认值为中心取作者尺度，不是电路极限。checker 遇到台架违反这些条件时报错（无判决），不记为候选失败。
9. 观察与容差：四个输出在每个采样事件后 `tr` 内到达新值，事件后 `1.25*tr` 内的点不评分，其余所有保存点都评分，误差上限 2 mV，步长不粗于 `tr/4`。理由：与 C260 题和首批同类规格一致。合成错误模型最小的偏差也是一个 duty 步长（50 mV）或一个逻辑电平。
   - 用户已确认（2026-10-28）：评分起点与到达期限（fix-r1，审核 F02）。现状：题面写四个输出“在 `tr` 内到达”，checker 从事件后 `1.25*tr` 起评分；只把输出斜坡拉长到 `1.2*tr` 的模型通过全部终评（审核 R02，`tr` 截止时逻辑电平还差 0.15 V）。fix-r1 列了两种读法：(A) 到达期限就是 `tr`，checker 应在 `tr` 截止处起观察，另定有依据的时间误差预算，并加刚好到达与超时 20 % 的对照；(B) 观察从 `1.25*tr` 开始，即晚于 `tr`、早于 `1.25*tr` 到达不区分，题面写明这一点。用户 2026-10-28 经项目协调方答复“全部按推荐”，采用本条的 (B)。项目协调方转问时把这一读法编为选项 A，与首批、第二批的 F01 同一决定。题面已写明实际观察起点（“Every saved point of the four outputs is scored except points less than `1.25*tr` after a sample event.”），checker 不动。迟到负例保留：输出 `1.3*tr` 才到达的模型必须被拒（合成控制 `late-1.3tr`、校准候选 `late_arrival_1p3tr`）。新用例 `vth-tr-override` 在每个事件后 127.5 ps（`tr` = 100 ps）留有评分行，正落在 `(1.25*tr, 1.3*tr)` 内，这个负例在该用例上稳定被拒；其余用例的事件在网格上，唯一的评分行恰在 `1.25*tr` 处，判定取决于舍入，不作预期。
10. 台架：五个用例，其中后两个是 fix-r1 新增的私有用例，公开用例与台架未变。`clk` 周期 8 ns；所有 PWL 拐点在网格上。前三个和 `duty-endpoints` 的上升沿在 `1+8k` ns，网格 50 ps，`maxstep=50p strobeperiod=50p`。
    - `base`（公开兼终评）：vref 0.62；软启动钳在 vref；duty 升到 0.95 再降到 0.05；pgood 合格、失去一拍、再合格；两拍 enable 清零后重启；一拍 rst 清零。
    - `vref-step-down`：soft_step 40 mV，pgood_tol 15 mV，duty 范围 [0.1, 0.8]；开头 enable 为低；vref 下降再上升；一拍 enable 清零。
    - `vss-offset`：vdd 1.0 V、vss 0.1 V；pgood 合格时 vfb 保持在窗口内穿过 enable 清零（资格必须重新计满三拍）；两拍 rst 清零。
    - `vth-tr-override`（F08）：`vth` = 0.8 V、`tr` = 100 ps，`clk` 沿 180 ps，0.8 V 穿越在 `1.0225+8k` ns，网格 25 ps（`tr/4`）。按 0.45 V 门限采样的模型早 70 ps，写死 200 ps 过渡的模型在评分起点仍在过渡，都被拒。内容：软启动到 vref 0.6 V，duty 先停在 duty_min 再上升，vfb 进入窗口后 pgood 合格，一拍 enable 清零后重启。
    - `duty-endpoints`（F07）：`duty_min` = 0、`duty_max` = 1。清零后 25 拍 duty 停在 0，pwm 在一个完整载波周期内恒低（载波回到 0）；duty 升到 1 后再停 25 拍，pwm 在一个完整周期内恒高；一拍 enable 清零；再从 duty 0、软参考 vss、载波 0 重启。禁止端点（duty 始终限在 [0.05, 0.95]，审核 R07）、载波回 0 时总置高的最小导通（duty 0 时每周期多一个脉冲）、载波 19 时强制置低的最小关断（duty 1 时每周期少一个脉冲）三种模型在前三个用例都通过，只在此被拒。
    前三个用例由 build_cases.py（`runs/t3-p0-pilot-20261027/r03-spec-buck-softstart/build_cases.py`） 生成，后两个由 power_filter_cases.py（`runs/t3-p0-pilot-20261027/fix-r1/scripts/power_filter_cases.py`） 追加，前三条记录逐字节不变。
11. checker（[buck_softstart_check.py](tests/buck_softstart_check.py)）不读候选源码或参考解：按记录的输入和记录的上升沿时刻逐拍推算四个状态，再逐点比较。它不依赖仿真器特有行，旧版 EVAS 只用网格行重判时判决不变。共用运行文件与首批逐字节相同。
12. 参考解是作者按新合同写的单模块实现，没有复制原 5 文件 gold，也没有为任何 EVAS 版本改写。
    - 记忆污染风险较高：原 gold 自 2026-07 起在公开 GitHub 上，其行为与本题合同一致。把它的五个文件原样拼成一个文件（只去掉重复的 include），在旧版 EVAS 0.8.7 上三个终评用例都通过本题 checker（旧版开发证据，待 Spectre 复跑）。
    - 新合同新增的 vref 下降、vss 非零和同步清零都是原 gold 已有的行为，所以记得原 gold 的模型会占优。评测分析时应考虑这一点。
13. 作者校准候选（fix-r1，F12）：[tests/calibration/](tests/calibration/README.md) 的 `mutants.py` 由参考解生成 29 个错误候选和 2 个正确替代实现，被拒矩阵存为 [expected.json](tests/calibration/expected.json)（格式照 C264-S1，条目都是待 Spectre 校准的预期），README 用中文列出各候选的应拒用例。原 5 文件 gold 所在的公开仓库没有 LICENSE，按复用边界只读参考，不放进候选。

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，没有执行任何 Spectre 电路仿真，也没有运行模型解题。

本轮做了下列开发检查，命令、退出码与结果见 checks.json（`runs/t3-p0-pilot-20261027/r03-spec-buck-softstart/checks.json`）：
- 包装检查与阶段静态检查；
- 官方 Harbor 配置解析；
- checker 合成波形控制；
- EVAS 02dee32b 阶段 a–c；
- Docker 引用首批同类检查；
- 旧版 EVAS 0.8.7 冒烟（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）。

EVAS 结果只是开发证据，不是 EVAS 能力验收或校准。旧版只给点值，结果可能不准也不报错。

待办：
- Spectre 校准：参考解在全部用例上通过 checker；
- 作者校准：
  - 在 Spectre 上跑原 5 模块 gold 合并成的单文件，作为另一种写法的正确实现（旧版 EVAS 已通过，见 checks.json）；
  - 跑 `tests/calibration` 的 VA 候选（与合成控制对应，包括新软参考比较、异步清零、载波不清零、duty_metric 清到 vss、pgood 看软参考、迟到 `1.3*tr`、写死门限与过渡、禁止 duty 端点等），结果与 `expected.json` 比对；
- 上面三个原“待用户确认”选择（建模选择第 1–3 条，待确认清单第 7–9 项）已定（用户 2026-10-29，决定单第 6 项），都按推荐，修正 r7b 改了状态（第 9 条的评分起点已于 2026-10-28 确认）；
- 记录 `results/reference.json` 与 `results/calibration.json`。

fix-r1 的检查（审核 `review-pilot-r1` 的 F02、F07、F08、F12；证据目录 `runs/t3-p0-pilot-20261027/fix-r1/`）：
- Python 合成轨迹（未仿真）：建题时的 27 个模型在 5 个用例上的总判定都与预期一致；fix-r1 的 7 个控制都符合事先写下的预期：`late-1.2tr` 全部通过（复现审核 R02；按 2026-10-28 的用户确认，这是题面写明不区分的区间），`late-1.3tr`、写死 0.45 V 门限、写死 200 ps 过渡在 `vth-tr-override` 被拒，三种端点模型只在 `duty-endpoints` 被拒。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：参考解 5 个私有用例和公开用例全部通过，只用网格行重判结论不变，前三个用例的结论与建题时相同；31 个校准候选都能运行，155 次判定中 151 次与 `expected.json` 一致，另 4 次是矩阵不设预期的 `late_arrival_1p3tr` 网格边界用例（旧版上都被拒）。
- Docker：环境镜像与评分镜像各实际构建一次（`runs/t3-p0-pilot-20261027/fix-r1/scripts/docker_check.py`，照 C264-S1 的脚本，镜像标签 `vabench-p0-fix:`），7 项检查通过：评分镜像 `/app` 为空，缺交付物判 0 分，环境镜像 `/app` 等于 starter 且不含 `/tests`、`/solution`，参考解安装逐字节一致，缺后端时公开自测退出码 2，独立评分记 `infrastructure_error` 并给 Harbor 0 分。建题时只引用首批同类检查，这是本题第一次实际构建；本轮 `environment/` 未改。未执行电路。

## 2026-10-29 修正 r7b（p0-fix-r7b）

依据：扫描 B 报告第 4 节 (t)、(k) 两项与第 10 节（项目协调方 2026-10-29 批准本轮）；项目协调方的决定：(t) 补 A 收窄版那句与台架判定；P0 各题写入标准审核定的容差行，U18 的 `Vvref` 一并补 `type=dc`；用户 2026-10-29 答复的决定单。改前改后的 sha256、脚本、命令与退出码见本轮记录 runs/t3-p0-build-20261027/p0-fix-r7b/disposition.md（不入库）。本节的检查都**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 题面（instruction.md 第 39 行，合法域的控制一条）。原句只写“Controls never rest at `vth`.”，其后补一句“A control that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.”，与 C264、C266 的写法相同（决定单第 4 项，用户 2026-10-29 定 A 收窄版）。其余不变。控制在 0 V 与 0.9 V 之间切换、`vth` 严格在两电平之间，t = 0 时本来就离开 `vth`，不另加起始余量。
2. checker（`tests/buck_softstart_check.py` 与公开副本逐字节相同；`verify.py` 不变）。新函数 `rest_or_touch` 按保存行把控制与 `vth` 精确比较：连续两行在 `vth` 上（停在门限上），或一行在 `vth` 上而前后两行在同一侧（触碰后返回），`raise ValueError`；单独一行在 `vth` 上、前后分处两侧是一次穿越，记录末尾单独一行在 `vth` 上按到达方向算一次穿越，都不报。它在提取 `clk` 穿越之前对 `clk`、`rst`、`enable` 各跑一次，`v2_runtime.py` 把 ValueError 记作 checker_error（不判分、不算候选失败）。原来只判 `clk` 起点低于 `vth`；采样事件的提取与判分代码不变。
   - 局限：只读保存行，正好落在两行之间的触碰看不到（行上都不等于 `vth`）；现有用例的控制都是完整切换，没有触碰或停在门限上的点（扫描 B 精确核对）。
3. 容差写入（第 (ii) 类，扫描 B 第 4 节 (k)；标准审核 2026-10-29 给的值）。7 份网表都在 tran 行之前另起一行写 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`，tran 行末补 `errpreset=moderate strobeoutput=strobeonly`；`base`、`vss-offset`、`vth-tr-override`、`duty-endpoints`、公开 `base` 与 `visible_test.scs` 的 `Vvref (vref 0) vsource dc=…` 补成 `vsource type=dc dc=…`（vsource 的缺省类型就是 dc，补写不改电路）。
   - `vref-step-down` 的 `Vvref` 本来就是 PWL，写入后再加执行路径一行，与预校准包 P0PC-must-01（包 spectre-P0PC-must-01-v1，结果包 sha256 `56bb45ddcc96029e2ee7bd556bdd9b26db70f2186f91bff0653353d43b837ad6`，已核收）的同例参考解作业网表逐字节相同。
   - 其余 5 个用例网表与 P0PC 作业网表只差 `Vvref` 这一行（`visible_test.scs` 与公开用例另差 include 路径）。按第二批的先例列了确认作业（参考解在这 5 份网表上各跑一次，期望与 P0PC 同例的 PSF 从 TYPE 段起逐位相同），清单在本轮记录里，并不并包由项目协调方定。
4. 复核（都未仿真）：
   - 合成控制 A：建题时的 27 个 Python 模型与 fix-r1 的 7 个控制在 5 个私有用例与公开用例上，加 3 个证据有效性控制，共 207 次判决；改前改后的 checker 给出的整份结果逐个相同，不同的 0 个。
   - 合成控制 B（新台架检查；`rst` 一直为高、每拍清零、输出恒为清零电平的台架，每个折点都在保存行上）：正常切换通过；`clk` 停在 `vth` 上两行、从下方或上方触碰后返回，`rst` 触碰或停在 `vth` 上，`enable` 触碰或停在 `vth` 上，都报台架错误；`clk` 正好穿过一行恰为 `vth` 的点、`rst` 在记录末尾恰到 `vth`，照常通过。改前的 checker 对这些台架照常判分，只有 `clk` 从下方触碰那一例因被当成一次采样、与相邻上升沿不足 5 ns 而报错。
   - 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：建题与 fix-r1 存档的 165 条旧版波形，全部行与只用网格行各判一次，共 330 次，改前改后判决逐个相同，没有新的台架错误。本轮没有新的旧版运行。
   - P0PC-must-01 已核收的 12 个参考解作业（带容差与缺省容差两组）用改后的 checker 重判，全部通过，判决与误差与改前逐个相同。
5. 决定单状态：建模选择第 1–3 条（原标“待用户确认 1–3”，待确认清单第 7–9 项）改为已定（用户 2026-10-29，决定单第 6 项），理由原文不动；待办同步。
6. 参考解、起始文件、校准候选与 `expected.json` 都没有改；校准 README 补了新台架检查与本轮复核的一段。

## 2026-10-30 修正 v417

依据：只读扫描 v417-bench-scan-r1 列的本题 2 处台架义务检查（U18-03、U18-04，Benchmark 维护方已核实）；网表约定清单第 4.21 版（sha256 前 8 位 `7d511985`）第 0.5 节第 20 条，第 4.17–4.21 版新增的各点逐条核过（第 4 小节）；项目协调方 2026-10-30 的三项决定：做法甲的范围是起点、停留、碰到、最小偏离四项一起按网表激励定义判，时序守卫、范围与数值 δ 类检查不动；“碰到”在 14 道题里一律报台架错误；strobeonly 不算满足条件 3，要改的清单不变。另据 Benchmark 维护方 2026-10-30 对本轮第 1 次停下的决定（重判的写法与题面依据，第 5、7 小节）。改动文件改前、改后的 sha256，脚本、命令与结果见 `runs/t3-harbor30-20261027/v417-bench-fix-r1/disposition.md`（不入库）。本节的检查都**未仿真**：没有运行 Spectre、EVAS（含旧版）、模型或 Docker；合成控制是 Python 合成行；重判只读已交回的 Spectre 波形。前面各节原文不改。

改动范围：两份 checker（`tests/buck_softstart_check.py` 与 `environment/starter/testbench/buck_softstart_check.py`，改后逐字节相同，sha256 `04a939dbff8873b4819da4d53c077cd820f76a7d41c04befbc7efb69f53070b4`，改前 `d0d0c6b6…`）与本文件。`tests/verify.py` 不变。题面、参考解、用例网表、`tests/calibration/`、`v2_runtime.py`、`task.toml`、`cases.json` 都没有改；判分逻辑、时序守卫、范围检查与数值 δ 类检查不变。

### 1. 改了什么（编号照扫描）

- **U18-03、U18-04**（`rest_or_touch` 第 39–44 行，evaluate 第 80–82 行对 `clk`、`rst`、`enable` 各调一次）：保存行上相邻两行恰为 `vth`（停留），或单行恰为 `vth` 而前后两行同侧（碰到），报台架错误 → 按定义判；`rest_or_touch` 删去。
- 新增（决定第 1 项的起点；Benchmark 维护方 2026-10-30 决定第 2 项）：`clk`、`rst`、`enable` 的起点恰在 `vth` 上报台架错误。改前只按保存行判 `clk` 从低开始（`clk must start low`，不变），`rst`、`enable` 的起点没有检查。

### 2. 怎么判（做法甲）

- 用哪份定义：checker 读所判用例自己的网表 `case["netlist"]`。它就是 `v2_runtime.py` 写成 `tb.scs` 交给仿真器、跑完再核 sha256 的那一份，被改动就记 evidence_error。私有用例取 `tests/cases.json`，公开检查取 `environment/starter/testbench/cases.json`；`visible_test.scs` 不经 checker 判，本轮用同一读法核过它也读得出。
- 受查量：`clk`、`rst`、`enable` 各自对 `vth`。`check_stimulus` 放在原来 `rest_or_touch` 的位置，在提取 `clk` 穿越之前。
- 定义取值：受查量由它涉及的节点自地起串着的 vsource 得出，在 [0, stop]（stop 取网表 tran 行）上于各源的定义点之间是直线：PWL 用各点的时刻与值，pulse 用 val0、val1 与四个拐角（按周期重复），dc 源用 dc 值，sine 用 sinedc ± ampl 与起点值。本题受查量涉及的源：PWL 14 个、pulse 7 个。
- 在门限上：定义点的值与门限按写出的十进制精确相等，或各自舍成 binary64 后相等，任一成立即算。节点由几个源叠成时，“精确和舍入一次”与“各源先舍成 binary64、自地起逐运算相加”两种值都算。
- 判法（都是 `raise ValueError`，`v2_runtime.py` 记作 checker_error：该例不判分，不算候选失败）：
  - 起点：t = 0 的定义值在门限上，报 “starts on …”（题面没有起点余量，只查恰在门限上）；
  - 停留：相邻两个定义点都在门限上，报 “rests on …”；
  - 碰到：一个定义点在门限上、前后两侧在同一侧，报 “touches … and returns to the same side”；stop 时刻恰到门限算到达方向的一次穿越，不报；
  - 读不出：受查量涉及的节点上的全部 vsource 都要读得出，在差里抵消的源也不例外。数字只写字面量，可带一个比例符号；不写参数名、表达式、行尾注释、单位，也不写指数后接比例符号。pulse 写全六个参数，rise、fall 大于 0；PWL 时刻严格递增；sine 写 sinedc、ampl、freq，不带 delay、damp。读不出报 “cannot read the stimulus definition of …”；受查节点不由用例网表的 vsource 驱动，报 “… is not driven by a voltage source of the case netlist”；网表里有只差大小写的节点名也报台架错误（保存信号按小写配对，Spectre 区分大小写）。
- 穿越：`clk` 的穿越仍由原来的 `crossings()` 从保存行取（不变）；保存行恰在 `vth` 上不再引起台架错误。

### 3. 余量（数值未改）

- 题面没有起点余量与最小偏离，checker 也没有这两项余量，没有数值要保留。本轮只加“起点恰在门限上”，不加余量。
- 改不改这些数值由项目协调方另定，本轮不改。

### 4. 清单第 4.17–4.21 版各点（第 6 条）

| 点 | 本题 | 怎么处理 |
| --- | --- | --- |
| 做法甲（v4.17） | 适用 | 受查量（`clk`、`rst`、`enable` 各自对 `vth`）的起点、停留、碰到按用例网表的 vsource 定义判，不读保存行（第 2 小节）。 |
| “在门限上”的读法（v4.18、v4.20） | 适用 | 门限 `vth` 是用例参数，按写出的十进制与 binary64 两种比；门限不是表达式。合成控制另做了只在 binary64 下才在门限上的变体（第 6 小节）。 |
| 和、差与叠放（v4.18、v4.20） | 不适用 | 受查量是单个节点对地；没有叠放源（本题网表里受查节点各由一个 vsource 直接对地驱动）。代码对叠放照两种舍入处理。 |
| 读得出（v4.18、v4.20） | 适用 | 本题 7 份网表（私有 5、公开 `cases.json` 1、`visible_test.scs` 1）共 35 个 vsource，都读得出，与扫描第 1 节一致；受查量涉及的源 21 个（PWL 14 个、pulse 7 个），都读得出。读不出报台架错误，该例不判分。 |
| 比较式的不同写法（v4.20） | 不适用 | 一种写法：checker 比 `V(x)` 与 `vth`，参考解在 `V(x) - vth` 上求根；binary64 下 `x - vth` 为 0 与 `x == vth` 等价，不另算。 |
| 另一个受查量（v4.21） | 不适用（没有新增受查量） | 参考解 `buck_ctrl_top` 只在 `cross(V(clk) - vth, +1)` 上求根（`rst`、`enable` 按电平读），就是受查输入本身。没有台架模块：`cases.json` 不带 support 源码，公开目录没有 `.va`。候选的写法不在此列（合成控制 B 仍按各候选自己的事件插了根处行）。 |
| 模块驱动的受查信号（v4.17–v4.20） | 不适用 | 受查信号都由用例网表的 vsource 直接驱动，7 份网表逐份核过，不由 vsource 驱动的 0 个；没有台架模块，也没有按候选输出生成的受查信号。 |
| 条件 3 与 strobeonly（决定第 3 项） | 适用 | 本题 7 份网表都写 `strobeoutput=strobeonly`；strobeonly 不算满足条件 3，照改。 |
| 碰到（决定第 2 项） | 适用 | 改前已按保存行报台架错误，现在按定义报。 |

### 5. 题面依据（不改题面）

- 起点、停留、碰到：instruction.md 第 39 行 “`clk`, `rst` and `enable` switch between 0 V and 0.9 V with transitions no longer than 200 ps, and `vth` lies strictly between those levels. Controls never rest at `vth`. A control that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.”
- 起点恰在门限上（Benchmark 维护方 2026-10-30 决定第 2 项）：题面写控制在 0 V 与 0.9 V 之间切换，且 “`vth` lies strictly between those levels”。t = 0 恰在 `vth` 上不是这两个电平之一，已在合法域之外，所以不改题面。这个台架错误只针对本方网表，候选触发不了，也不影响候选的判决；现有网表都没有这种情况。14 道题里只有本题与 C260 的题面没有单独的起点规则，其他 12 题都写了起点（at least 50 mV away，或 starts at a level different from `vth`）。
- 读不出、不由 vsource 驱动：这两种台架错误都是本方网表的失败保护，候选改不了网表，也就触发不了；清单第 20 条写明该例不判分。题面第 45 行 “A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong.”

### 6. 合成控制（未仿真）

- 做法：合成 strobe 行。网表定义在每个 strobe 时刻精确取值、舍成 binary64；候选输出一律给 0 V（沿用扫描 `rowsim.py` 的做法），所以判分结果多为失败，只用来比改前、改后两版 checker 的整份判决与台架错误。导入的是本轮 scratch 下的 checker 副本，字节码关闭。
- A 现有用例网表：7 份网表各两组行，一组只有 strobe 行，一组另在每个受查量的每个定义穿越处插一行恰在门限上的根处行（共 1049 行）。14 次判决：新 checker 都不报台架错误，与改前的 checker 整份判决逐个相同（14/14）。
- B 候选：扫描列出的 31 个候选（`tests/calibration/mutants.py` 在本轮 scratch 生成，不在题包里生成），按各自的 `cross()`、`above()` 事件映射到台架节点，在每份网表上插它们自己的根处行（28 组不同的行，共 15820 行）。改前、改后判决逐个相同，新 checker 不报台架错误（31/31）。
- C 变体（在 `base` 上改 `rst` 的定义；每个变体事先写下预期），10/10 符合预期：
  - `rst` 起点按十进制恰在门限上：报 “starts on”
  - `rst` 起点只在 binary64 下恰在门限上：报 “starts on”
  - `rst` 在 2.795e-07 s 处按十进制停在门限：报 “rests on”
  - `rst` 在 2.795e-07 s 处只在 binary64 下停在门限：报 “rests on”
  - `rst` 在 2.795e-07 s 处按十进制碰到门限：报 “touches”
  - `rst` 在 2.795e-07 s 处只在 binary64 下碰到门限：报 “touches”
  - `rst` 的源有一个值写成参数名 `vlo`：报 “cannot read”
  - `rst` 的源有一个值写成表达式 `0.9*1`：报 “cannot read”
  - `rst` 的源有一个值带单位 `0.9V`：报 “cannot read”
  - `rst` 不由 vsource 驱动：报 “is not driven”

### 7. 已交回作业的重判（未仿真）

- 范围：14 道题全部已交回的 Spectre 作业，以各包 `jobs.json` 的 meta.task 为准，只数正式打包目录（不数 scratch 下的试做包）：34 包 3852 个作业，判了 3848 个，未判 4 个（C266 的执行错误，没到 checker）。
- 做法：每个作业用它发出时的快照判，用例取快照里的那份，只把 checker 换成新版，与原判逐个比；判决相同指 status、passed 与台架错误的有无都相同。P0PC 里有些作业跑的是后来改过的旧网表，只用来比两版 checker，不对现行题包评。快照里的旧 checker 重判，与预读记录的原判逐个相同（status、passed、整份判决 sha256），工具与环境没有问题。
- 结论：本轮改动没有改变任何作业的判决（new 与改前 checker 3848/3848 相同）；与打包时的原判比，3708 相同，140 不同，来自 p0-fix-r9 已记录的激励与规则改动。
- 不同的 140 个全是 U15（`r04-spec-delay-pulse-hold`）：spectre-P0PC-must-01-v1 10、spectre-P0PC-opt-01-v1 26、spectre-P0PC-rec-03-v1 84、spectre-P0PC-rec-04-v1 20。
- 本题：spectre-P0PC-must-01-v1 12、spectre-P0PC-opt-01-v1 35、spectre-P0PC-rec-02-v1 136、spectre-P0PC-rec-03-v1 15、spectre-P0R7-must-01-v1 4，共 202 个。new 与改前 checker 整份判决 202/202 相同。与原判比 status、passed 与台架错误的有无 202/202 相同，整份判决 sha256 也相同。

### 8. 前面各节的相关句子

- 修正 r7b 一节第 2 条第 129、130 行（`rest_or_touch` 按保存行判停留与碰到、“只读保存行”的局限）：自本节起按定义判。第 128 行“t = 0 时本来就离开 `vth`，不另加起始余量”仍成立：本轮只加“起点恰在门限上”的台架错误，不加余量。
