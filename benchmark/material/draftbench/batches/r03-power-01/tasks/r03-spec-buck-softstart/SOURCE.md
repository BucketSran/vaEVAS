# 来源与验收状态

## 行为依据

规划候选身份：`task_id` U18-S1，`unit_id` U18，来源 `src-32a72c70266b`，`primary_ref` C397，动作 S（spec-modeling），家族 R03，优先级 P0，建设成本 M。登记见规划登记（`benchmark/material/draftbench/planning/history-candidates/register.json`）中的 U18-S1 条目，规划说明见候选说明（`benchmark/material/draftbench/planning/history-candidates/CANDIDATES.md`）。规划中的 author_work 和 spec_plan 要求如下：
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

每条决定都附理由。标“待用户确认”的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目。

1. 【待用户确认 1】单文件交付，并且不要求模块划分。只收 `/app/circuit.va`，顶层 `buck_ctrl_top`；允许在该文件内自定义辅助模块，但不要求 soft_start、error_comparator、pwm_modulator、power_good 四个公开模块或五个文件。
   - 理由：author_work 要求删除不必要的文件数量约束。本题动作是按规格建模，模块边界不能从输出观察到，checker 也不解析源码。
   - 另一种读法：单文件内仍要求四个具名模块，以保留原题“模块边界有意义”的结构要求。
   - 推荐：不要求模块划分。
   - 代价：原题“多模块系统”的上下文层次降为单模块，`context_level` 取 `single-module`。
2. 【待用户确认 2】`duty_up` 用本拍更新前的软参考。
   - 理由：原文只写 `vfb < soft_ref`，同拍先后没有写明。原 gold 的连续比较器读 transition 输出，在时钟沿上看到的是旧值；实际电路中参考 DAC 的输出也在时钟沿之后才更新。spec_plan 要求写明计算顺序。
   - 另一种读法：用本拍更新后的软参考。合成控制中该读法在三个用例都失败。
   - 推荐：用更新前的值。
3. 【待用户确认 3】`rst` 和 `enable` 只在采样事件读取（同步清零），清零优先于本拍全部更新。
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
   - 控制电平 0/0.9 V，边沿不长于 200 ps，上升沿间隔至少 5 ns，高低电平各至少 2 ns，rst/enable 跨阈值离任何上升沿至少 1 ns；
   - `duty_min`、`duty_max` 必须是 0.05 的倍数，使 duty 始终落在 0.05 的格点上；
   - soft_step、pgood_tol 在 5–100 mV，tr 在 10 ps–1 ns。
   理由：author_work 要求补 vfb/vref 合法域。比较平局按首批惯例排除，不另定平局规则。参数范围以默认值为中心取作者尺度，不是电路极限。checker 遇到台架违反这些条件时报错（无判决），不记为候选失败。
9. 观察与容差：四个输出在每个采样事件后 `tr` 内到达新值，事件后 `1.25*tr` 内的点不评分，其余所有保存点都评分，误差上限 2 mV，步长不粗于 `tr/4`。理由：与 C260 题和首批同类规格一致。合成错误模型最小的偏差也是一个 duty 步长（50 mV）或一个逻辑电平。
   - 用户已确认（2026-10-28）：评分起点与到达期限（fix-r1，审核 F02）。现状：题面写四个输出“在 `tr` 内到达”，checker 从事件后 `1.25*tr` 起评分；只把输出斜坡拉长到 `1.2*tr` 的模型通过全部终评（审核 R02，`tr` 截止时逻辑电平还差 0.15 V）。fix-r1 列了两种读法：(A) 到达期限就是 `tr`，checker 应在 `tr` 截止处起观察，另定有依据的时间误差预算，并加刚好到达与超时 20 % 的对照；(B) 观察从 `1.25*tr` 开始，即晚于 `tr`、早于 `1.25*tr` 到达不区分，题面写明这一点。用户 2026-10-28 经总协调答复“全部按推荐”，采用本条的 (B)。总协调转问时把这一读法编为选项 A，与首批、第二批的 F01 同一决定。题面已写明实际观察起点（“Every saved point of the four outputs is scored except points less than `1.25*tr` after a sample event.”），checker 不动。迟到负例保留：输出 `1.3*tr` 才到达的模型必须被拒（合成控制 `late-1.3tr`、校准候选 `late_arrival_1p3tr`）。新用例 `vth-tr-override` 在每个事件后 127.5 ps（`tr` = 100 ps）留有评分行，正落在 `(1.25*tr, 1.3*tr)` 内，这个负例在该用例上稳定被拒；其余用例的事件在网格上，唯一的评分行恰在 `1.25*tr` 处，判定取决于舍入，不作预期。
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
- 用户确认上面三个“待用户确认”选择（第 9 条的评分起点已于 2026-10-28 确认）；
- 记录 `results/reference.json` 与 `results/calibration.json`。

fix-r1 的检查（审核 `review-pilot-r1` 的 F02、F07、F08、F12；证据目录 `runs/t3-p0-pilot-20261027/fix-r1/`）：
- Python 合成轨迹（未仿真）：建题时的 27 个模型在 5 个用例上的总判定都与预期一致；fix-r1 的 7 个控制都符合事先写下的预期：`late-1.2tr` 全部通过（复现审核 R02；按 2026-10-28 的用户确认，这是题面写明不区分的区间），`late-1.3tr`、写死 0.45 V 门限、写死 200 ps 过渡在 `vth-tr-override` 被拒，三种端点模型只在 `duty-endpoints` 被拒。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：参考解 5 个私有用例和公开用例全部通过，只用网格行重判结论不变，前三个用例的结论与建题时相同；31 个校准候选都能运行，155 次判定中 151 次与 `expected.json` 一致，另 4 次是矩阵不设预期的 `late_arrival_1p3tr` 网格边界用例（旧版上都被拒）。
- Docker：环境镜像与评分镜像各实际构建一次（`runs/t3-p0-pilot-20261027/fix-r1/scripts/docker_check.py`，照 C264-S1 的脚本，镜像标签 `vabench-p0-fix:`），7 项检查通过：评分镜像 `/app` 为空，缺交付物判 0 分，环境镜像 `/app` 等于 starter 且不含 `/tests`、`/solution`，参考解安装逐字节一致，缺后端时公开自测退出码 2，独立评分记 `infrastructure_error` 并给 Harbor 0 分。建题时只引用首批同类检查，这是本题第一次实际构建；本轮 `environment/` 未改。未执行电路。
