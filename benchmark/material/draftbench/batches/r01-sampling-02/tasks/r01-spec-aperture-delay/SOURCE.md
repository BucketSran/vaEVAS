# 来源与建设记录

2026-10-27 按 P0 试点新建，阶段 implementation，`pending = ["grading", "runtime"]`。本机没有 Spectre，本题未经 Spectre 仿真；EVAS 结果只作开发证据。本页不表示科学校准、模型试做、题目审核或正式录取。

## 行为依据

### 规划候选身份

| 项目 | 值 |
| --- | --- |
| task_id | `C056-S1`（规划候选，规格建模） |
| unit_id / primary_ref | `C056` / `C056` |
| 主来源 | `src-f0266764f7da`：v4 072 公开题面，SHA256 `86d79b3374d86cca66437fb0abf9d79e96cbab599244456f93b0b901e4016e37` |
| 规划登记 | register.json（`benchmark/material/draftbench/planning/history-candidates/register.json`） 的 C056-S1：P0，结构估计难度 M，建设成本 L，作者工作为“补 taperture 合法域、未完成采样的再触发策略和同刻读入约定；不把延迟前采样加输出延迟当等价解” |
| 已确认边界 | 规划说明（`benchmark/material/draftbench/planning/history-candidates/README.md`）：首版公开限定最小触发间隔，排除上一采样未完成时再次触发；保留孔径内输入变化，验收延迟时刻实际读入 |
| 用户决定 | 排除未完成采样的重叠触发，不讨论队列策略；默认孔径 200 ps |
| 建设决策卡 | 本机 `local/research/benchmark-submission-20261025/README.md`「C056-S1：在延迟孔径时读入，而不是延迟输出旧样本」，只读；卡片为暂定补充，未独立审核 |

### 历史原件与改编

[v4 072 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/072-aperture-delay-track-and-hold/public/instruction.md)规定：初值取初始 `vin`；每个 `clk` 上升沿预约 `$abstime + taperture`；到该时刻读入当时的 `vin`；保持到下一次延迟采样；不按 `VSS` 到 `VDD` 夹位；输出平滑。参数默认值 `vth = 0.45 V`、`taperture = 200 ps`、`tedge = 50 ps`。本题沿用这些行为、默认值和端口顺序，并补齐合法域、同刻规则和验收尺度。

[v4 072 gold](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/072-aperture-delay-track-and-hold/evaluator/solution/sample_hold_aperture_ref.va) 第 25–43 行只作实现线索。它在忙时新沿覆盖待采时刻，这一行为本题不评。参考解另写，没有复制。v4 [公开激励](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/072-aperture-delay-track-and-hold/public/visible_test.scs)在沿后 40–140 ps 改变 `vin`，已能区分沿读入与孔径读入。本题的用例重新设计，不沿用其刺激表。

v1 `vbr1_l1_aperture_delay_track_and_hold` 的 dut、bugfix、tb 形式与 v4 072 同一内核 `track_hold_with_aperture_delay`。v1 [bugfix 题面](../../../../../historyref/v1/tasks/CT03_sampling_and_analog_memory/vbr1_l1_aperture_delay_track_and_hold/forms/bugfix/prompt.md)（`src-aed9a9062108`，即 C056-R1 主来源）的坏版在触发沿立即读入。v4 [1072 坏版](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/1072-aperture-delay-track-and-hold-bugfix/public/buggy_bundle/sample_hold_aperture_ref.va)仍延迟读入，但把值改成 `V(VDD,VSS) - vin`，属于另一故障。

### 同源关系与职责差异

