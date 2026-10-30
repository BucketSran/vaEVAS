# 来源与建设记录

2026-10-27 按 P0 试点新建，阶段 implementation，`pending = ["grading", "runtime"]`。本机没有 Spectre，本题未经 Spectre 仿真；EVAS 结果只作开发证据。本页不表示科学校准、模型试做、题目审核或正式录取。

## 行为依据

### 规划候选身份

| 项目 | 值 |
| --- | --- |
| task_id | `C056-S1`（规划候选，规格建模） |
| unit_id / primary_ref | `C056` / `C056` |
| 主来源 | `src-f0266764f7da`：v4 072 公开题面，SHA256 `86d79b3374d86cca66437fb0abf9d79e96cbab599244456f93b0b901e4016e37` |
| 规划登记 | [register.json](../../../../planning/history-candidates/register.json) 的 C056-S1：P0，结构估计难度 M，建设成本 L，作者工作为“补 taperture 合法域、未完成采样的再触发策略和同刻读入约定；不把延迟前采样加输出延迟当等价解” |
| 已确认边界 | [规划说明](../../../../planning/history-candidates/README.md#代表题已确认的改造边界)：首版公开限定最小触发间隔，排除上一采样未完成时再次触发；保留孔径内输入变化，验收延迟时刻实际读入 |
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

本题只计 C056-S1 一项，不与 024、ideal、acquisition、071 重复计数。`v4-family-072` 是新组名，按 SOURCE_GROUPS 的 v4 家族命名，覆盖 v4 072 与同内核的 v1 形式；正式组名由Benchmark 维护方登记时确定。

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
5. 触发间距：相邻触发间隔严格大于 `taperture`。这是用户“排除未完成采样的重叠触发”的直接表述，不再缩小。曾有建议把间距定为大于 `taperture + 2*tedge`，Benchmark 维护方已拦下，本题未采用。输出过渡未完成时可以出现新读入，此时输出转向新值。
6. 恰在上次读入时刻再次触发：排除在合法输入外。理由：同刻事件的执行次序依赖仿真器，有两种合理读法，列为待确认 Q1。【已定（用户 2026-10-29，决定单第 6 项）；即待确认清单第 1 项】
7. 零孔径：排除，`taperture > 0`。理由：零孔径退化为触发沿读入，属于 024 的职责；同刻预约和读入的次序也依赖仿真器。列为待确认 Q2。【已定（用户 2026-10-29，决定单第 6 项）；即待确认清单第 2 项】
8. 读入瞬间输入不连续：只接受连续 `vin`（决策卡建议）。读入值是该时刻的瞬时值；陡坡由读入时间容差吸收，不另立左右极限规则。Spectre 的 PWL 源本身连续。
9. 输出过渡：读入前不动；读入后单调趋向新值，在 `tedge` 内到达，允许更快；被下一次读入打断时转向更新的值。依据决策卡“由到达时间、单调性和保持误差约束，不强制某个语言函数”。`tedge` 因此是上限，这一点列为待确认 Q3。【已定（用户 2026-10-29，决定单第 6 项）；即待确认清单第 3 项】
   - 被打断的过渡（fix-r1，F03）：验收除了单调和区间界，还检查方向。`c_k ± tau_t` 内的输出整体在新接受带之上超过 `epsilon_v` 时，之后不得上升超过 `epsilon_v`；整体在其下时不得下降。方向由新接受带和捕获时的输出范围决定，不用前后目标的大小代替。输出已在接受带附近时只要求单调。理由：题面要求“turns toward the newer held value”，原 checker 只查任一方向单调，朝反方向移动的输出能通过（审核 R03）。LRM 4.5.8 的补全斜率规则和各种更快的单调过渡都满足这一检查。
   - 初值（fix-r1，F05）：初值的保持区间总包含时刻 0。首次读入早于 `tau_t` 时，原 checker 的初值区间为空，错误初值可落在过渡区间界内而通过（审核 R05）。
10. 验收尺度：`epsilon_v = 2 mV` 沿用首批；读入时间容差 `tau_s = 2 ps`，输出时序容差 `tau_t = 5 ps`，观察网格 2 ps。读入带宽等于 `vin` 在 `c_k ± tau_s` 内的范围。用例在读入时刻附近的斜率不超过 1.5 mV/ps，读入带宽不超过 ±3 mV；典型错误相差至少 20 ps，在 1.33 mV/ps 斜率下约 27 mV。`tau_t` 只覆盖沿检测和网格误差，不允许输出延迟。这些数值是作者初值，待 Spectre 校准。
11. 输入域：`vin` 连续，取值在 -1 V 到 2 V；供电为任意连续电压。没有 reset、enable、忙标志或健康监控（决策卡）。`clk` 到达 `vth` 必定穿过、不触碰后返回，相邻两次穿越之间离 `vth` 至少 50 mV（2026-10-29 修正 r7b 补写，见该节）。
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

### 待用户确认（三项都已定，用户 2026-10-29）

下面三项原为“待用户确认”，用户 2026-10-29 已按推荐定：Q1–Q3 依次是待确认清单第 1–3 项，都属决定单第 6 项。推荐、另一读法与理由的原文保留，2026-10-29 修正 r7b 只改状态（上文建设决定第 6、7、9 条同样只补了状态）。

| 编号 | 选择 | 推荐（已写入题面） | 另一读法 |
| --- | --- | --- | --- |
| Q1 | 【已定（用户 2026-10-29，决定单第 6 项）】恰在上次读入时刻再次触发 | 排除在合法输入外 | 允许，并规定先完成本次读入、再预约下一次 |
| Q2 | 【已定（用户 2026-10-29，决定单第 6 项）】零孔径 | `taperture > 0` | 允许 0，规定等同触发沿立即读入 |
| Q3 | 【已定（用户 2026-10-29，决定单第 6 项）】`tedge` 的含义 | 输出过渡的上限：读入前不动，单调，`tedge` 内到达，允许更快 | 像 024 那样要求完整的 `tedge` 过渡，同时检查离开旧值和进入新值的时刻 |

用户已确认（2026-10-28）：原 Q4（C056-R1 的处置）经项目协调方答复“全部按推荐”，采用推荐：不单独建题，坏版留作本题校准负例，C056 只计一题。另一读法（建成基础单模块修复题或系统修复题）不再执行，见 R1 设计说明。

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

## 2026-10-29 修正 r7b（p0-fix-r7b）

依据：扫描 B 报告第 4 节 (补p)、(t)、(k) 三项与第 10 节（项目协调方 2026-10-29 批准本轮）；项目协调方的决定：补p 照 C061 补一句与台架判定，逻辑输入取 50 mV；(t) 补 A 收窄版那句与台架判定；P0 各题写入标准审核定的容差行；用户 2026-10-29 答复的决定单。改前改后的 sha256、脚本、命令与退出码见本轮记录 runs/t3-p0-build-20261027/p0-fix-r7b/disposition.md（不入库）。本节的检查都**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 题面（instruction.md 第 23 行，合法输入一段）。原句“`clk` starts at a level different from `vth` and passes through `vth` without stopping on it.”改为三句：“`clk` starts at a level different from `vth` and never rests at `vth`. When `clk` reaches `vth`, it always crosses it; it never touches `vth` and returns to the same side. Between two successive crossings of `vth`, `clk` moves at least 50 mV away from `vth`.”
   - 前两句是决定单第 4 项（用户 2026-10-29 定 A 收窄版）的写法，与 C176、C109 等题的句子相同；原句的“不停在 `vth` 上”由“never rests at `vth`”保留。
   - 第三句补扫描 B 第 4 节 (补p) 的缺口：原合同对 `clk` 两次穿越之间离 `vth` 有多远没有下限，合法激励可以有离 `vth` 不到 `cross()` 表达式容差的返回根。按标准审核 SL-DEC-20261029-05，这样的两根报一次、报两次都合 LRM 5.10.3.1，触发次数就不能评分。参考解的 `cross(V(clk) - vth, +1)` 没写容差，Spectre 的缺省 time_tol 是 1 s，实际只看 expr_tol。离 `vth` 至少 50 mV 时，两根之间的偏离远大于 expr_tol（第 3 条），两根都必须报，触发照常评分。与 C061 修正 r2 同一做法。
   - 其余句子不变。现有 7 个私有用例与公开用例都满足新的三句（第 3、5 条）。
2. checker（`tests/verify.py` 与公开副本逐字节相同）。触发仍由原来的 `rising_crossings` 取，判分代码不变；新加的只是台架检查，在“`clk` starts at vth”之后：
   - `threshold_crossings` 按保存行把 `clk` 与 `vth` 精确比较，恰在 `vth` 上的行不属于任何一侧。连续两行在 `vth` 上（停在门限上），或一行在 `vth` 上而前后两行在同一侧（触碰后返回），都 `raise ValueError`；单独一行在 `vth` 上、前后分处两侧，是一次穿越；记录末尾单独一行在 `vth` 上，按到达方向算一次穿越。做法照 C176 等题统一的穿越规则，另把触碰也报成台架错误。
   - 对每一对相邻穿越（两个方向都算），取两者之间各保存行上 `|V(clk) - vth|` 的最大值，小于 50 mV − 1 mV = 49 mV 时 `raise ValueError`。余量 1 mV：受约束的量只涉及一个保存节点 `clk`（题面写明电压都对地，`vth` 是参数），按样板每个保存样本可偏离 1 mV，与 C061 修正 r2 的算法相同（C061 涉及 `clk`、`vss` 两个节点，取 2 mV）。所以合法台架上 `clk` 采样偏 1 mV 也不会误报；通过检查的台架，两根之间的真实偏离至少 48 mV，仍是第 3 条 expr_tol 的 8e4 倍以上。
   - 这些 ValueError 由 `v2_runtime.py` 记作 checker_error（不判分、不算候选失败），与其他台架检查同一路径。
   - 局限：只读保存行。极值落在两行之间时会被低估，低估量没有上限；正好落在两行之间的触碰也看不到（行上都不等于 `vth`）。所以台架的极值要放在平台或保存行上。现有用例的极值都在平台的保存行上：2 ps 网格上按网表重放的行与按折点精确求出的最大偏离逐对相同（第 5 条的合成控制 A 用的就是这样的行）。
3. expr_tol 核对（标准审核条件：50 mV 要大于每份网表最宽的缺省 expr_tol，即 1e-9 + reltol_eff·max|expr|；reltol_eff 计入 errpreset 倍数，最宽读法取 options 与瞬态实际值中较大的；脚本 runs/t3-p0-build-20261027/p0-fix-r7b/scripts/check_exprtol_r7b.py，退出码 0）。表达式取 `V(clk) - vth`，`clk` 的 PWL 按 binary64 读入后精确求值：
   - 9 份网表（7 个私有用例、公开 `cases.json`、`visible_test.scs`）写入容差后 reltol 为 1e-6、errpreset 为 moderate，最宽 expr_tol 最大 0.601 µV（`parameter-override`，`vth` 0.3 V，max|expr| 0.6 V），50 mV 是它的 8.32e4 倍以上；
   - 缺省容差对照（去掉容差行与 tran 的补写，reltol 1e-3）最大 0.600 mV，50 mV 仍是 83.3 倍以上；
   - 相邻两根之间的最小偏离 0.3 V（`parameter-override`），其余用例 0.45 V；t = 0 离 `vth` 至少 0.3 V；没有触碰、平台或停在门限上的点。
4. 容差写入（第 (ii) 类，扫描 B 第 4 节 (k)；标准审核 2026-10-29 给的值）。9 份网表都在 tran 行之前另起一行写 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`，tran 行末补 `errpreset=moderate strobeoutput=strobeonly`，其余字节不变。8 个用例网表（7 个私有、1 个公开）写入后再加执行路径一行，与预校准包 P0PC-must-01（包 spectre-P0PC-must-01-v1，结果包 sha256 `56bb45ddcc96029e2ee7bd556bdd9b26db70f2186f91bff0653353d43b837ad6`，已核收）的同例参考解作业网表逐字节相同；`visible_test.scs` 与公开用例只差 include 路径。所以已核收的结果仍然作数，激励没有变，本题不需要新的 Spectre 作业。
5. 复核（都未仿真）：
   - 合成控制 A：建题时的 29 个 Python 模型、fix-r1 的 5 个模型在 8 个用例上，加 4 个证据有效性控制，共 276 次判决；改前改后的 checker 给出的整份结果（状态、判决、误差、检查数、失败数）逐个相同，不同的 0 个。
   - 合成控制 B（新台架检查；每个折点都在保存行上）：`clk` 在两根之间只离开 40 mV、48.9 mV 时报台架错误，离开 60 mV、49.1 mV 时通过；高于 `vth` 只到 40 mV 后返回报错、60 mV 通过；停在 `vth` 上两行报错，从下方、从上方触碰后返回都报错；正好穿过一行恰为 `vth` 的点、记录末尾恰到 `vth` 都照常通过。恰好 50 mV 与 49 mV 两个十进制电平在 binary64 下离 `vth` 为 0.04999999999999999 V 与 0.04899999999999999 V，前者通过、后者报错，结果取决于舍入，只作平局诊断。改前的 checker 对这 14 个台架都照常判分。
   - 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：建题与 fix-r1 存档的 163 条旧版波形（参考解与全部校准候选），全部行与只用网格行各判一次，共 320 次；改前改后判决逐个相同，没有新的台架错误。本轮没有新的旧版运行。
   - P0PC-must-01 已核收的 16 个参考解作业（带容差与缺省容差两组，私有与公开用例）用改后的 checker 重判，全部通过，判决、误差与改前逐个相同。新检查只读 `vsource` 驱动的 `clk`，同一用例各作业的 `clk` 行相同，候选作业不需另判。
6. 决定单状态：建设决定第 6、7、9 条与“待用户确认”一节的 Q1–Q3（待确认清单第 1–3 项）改为已定（用户 2026-10-29，决定单第 6 项），理由原文不动。
7. 参考解、起始文件、校准候选与 `expected.json` 都没有改；校准 README 补了新台架检查与本轮复核的一段。

## 2026-10-30 修正 v417

依据：只读扫描 v417-bench-scan-r1 列的本题 3 处台架义务检查（C056-02、C056-03、C056-04，Benchmark 维护方已核实）；网表约定清单第 4.21 版（sha256 前 8 位 `7d511985`）第 0.5 节第 20 条，第 4.17–4.21 版新增的各点逐条核过（第 4 小节）；项目协调方 2026-10-30 的三项决定：做法甲的范围是起点、停留、碰到、最小偏离四项一起按网表激励定义判，时序守卫、范围与数值 δ 类检查不动；“碰到”在 14 道题里一律报台架错误；strobeonly 不算满足条件 3，要改的清单不变。另据 Benchmark 维护方 2026-10-30 对本轮第 1 次停下的决定（重判的写法与题面依据，第 5、7 小节）。改动文件改前、改后的 sha256，脚本、命令与结果见 `runs/t3-harbor30-20261027/v417-bench-fix-r1/disposition.md`（不入库）。本节的检查都**未仿真**：没有运行 Spectre、EVAS（含旧版）、模型或 Docker；合成控制是 Python 合成行；重判只读已交回的 Spectre 波形。前面各节原文不改。

改动范围：两份 checker（`tests/verify.py` 与 `environment/starter/testbench/verify.py`，改后逐字节相同，sha256 `f465e10b70116465f3bf7a8f3d6a71c315875fcce782acddcc9327c713d6d082`，改前 `f1f417c6…`）与本文件。题面、参考解、用例网表、`tests/calibration/`、`v2_runtime.py`、`task.toml`、`cases.json` 都没有改；判分逻辑、时序守卫、范围检查与数值 δ 类检查不变。

### 1. 改了什么（编号照扫描）

- **C056-02**（evaluate 第 103–104 行）：t = 0 那一行 `clk[0] == vth` 报台架错误 → 按 `clk` 的定义判起点是否恰在 `vth` 上。
- **C056-03、C056-04**（`threshold_crossings` 第 47–54 行，evaluate 第 111 行调用）：保存行上相邻两行恰为 `vth`（停留），或单行恰为 `vth` 而前后两行同侧（碰到），报台架错误 → 按定义判。碰到原来就报台架错误，不变。
- 随同改（项目协调方决定第 1 项，最小偏离）：修正 r7b 加的“相邻两次穿越之间离 `vth` 至少 50 mV”（evaluate 第 105–115 行，取两次穿越之间各保存行的最大偏离）→ 按定义判，报错门槛仍是 50 mV − `SAMPLE_SLACK` = 49 mV。`threshold_crossings` 只给这项检查提供穿越，随之删去。
- 触发仍由 `rising_crossings` 从保存行取，判分代码不变。

### 2. 怎么判（做法甲）

- 用哪份定义：checker 读所判用例自己的网表 `case["netlist"]`。它就是 `v2_runtime.py` 写成 `tb.scs` 交给仿真器、跑完再核 sha256 的那一份，被改动就记 evidence_error。私有用例取 `tests/cases.json`，公开检查取 `environment/starter/testbench/cases.json`；`visible_test.scs` 不经 checker 判，本轮用同一读法核过它也读得出。
- 受查量：`clk` 对 `vth`。`check_stimulus` 放在原来起点检查的位置，在取触发与判分之前。
- 定义取值：受查量由它涉及的节点自地起串着的 vsource 得出，在 [0, stop]（stop 取网表 tran 行）上于各源的定义点之间是直线：PWL 用各点的时刻与值，pulse 用 val0、val1 与四个拐角（按周期重复），dc 源用 dc 值，sine 用 sinedc ± ampl 与起点值。本题受查量涉及的源：PWL 9 个。
- 在门限上：定义点的值与门限按写出的十进制精确相等，或各自舍成 binary64 后相等，任一成立即算。节点由几个源叠成时，“精确和舍入一次”与“各源先舍成 binary64、自地起逐运算相加”两种值都算。
- 判法（都是 `raise ValueError`，`v2_runtime.py` 记作 checker_error：该例不判分，不算候选失败）：
  - 起点：t = 0 的定义值在门限上，报 “starts on …”（题面只要求起点不同于 `vth`，没有起点余量）；
  - 停留：相邻两个定义点都在门限上，报 “rests on …”；
  - 碰到：一个定义点在门限上、前后两侧在同一侧，报 “touches … and returns to the same side”；stop 时刻恰到门限算到达方向的一次穿越，不报；
  - 最小偏离：相邻两次定义穿越之间，各定义点离门限的最大偏离小于 0.049 V（`CROSSING_EXCURSION` − `SAMPLE_SLACK`，50 mV − 1 mV），报 “moves only … away from …”；
  - 读不出：受查量涉及的节点上的全部 vsource 都要读得出，在差里抵消的源也不例外。数字只写字面量，可带一个比例符号；不写参数名、表达式、行尾注释、单位，也不写指数后接比例符号。pulse 写全六个参数，rise、fall 大于 0；PWL 时刻严格递增；sine 写 sinedc、ampl、freq，不带 delay、damp。读不出报 “cannot read the stimulus definition of …”；受查节点不由用例网表的 vsource 驱动，报 “… is not driven by a voltage source of the case netlist”；网表里有只差大小写的节点名也报台架错误（保存信号按小写配对，Spectre 区分大小写）。
- 穿越：触发仍由 `rising_crossings` 从保存行取，判分代码不变。保存行恰在 `vth` 上（例如模块在同一输入、同一门限上求根时写下的根处行）不再引起台架错误。

### 3. 余量（数值未改）

- 最小偏离：`SAMPLE_SLACK` = 1 mV 仍从题面的 50 mV 中扣除，报错门槛 49 mV 不变。它原来的理由是每个保存样本可偏离源 1 mV、保存行会低估两行之间的极值；按定义判以后定义值是精确的，这个理由不再适用。现在它只是容让：定义上只离开 49 mV 到 50 mV 的激励已在题面合法域之外，但不报台架错误。常量注释照此改写，数值未改。
- 起点：题面只要求起点不同于 `vth`，checker 只查恰在 `vth` 上，没有余量。
- 改不改这些数值由项目协调方另定，本轮不改。

### 4. 清单第 4.17–4.21 版各点（第 6 条）

| 点 | 本题 | 怎么处理 |
| --- | --- | --- |
| 做法甲（v4.17） | 适用 | 受查量（`clk` 对 `vth`）的起点、停留、碰到、最小偏离按用例网表的 vsource 定义判，不读保存行（第 2 小节）。 |
| “在门限上”的读法（v4.18、v4.20） | 适用 | 门限 `vth` 是用例参数，按写出的十进制与 binary64 两种比；门限不是表达式。合成控制另做了只在 binary64 下才在门限上的变体（第 6 小节）。 |
| 和、差与叠放（v4.18、v4.20） | 不适用 | 受查量是单个节点 `clk` 对地；没有叠放源（本题网表里 `clk` 由一个 vsource 直接对地驱动）。代码对叠放照两种舍入处理。 |
| 读得出（v4.18、v4.20） | 适用 | 本题 9 份网表（私有 7、公开 `cases.json` 1、`visible_test.scs` 1）共 36 个 vsource，都读得出，与扫描第 1 节一致；受查量涉及的源 9 个（PWL 9 个），都读得出。读不出报台架错误，该例不判分。 |
| 比较式的不同写法（v4.20） | 不适用 | 一种写法：checker 比 `V(clk)` 与 `vth`，参考解在 `V(clk) - vth` 上求根；binary64 下 `x - vth` 为 0 与 `x == vth` 等价，不另算。 |
| 另一个受查量（v4.21） | 不适用（没有新增受查量） | 参考解 `aperture_sample_hold` 只在 `cross(V(clk) - vth, +1)` 上求根，就是受查量本身。没有台架模块：`cases.json` 不带 support 源码，公开目录没有 `.va`。候选的写法不在此列（合成控制 B 仍按各候选自己的事件插了根处行）。 |
| 模块驱动的受查信号（v4.17–v4.20） | 不适用 | 受查信号都由用例网表的 vsource 直接驱动，9 份网表逐份核过，不由 vsource 驱动的 0 个；没有台架模块，也没有按候选输出生成的受查信号。 |
| 条件 3 与 strobeonly（决定第 3 项） | 适用 | 本题 9 份网表都写 `strobeoutput=strobeonly`；strobeonly 不算满足条件 3，照改。 |
| 碰到（决定第 2 项） | 适用 | 改前已按保存行报台架错误，现在按定义报。 |

### 5. 题面依据（不改题面）

- 起点、停留、碰到、最小偏离：instruction.md 第 23 行 “`clk` starts at a level different from `vth` and never rests at `vth`. When `clk` reaches `vth`, it always crosses it; it never touches `vth` and returns to the same side. Between two successive crossings of `vth`, `clk` moves at least 50 mV away from `vth`.”
- 读不出、不由 vsource 驱动：这两种台架错误都是本方网表的失败保护，候选改不了网表，也就触发不了；清单第 20 条写明该例不判分。题面第 30 行 “A missing simulator, or any other execution or infrastructure failure, is not evidence that the model behavior is wrong.”

### 6. 合成控制（未仿真）

- 做法：合成 strobe 行。网表定义在每个 strobe 时刻精确取值、舍成 binary64；候选输出一律给 0 V（沿用扫描 `rowsim.py` 的做法），所以判分结果多为失败，只用来比改前、改后两版 checker 的整份判决与台架错误。导入的是本轮 scratch 下的 checker 副本，字节码关闭。
- A 现有用例网表：9 份网表各两组行，一组只有 strobe 行，一组另在每个受查量的每个定义穿越处插一行恰在门限上的根处行（共 89 行）。18 次判决：新 checker 都不报台架错误，与改前的 checker 整份判决逐个相同（18/18）。
- B 候选：扫描列出的 21 个候选（`tests/calibration/mutants.py` 在本轮 scratch 生成，不在题包里生成），按各自的 `cross()`、`above()` 事件映射到台架节点，在每份网表上插它们自己的根处行（36 组不同的行，共 969 行）。改前、改后判决逐个相同，新 checker 不报台架错误（21/21）。
- C 变体（在 `contract-base` 上改 `clk` 的定义；每个变体事先写下预期），12/12 符合预期：
  - `clk` 起点按十进制恰在门限上：报 “starts on”
  - `clk` 起点只在 binary64 下恰在门限上：报 “starts on”
  - `clk` 在 1.0755e-08 s 处按十进制停在门限：报 “rests on”
  - `clk` 在 1.0755e-08 s 处只在 binary64 下停在门限：报 “rests on”
  - `clk` 在 1.0755e-08 s 处按十进制碰到门限：报 “touches”
  - `clk` 在 1.0755e-08 s 处只在 binary64 下碰到门限：报 “touches”
  - `V_CLK` 在 2e-09 s 与 2.5e-09 s 两次穿越之间只离门限 0.0489 V：报 “moves only”
  - `V_CLK` 在 2e-09 s 与 2.5e-09 s 两次穿越之间只离门限 0.0491 V：不报台架错误（照常判分）
  - `clk` 的源有一个值写成参数名 `vlo`：报 “cannot read”
  - `clk` 的源有一个值写成表达式 `0*1`：报 “cannot read”
  - `clk` 的源有一个值带单位 `0V`：报 “cannot read”
  - `clk` 不由 vsource 驱动：报 “is not driven”

### 7. 已交回作业的重判（未仿真）

- 范围：14 道题全部已交回的 Spectre 作业，以各包 `jobs.json` 的 meta.task 为准，只数正式打包目录（不数 scratch 下的试做包）：34 包 3852 个作业，判了 3848 个，未判 4 个（C266 的执行错误，没到 checker）。
- 做法：每个作业用它发出时的快照判，用例取快照里的那份，只把 checker 换成新版，与原判逐个比；判决相同指 status、passed 与台架错误的有无都相同。P0PC 里有些作业跑的是后来改过的旧网表，只用来比两版 checker，不对现行题包评。快照里的旧 checker 重判，与预读记录的原判逐个相同（status、passed、整份判决 sha256），工具与环境没有问题。
- 结论：本轮改动没有改变任何作业的判决（new 与改前 checker 3848/3848 相同）；与打包时的原判比，3708 相同，140 不同，来自 p0-fix-r9 已记录的激励与规则改动。
- 不同的 140 个全是 U15（`r04-spec-delay-pulse-hold`）：spectre-P0PC-must-01-v1 10、spectre-P0PC-opt-01-v1 26、spectre-P0PC-rec-03-v1 84、spectre-P0PC-rec-04-v1 20。
- 本题：spectre-P0PC-must-01-v1 16、spectre-P0PC-opt-01-v1 21、spectre-P0PC-rec-01-v1 140、spectre-P0PC-rec-02-v1 7，共 184 个。new 与改前 checker 整份判决 184/184 相同。与原判比 status、passed 与台架错误的有无 184/184 相同，整份判决 sha256 也相同。

### 8. 前面各节的相关句子

- 建模选择第 15 条（第 83 行）“它只读波形”：checker 现在也读用例记录里的网表（vsource 定义与 tran 行的 stop），仍不读候选源码或参考解。
- 修正 r7b 一节第 2 条第 128、129、131 行（`threshold_crossings` 按保存行判停留与碰到、按保存行判最小偏离及余量 1 mV 的理由、“只读保存行”的局限）：自本节起按定义判。第 130 行（记作 checker_error）仍成立。