| 题目或候选 | 来源组 | 职责 | 与本题的关系 |
| --- | --- | --- | --- |
| 首批30 [v2-spec-024](../../../v2-01/tasks/v2-spec-024-clocked-sample-and-hold/instruction.md) | `v4-024` | `V(CLK,VSS)` 上升穿越时立即读入；输出相对本地电源；初态 `OUT = VSS`，不采样初始输入 | 不同来源电路。本题读入未来孔径时刻的输入，初值取 `vin(0)`，电压对地，供电不影响输出 |
| R01 [r01-spec-ideal](../../../r01-sampling-01/tasks/r01-spec-ideal/instruction.md) | `r01-ideal` | 窗口打开时连续跟踪、关窗冻结、复位优先 | 本题没有跟踪窗口和复位，读入时刻由预约产生 |
| R01 [r01-spec-acquisition](../../../r01-sampling-01/tasks/r01-spec-acquisition/instruction.md) | `r01-basic` | 有限采集的连续动态 | 机制不同 |
| 第二批草稿 [v2-spec-071](../../../v2-01/tasks/v2-spec-071-acquisition-limited-sample-and-hold/instruction.md) | `v4-071` | 按固定 tick 以 `alpha` 比例采集，带 metric 输出 | 同属采样族，机制不同。其余第二批草稿未见孔径时刻责任 |
| 原 56 题 | 各自来源组 | 024、071 和 `v2-data-sampling-identification` 与采样相关 | 本次只读采样相关题面，未复审全部 56 题 |
| C056-R1 | `v4-family-072` | 规划为修复沿上读入的坏版：v1 坏版在沿上立即读入；任务说明举例的“沿上读入、延迟输出”同属此类 | 同源。本轮判断与本题实质重复，未建题包；用户 2026-10-28 确认不建（原 Q4）。设计说明见 `runs/t3-p0-pilot-20261027/r01-repair-aperture-delay/design-note.md`。两种坏版作为本题校准候选 `edge_sample_immediate`、`edge_read_delayed_output` 保存 |
| C067-S1（规划） | 未建 | 下垂前端，复用孔径预约 | 以后若复用本题 DUT、checker 或用例，应登记共享资产 |

本题只计 C056-S1 一项，不与 024、ideal、acquisition、071 重复计数。`v4-family-072` 是新组名，按 SOURCE_GROUPS 的 v4 家族命名，覆盖 v4 072 与同内核的 v1 形式；正式组名由主控登记时确定。

### 外部来源与许可

| 来源 | 版本 | 许可 | 用途 |
| --- | --- | --- | --- |
| [ADI MT-007](https://www.analog.com/media/en/training-seminars/tutorials/MT-007.pdf)，Walt Kester，“Aperture Time, Aperture Jitter, Aperture Delay Time—Removing the Confusion” | Rev.A 10/08；2026-10-27 取得的 PDF SHA256 `4eafce259297b697c578be11ab9313b7864c76a0276bcd9d140f23e6ac30afa0` | Analog Devices 版权教程 | 只引用工程定义：孔径延迟决定输入相对采样时钟沿的实际采样时刻，等价于延迟采样时钟；交织与同时采样中，孔径延迟差会使快速变化的输入产生误差。未复制文字或图 |
| [Arcadia-1/behavioral-veriloga-eval](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd) | 提交 `7b5616dc52195ec275ec6d21c71d7763613702cd` | 公开仓库，未见 LICENSE | 含 v3 081、v4 072/1072/180 孔径题的公开合同、gold 与负例；本仓库 historyref 是其迁入快照。未复制代码 |
| [phani91/Vams](https://github.com/phani91/Vams/blob/768e4c109703203c13108f77148f076078315952/Other/k_trackhold_t1.vams) | 提交 `768e4c109703203c13108f77148f076078315952` | 未见 LICENSE | 检索所得；其中 aperture 指电流型保持电容的采集窗口，概念不同，未使用 |
| [Verilog-AMS LRM](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（Accellera） | 2.4.0，2014-05-30；PDF SHA256 `621b2a1a3751e7685600f180fe8f362766fe13e952023ded3d7ae48314337c03`，与 U15-S1 在 2026-10-27 核验的文件相同 | 标准文本，版权所有 | 按 5.10.3.1 `cross()`、5.10.3.2 `above()`（初始化时表达式为正即触发）、5.10.3.3 `timer()`、4.5.8 `transition()` 写参考解和校准候选；4.5.8 中被打断过渡按原起点补全斜率的规则，用来确认被打断过渡的合法形状。未复制文字 |

记忆污染风险：历史合同与 gold 在上述公开仓库可检索。参考解独立编写，但“上升穿越预约、定时读入、transition 输出”是 LRM 的标准写法，与公开 gold 同构。评测时应考虑模型可能见过原题。本题的模块名、合法域、验收和用例已改变。

## 建模选择

### 建设决定

1. 模块名改为 `aperture_sample_hold`。原名 `sample_hold_aperture_ref` 的 `_ref` 是历史 gold 命名；按题包约定，新题用电路功能名。
2. 端口沿用 `VDD, VSS, clk, vin, vout`。全部电压对地，`VDD`、`VSS` 只作连接，不夹位、平移或缩放已读入值（决策卡）。时钟门限也对地，与 v4 一致。
3. 参数：`taperture > 0`、`tedge > 0`；`vth` 不另设区间，由合法激励保证穿越。
4. 触发与读入：上升穿越 `vth` 预约一次读入，读入时刻 `c_k = t_k + taperture`。下降穿越、读入时刻的 `clk` 电平、0 时刻已高的 `clk` 都不触发或取消读入。理由：孔径延迟按时钟沿定义（MT-007），与保持期间的时钟电平无关。用例含短于孔径的时钟脉冲，排除“读入时要求 clk 仍为高”的写法。
5. 触发间距：相邻触发间隔严格大于 `taperture`。这是用户“排除未完成采样的重叠触发”的直接表述，不再缩小。曾有建议把间距定为大于 `taperture + 2*tedge`，主控已拦下，本题未采用。输出过渡未完成时可以出现新读入，此时输出转向新值。
6. 恰在上次读入时刻再次触发：排除在合法输入外。理由：同刻事件的执行次序依赖仿真器，有两种合理读法，列为待确认 Q1。
7. 零孔径：排除，`taperture > 0`。理由：零孔径退化为触发沿读入，属于 024 的职责；同刻预约和读入的次序也依赖仿真器。列为待确认 Q2。
8. 读入瞬间输入不连续：只接受连续 `vin`（决策卡建议）。读入值是该时刻的瞬时值；陡坡由读入时间容差吸收，不另立左右极限规则。Spectre 的 PWL 源本身连续。
9. 输出过渡：读入前不动；读入后单调趋向新值，在 `tedge` 内到达，允许更快；被下一次读入打断时转向更新的值。依据决策卡“由到达时间、单调性和保持误差约束，不强制某个语言函数”。`tedge` 因此是上限，这一点列为待确认 Q3。
   - 被打断的过渡（fix-r1，F03）：验收除了单调和区间界，还检查方向。`c_k ± tau_t` 内的输出整体在新接受带之上超过 `epsilon_v` 时，之后不得上升超过 `epsilon_v`；整体在其下时不得下降。方向由新接受带和捕获时的输出范围决定，不用前后目标的大小代替。输出已在接受带附近时只要求单调。理由：题面要求“turns toward the newer held value”，原 checker 只查任一方向单调，朝反方向移动的输出能通过（审核 R03）。LRM 4.5.8 的补全斜率规则和各种更快的单调过渡都满足这一检查。
   - 初值（fix-r1，F05）：初值的保持区间总包含时刻 0。首次读入早于 `tau_t` 时，原 checker 的初值区间为空，错误初值可落在过渡区间界内而通过（审核 R05）。
10. 验收尺度：`epsilon_v = 2 mV` 沿用首批；读入时间容差 `tau_s = 2 ps`，输出时序容差 `tau_t = 5 ps`，观察网格 2 ps。读入带宽等于 `vin` 在 `c_k ± tau_s` 内的范围。用例在读入时刻附近的斜率不超过 1.5 mV/ps，读入带宽不超过 ±3 mV；典型错误相差至少 20 ps，在 1.33 mV/ps 斜率下约 27 mV。`tau_t` 只覆盖沿检测和网格误差，不允许输出延迟。这些数值是作者初值，待 Spectre 校准。
11. 输入域：`vin` 连续，取值在 -1 V 到 2 V；供电为任意连续电压。没有 reset、enable、忙标志或健康监控（决策卡）。
12. 不沿用 v4 对电流贡献、`ddt()`、`idt()` 的语法限制。理由同 024 迁移：验收只看外部行为，checker 不检查写法。
13. 用例共 7 个，公开 1 个。后两个是 fix-r1 新增的私有用例，公开用例与台架未变：

| 用例 | 参数 | 主要区分 |
| --- | --- | --- |
| `contract-base`（公开） | 默认 | 首次触发前输入变化；孔径窗口内和窗口后的输入变化；1.33 mV/ps 斜坡穿过读入时刻；80 ps 窄时钟脉冲；与上一触发相距 260 ps 的触发；长保持中输入继续变化 |
| `rails-and-supplies` | 默认 | 初值 1.05 V 高于 `VDD`；读入低于 `VSS`、高于 `VDD`；保持期间 `VDD`、`VSS` 阶跃 |
| `parameter-override` | `vth = 0.3`、`taperture = 450 ps`、`tedge = 100 ps` | 300 ps 慢上升沿；固定 200 ps 孔径、固定 0.45 V 门限的写法读到不同值；孔径窗口外的变化 |
| `short-aperture-burst` | `taperture = 60 ps`、`tedge = 20 ps` | 120 ps 间距连续触发；50 ps 时钟脉冲；固定 50 ps 过渡来不及到达 |
| `initial-high-clock` | 默认 | 0 时刻 `clk` 已高；1 ns 慢上升沿；斜坡穿过读入时刻 |
| `interrupted-transitions` | `taperture = 60 ps`、`tedge = 200 ps` | 捕获间隔 120 ps，介于孔径和 `tedge` 之间，包含输出尚未到达时再次捕获以及连续两次打断（按 LRM 补全斜率，实际打断发生在 680、1680、1800 ps 的捕获；其余捕获时过渡已完成）：先升、继续升、再降，以及降、升、降、升；每组最后一次捕获后有可观测的保持段。丢弃过渡中读入、先走完再转向、朝反方向移动的模型在此被拒（F03、F04） |
| `early-first-capture` | `taperture = 3 ps`、`tedge = 20 ps` | 首个触发在 1 ps，读入在 4 ps，早于 `tau_t`，初值只能由时刻 0 的采样判定；触发时 `vin` 还在斜坡上，沿读入的模型在此被拒（F05） |

14. 参考解 [solution/circuit.va](solution/circuit.va)：上升穿越记录读入时刻并置待读标志，`timer` 到时读入 `vin`，`transition` 输出。未用历史 gold 的变量名或注释。
15. 包装按首批30题的 Harbor 形式。`environment/Dockerfile`、两份 `.dockerignore`、`tests/Dockerfile`、`tests/test.sh`、`solution/solve.sh`、`harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、公开 `check.py` 与首批逐字节相同。题目判定写在 [tests/verify.py](tests/verify.py)，公开副本相同；它只读波形，不读候选源码或参考解。
16. 按 R01 ideal 的先例增加 [tests/calibration/](tests/calibration/README.md)：`mutants.py` 由参考解生成 19 个错误候选和 2 个正确替代实现，供以后 Spectre 校准；fix-r1 新增其中的 `drop_while_moving`、`finish_then_turn`、`init_mid_supply`。被拒矩阵另存为 [expected.json](tests/calibration/expected.json)，格式照 C264-S1，条目都是待 Spectre 校准的预期。

### 待用户确认

| 编号 | 选择 | 推荐（已写入题面） | 另一读法 |
| --- | --- | --- | --- |
| Q1 | 恰在上次读入时刻再次触发 | 排除在合法输入外 | 允许，并规定先完成本次读入、再预约下一次 |
| Q2 | 零孔径 | `taperture > 0` | 允许 0，规定等同触发沿立即读入 |
| Q3 | `tedge` 的含义 | 输出过渡的上限：读入前不动，单调，`tedge` 内到达，允许更快 | 像 024 那样要求完整的 `tedge` 过渡，同时检查离开旧值和进入新值的时刻 |

用户已确认（2026-10-28）：原 Q4（C056-R1 的处置）经总协调答复“全部按推荐”，采用推荐：不单独建题，坏版留作本题校准负例，C056 只计一题。另一读法（建成基础单模块修复题或系统修复题）不再执行，见 R1 设计说明。

## 待定项

未仿真：本机没有 Spectre，参考解、checker 和用例都没有 Spectre 运行证据。`results/reference.json` 与 `results/calibration.json` 尚未生成。

待办：

- Spectre 校准：参考解跑全部私有与公开用例；`tests/calibration` 的候选逐个过同一 checker，结果与 `expected.json` 比对；确认 `tau_s`、`tau_t` 能覆盖 `cross` 检测与 `strobeperiod` 网格；核对公开与私有用例一致。
- 记录 Spectre 的 `transition()` 待发与被打断过渡行为：`interrupted-transitions` 里输出尚未到达时的再次捕获（含 1680、1800 ps 的连续两次打断），记录它们是否按 LRM 4.5.8 的补全斜率规则运行；记录 `early-first-capture` 在 1 ps 触发、4 ps 读入时 `cross()` 与 `timer()` 的定位。
- 作者校准：按上述结果写结果文件，复核 2 mV、2 ps、5 ps 是否需要调整。
- 难度：决策卡判断 B–M，有偏易风险，未实测。

开发证据（证据目录 `runs/t3-p0-pilot-20261027/r01-spec-aperture-delay/`，待 Spectre 复跑，不作校准、录取或 EVAS 能力验收）。下面前三项是建题时的记录，针对前 5 个用例和修正前的 checker；fix-r1 的结果另列在最后：

- Python 合成轨迹：29 个行为模型（3 个正确、26 个错误）× 5 用例共 145 次判决，全部符合预期；另 4 项证据有效性控制都判为 checker 错误而非候选失败。
- EVAS `02dee32b`：参考解 6 个用例都过 a、b 阶段。`short-aperture-burst` 跑完 c 阶段并通过 checker；其余 5 个在 c 阶段停于 `source transition proof budget exhausted`（#270 NF-01），停在约 5.4–5.9 ns。起始模型在 a 阶段被拒：`module requires an analog block or child instances`。
- 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：参考解 6 个用例全部通过，只用规则网格行重判结论不变；起始模型因空模块被拒（`ERROR [rust_lowering]: model:0:aperture_sample_hold_Model:no_continuous_linear_ir`）。16 个错误候选在设计用例中都被拒；`alt_fast_output` 全部通过；`alt_delayed_clock` 因旧版不支持 `absdelay()` 未能运行，属于旧版局限。旧版只给点值，不做可信证明，结果可能不准也不报错。
- fix-r1（审核 `review-pilot-r1` 的 F03–F05、F12、F14、F15；证据目录 `runs/t3-p0-pilot-20261027/fix-r1/`，未仿真部分与旧版部分分开记录）：
  - Python 合成轨迹（未仿真）：建题时的 29 个模型加 fix-r1 的 5 个（`lrm_completion_slope` 为正确模型）在 7 个用例上共 238 次判决，全部符合事先写下的预期；审核复现 R03（被打断后朝反方向移动）与 R05（首次读入早于 `tau_t` 时的错误初值）在修正前通过、修正后被拒，对应的正确轨迹前后都通过。
  - 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 `6cb6fa7a`），待 Spectre 复跑：参考解 7 个私有用例和公开用例全部通过，只用网格行重判结论不变，前 5 个用例的结论与建题时相同；旧版的被打断过渡与 LRM 4.5.8 补全斜率规则一致。21 个校准候选中，除 `alt_delayed_clock`（旧版不支持 `absdelay()`）外的 140 次判定都与 `expected.json` 一致。`drop_while_moving`、`finish_then_turn` 在修正前的题包上 5 个用例全部通过；`init_mid_supply` 在修正前的 checker 下通过 `early-first-capture`，修正后被拒。
  - Docker：环境镜像与评分镜像各实际构建一次（`runs/t3-p0-pilot-20261027/fix-r1/scripts/docker_check.py`，照 C264-S1 的脚本，镜像标签 `vabench-p0-fix:`），7 项检查通过：评分镜像 `/app` 为空，缺交付物判 0 分，环境镜像 `/app` 等于 starter（含改过的公开 `verify.py`）且不含 `/tests`、`/solution`，参考解安装逐字节一致，缺后端时公开自测退出码 2，独立评分记 `infrastructure_error` 并给 Harbor 0 分。未执行电路。
