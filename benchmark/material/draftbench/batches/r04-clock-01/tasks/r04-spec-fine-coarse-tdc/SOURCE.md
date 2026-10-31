# 来源与验收状态

## 行为依据

规划候选身份：`task_id` U16-S1，`unit_id` U16，`case_anchor` C295，来源 `src-145a2fa31e0f`，`primary_ref` C295，动作 S（spec-modeling），家族 R04，优先级 P0，结构难度 M-H，建设成本 M。登记见[规划登记](../../../../planning/history-candidates/register.json)中的 U16-S1 条目，来源身份见同目录 [sources.json](../../../../planning/history-candidates/sources.json)，规划说明见[候选说明](../../../../planning/history-candidates/CANDIDATES.md#u16-s1)。登记要求：
- reuse：start/stop、粗计数、stop 细时间与 valid 接口；
- author_work：补起点和终点两端细时间的量化关系，定义参考预热、码饱和/无效、同刻事件及输出协议；
- solver_work：建立粗计数与细残差一致的模型，处理跨周期边界和一次测量的资格状态；
- acceptance：同一时间间隔平移到不同参考相位时，重构值只差规定的量化；跨周期相邻的输入不多算也不少算一周期；
- rollback：若仍只输出 stop 在周期内的相位、不重构有效间隔，退回扩展素材；
- spec_plan：采用公开的理想量化模型，分别记录 start 和 stop 相对参考的细时间，再与完整周期组合；明确同参考周期、细时间借位、参考预热、溢出、超时和复位中断。

主来源是 2026-10-22 历史净化修订后的 v4:325 题面，sha256 `b1e74b82b4634932305caf56968d5dbc1677940314933b8c6a64df48c24d29b1`。规划登记标为 local-only，原件在主工作区的 `runs/historical-purification-20261022/improve-packs/finecoarsetdcencoder/OUTPUT/instruction.md`，不在本工作树。修订只比发布版 [v4:325 题面](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/325-fine-coarse-tdc-encoder/public/instruction.md)多一条 `fine_metric` 公式（缺陷 D1）。原题沿用的事实：
- start 上升沿武装测量；数已计入的 `ref_clk` 上升沿，直到第一个 stop 上升沿；粗码 4 位；stop 后 `valid` 有效；复位清零；
- stop 细时间是 stop 在参考周期内的位置：从最近一个已计数参考沿到 stop 的时间，除以最近两个已计数参考沿的间隔；
- 参数默认值 `vdd = 0.9 V`、`vth = 0.45 V`、`tr = 200 ps`。

原 gold（[coarse_counter](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/325-fine-coarse-tdc-encoder/evaluator/solution/coarse_counter.va)、[fine_residual_metric](../../../../../historyref/v4/release/benchmarkv4-r53/tasks/325-fine-coarse-tdc-encoder/evaluator/solution/fine_residual_metric.va)）只量 stop 一端，`fine_metric` 是模拟代理量。它没有用 start 相位重构间隔，粗码在 15 饱和但不报溢出，start 只清 `valid` 和细量、不清粗码；少于两个参考沿时分母用初值 1.0 s。原 checker（修订包中的 `check_v4_325_fine_coarse_tdc_encoder`）有以下局限：
- 只在 `valid` 上升那一行检查，粗码和细量各允许错 1 次，细量容差 0.12 V；
- 台架只有三次测量，`ref` 周期固定 6 ns，粗码只出现 2 和 3；
- 修订包的 DEFECTS 还指出：复位没有有效激励（D2）、首次 start 与 enable 同刻、参数从不改写。
本题不继承它的判据和成绩，这些缺口就是本题要补的。

历史 Spectre 证据：按样板第3a节查了本机 `legacy/behavioral-veriloga-eval/results/`（含 `_local/v3_skeleton_dual_parity_cache/hidden/` 与各 `v3_spectre_audit*` 目录），没有 v4:325 或同类细粗 TDC 的 Spectre 运行；缓存里的 `325-slew-asymmetric-rise-fall` 是 v3 编号的另一道题。

外部依据：
- Nutt 法（插值式 TDC）：粗计数加起止两端细时间，`T = n*T0 + T_start - T_stop`。依据 [Wikipedia Time-to-digital converter，修订 1375889752](https://en.wikipedia.org/w/index.php?title=Time-to-digital_converter&oldid=1375889752)（CC BY-SA 4.0，只引用，没有复制文字）。该页引用 Kalisz、Pawlowski、Pelka 1987 年 J. Phys. E 20(11) 1330–1341 页和 Nutt 等人 1976 年的美国专利 3983481。本题用与之等价的"距上一个参考沿的相位"写法 `D = 16*N + q_e - q_s`；Nutt 原式写法是校准候选 `alt_nutt_complement`。
- [Accellera Verilog-AMS LRM 2.4.0](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)（2014-05-30）：
  - §5.10.3.1 `cross()` 的时间容差，t = 0 不产生事件；
  - §5.10.3.3 `timer()`；
  - §4.5.8 `transition()` 过渡被打断时的完成规则；
  - §4.2 `floor()`。
  只引用定义，没有复制文字。

外部来源与许可证另列在 sources.json（`runs/t3-p0-build-20261027/r04-spec-fine-coarse-tdc/sources.json`）。GitHub 代码检索只找到 Arcadia 历史题、本仓库自己的首批候选，以及一份没有 LICENSE 的延迟线 TDC（EECS251B 课程项目，只读）。arXiv 检索到的 FPGA/ASIC TDC 论文摘要没有给出组合公式。没有可复制的宽松许可代码，参考解是作者按新合同自写的。

记忆污染风险：低到中。原 v4:325 的题面、gold 和台架在公开仓库 [Arcadia-1/behavioral-veriloga-eval@7b5616dc](https://github.com/Arcadia-1/behavioral-veriloga-eval/tree/7b5616dc52195ec275ec6d21c71d7763613702cd/benchmark-vabench-release-v4/release/benchmarkv4-r53/tasks/325-fine-coarse-tdc-encoder) 中，与本仓库副本的 git 对象一致（题面 `e8ddbe07`，`fine_residual_metric` `558d757a`）。该仓库没有 LICENSE 文件。新合同改了模块名、接口、两端细时间组合、量化、预热和溢出，原 gold 不能通过。Nutt 公式本身是教科书内容。

同源与职责，均不重复计数：
- 首批30题 [v2-integrate-case0007-adpll-fine-tdc](../../../v2-01/tasks/v2-integrate-case0007-adpll-fine-tdc/instruction.md)（`tiny-tapeout-adpll`）的 `fine_tdc` 量的是 ADPLL 中 ref 与 fb 两沿的相位差：
  - 250 ps 步长，四舍五入，饱和到 ±31，没有粗计数，用作环路的鉴相器；
  - 本题量 start 到 stop 的时间间隔，由粗计数和两端细时间组合，职责是粗细分解与两端一致，不是闭环控制。
- 第二批草稿 [v2-test-time-protocol](../../../v2-01/tasks/v2-test-time-protocol/instruction.md)（`v4-346`，与规划 C328-S1 同源）是 8 位 start–stop 时钟沿计数器，有重新武装、锁存和第 256 沿溢出，没有细插值。
  - 登记的 difference 写明：C328/C333 是 start–stop 事件测量；本题的新职责是粗细分解和两端细时间的一致性，不是增加计数位宽。
  - 本题的输出协议（start 清结果并重新武装、测量中不显示计数、溢出时置饱和码与标志、未武装的 stop 被忽略）有意与该题一致，避免同族出现冲突的协议。
- 规划中的 U13-T1（对外部时钟选窗口测频）与 C328-S1、C333 尚未另建题。
- 原56题：除上述各题外，没有以 v4:325 为来源的题。旧41题中的 `integrate-tdc-measurement-chain` 直接按时间戳量化，没有参考时钟，不在草稿分母内。
- P0 试点 [r04-spec-delay-pulse-hold](../r04-spec-delay-pulse-hold/instruction.md)（U15-S1）同在本批，是可编程延迟单元，与本题无同源关系。
- R01：采样家族，无同源。
- 本题 `source_group` 取新组名 `v4-325`；SOURCE_GROUPS 中原无此组，也没有 `v4-family-325`。

## 建模选择

每条决定都附理由。标"待用户确认"的条目会改变范围、科学合同或评分口径，而且有两种以上合理读法；已先按推荐写进题目。原标"待用户确认 1–4"的第 1、3、4、5 条（待确认清单第 27–30 项）已定（用户 2026-10-29，决定单第 6 项），都按推荐，2026-10-29 修正 r7b 只改了状态。

1. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 1”，即待确认清单第 27 项】接口改为单模块 `fine_coarse_tdc(start, stop, ref_clk, rst, code_7..code_0, valid, overflow)`。
   - 输出 8 位组合间隔码 `D`（`code_7` 为最高位）、`valid`、`overflow`；
   - 删去原接口的 `enable`、`vss`、`vcm`、`fine_metric` 和分开的 `coarse_3..coarse_0`；
   - 原题要求的三个模块边界也不再要求，解题者可以在同一文件内自定义辅助模块。
   - 理由：rollback 要求模型自己重构有效间隔，组合码直接检验粗细一致和借位；`enable` 与复位职责重复；`vcm` 在原 gold 中从未使用；原 family_spec 的辅助模块端口只是占位。
   - 另一种读法是保留粗码，另加 start、stop 两个细码，由 checker 重构。这样借位不由模型负责，"多算一周期"的错误也看不到。
   - 推荐组合码。
2. 细码定义：事件距最近一个参考上升沿（含同刻的沿）的时间，以 `T_ref/16` 为步长截断，取值 0–15。`N` 是 start 之后、到 stop 为止（含同刻）的参考上升沿数，`D = 16*N + q_e - q_s`。
   - 这是 Nutt 法的等价写法：`D` 与 `16*(t_stop - t_start)/T_ref` 之差小于 1，同一间隔在不同相位只差一个细步；
   - 同一周期内（`N = 0`）`D = q_e - q_s ≥ 0`；`q_e < q_s` 时向粗计数借位；
   - "同刻沿算在事件之前"与截断一致，使相位落在 0, 1)。
3. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 2”，即待确认清单第 28 项】量化：每周期 16 个细步，截断，细步跟随实测的参考周期。`T_ref` 不是参数，模型要从 `ref_clk` 得到它，终评用 4、3.2、2.4 ns 三种周期。
   - 理由：原题的 stop 细时间就用实测周期归一；周期不设参数，写死周期的模型（`fixed_period_4ns`）会在另外两种周期下被拒。
   - 另一种读法是按固定时间步长（例如参数 `tlsb = 250 ps`）量化，参考周期设为参数并要求是步长的整数倍，这接近延迟线插值器；或者改为四舍五入。
   - 推荐按周期 1/16 截断。
4. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 3”，即待确认清单第 29 项】参考预热：复位释放（或 t = 0）之后 `ref_clk` 要有两个上升沿，转换器才接受 start，复位期间的参考沿不计。这对应原题"少于两条参考边沿时分母无定义"的问题和 spec_plan 的"参考预热"。
   - `reset-warmup` 用例中复位前参考时钟一直在跑，释放后只过一个沿的 start 必须被忽略；不重新预热的模型（`warm_up_survives_reset`）只在这一例被拒。
   - 另一种读法是预热只在上电时需要，周期估计跨复位保留。
   - 推荐复位后重新预热，因为复位通常也清掉周期估计；若用户选另一读法，只需改这一例和一句题面。
5. 【已定（用户 2026-10-29，决定单第 6 项）；原标“待用户确认 4”，即待确认清单第 30 项】溢出（码饱和）与无效：start 之后第 16 个参考上升沿先于 stop 到达时，测量在该沿结束，输出码 255、`valid` 高、`overflow` 高，之后的 stop 被忽略。
   - 无效情形不发布结果：预热未完成或复位期间的 start；被复位中断的测量；没有测量时的 stop。
   - 理由：与 v2-test-time-protocol 的第 256 沿溢出一致，粗计数 4 位，超时即溢出，不需要等待 stop。
   - `base` 另有 `N = 15, q_e = 15, q_s = 0` 的合法结果 255，`overflow` 为低，用来区分饱和码与真实码。
   - 另一种读法是在 stop 时按 `D > 255` 饱和，或溢出时只置 `overflow`、`valid` 保持低。
   - 推荐第 16 沿溢出。
6. 输出协议：被接受的 start 把全部输出清低（测量期间 `valid` 低、码为 0）；stop 或溢出发布结果，保持到下一次被接受的 start 或复位；测量中的 start 取消旧测量并从新 start 重新开始；`rst` 上升清零并结束测量，高电平期间不开始测量。理由：spec_plan 要求明确复位中断与输出协议，与第二批同族题一致。
7. 同刻事件：参考沿与 start/stop 同刻时，参考沿算在事件之前（写在细码定义中）。合法激励域把所有正好同刻排除在终评之外：
   - start/stop 离本周期任何细码边界 `r + k*T_ref/16` 至少 20 ps，台架实际留了 30 ps 以上；
   - start 与 stop 相距至少 100 ps；
   - `rst` 穿越离其他输入的上升穿越至少 100 ps。
   截断判决因此不依赖仿真器的事件定位误差。
8. 用户已确认（2026-10-28，经项目协调方答复“全部按推荐”，F01 选题面写明实际观察起点）：评分起点与到达期限照样板第3b节沿用试点写法，输出变化后 `1.25*tr` 内不评分，题面照实写明，checker 不动。
   - 另加负例 `slow_output_1p3tr`。start、stop、`rst` 穿越都对齐在网格相位 `0.9*g`；`reset-warmup`、`param-override`、`two-ref-short` 的参考上升沿也在这个相位，所以由参考沿引起的溢出同样有评分点。评分起点后的第一个点在事件后 `1.275*tr`，落在 `(1.25*tr, 1.3*tr)` 之内。
   - p0-fix-b 按审核 F06 改正：原先相位是 `g − 5 ps`，`tr = 100 ps`、网格 25 ps 时第一个点正好在 `1.3*tr`，`param-override` 的普通结果和清零看不到迟到，负例只靠溢出那一个恰在 `1.25*tr` 的边界行被拒。
   - 该负例在五个用例都被拒：合成控制 17 mV（`param-override` 23 mV），旧版 EVAS 相同。
   - 按输出变化逐次统计严格开区间 `(t + 1.25*tr, t + 1.3*tr)` 内的评分行，以及 1.3·tr 负例在第一个这样的行上超出 10 mV 的余量：
     - `phase-sweep` 结果 96/96、清零 95/95；`reset-warmup` 结果 4/4、清零 4/4、溢出 1/1；`param-override` 结果 4/4、清零 4/4、溢出 1/1（修正前 0/4、0/4、0/1）；`two-ref-short` 结果 1/1。余量最小 7.3 mV，`param-override` 13.1 mV。
     - 例外都在公开用例 `base`（逐字节不变）：54.295 ns 的清零 150 ps 后被结果覆盖，没有自己的评分点；54.445 ns 的结果只改变 `valid`，从被打断的电平起步，第一个评分点上余量为 −0.015 mV；174 ns 的溢出由 pulse 源的参考沿引起，沿在网格上，只有恰在 `1.25*tr` 的边界行，判定取决于舍入。溢出的迟到由 `reset-warmup` 与 `param-override` 覆盖。
   - 另加只让一种原因变慢、其余正常到达的合成控制：
     - 只有结果迟到：五例都拒；
     - 只有清零迟到：`two-ref-short` 没有清零，其余四例都拒；
     - 只有溢出迟到：`reset-warmup`、`param-override` 拒，`base` 不拒（边界行）；
     - 审核给出的反例（只在 `tr = 100 ps` 时让结果和清零迟到）现被 `param-override` 拒绝，误差 23 mV；
     - 把 `param-override` 的参考沿整体推迟 1 ps，全部输出 1.3·tr 的负例仍被拒，修正前可以通过。
   - 1.2·tr 到达的合成输出通过全部用例。按用户确认，期限 `tr` 与评分起点 `1.25*tr` 之间到达不区分，这是题面写明的余量。
9. 误差上限 10 mV，与 C176-S1 相同：输出是 0/`vdd` 理想电平，正确实现在旧版 EVAS 上误差 0.0 mV。
10. 输入域允许中间电平与任意斜坡：`param-override`（`vth = 0.3 V`）用只到 0.4 V 的 start 脉冲，以及 500 ps、在第一格后折转的参考上升沿（0.45 V 穿越比 0.3 V 晚 100 ps；p0-fix-b 之前是 600 ps 的 pulse 斜坡），写死门限的模型必败。这是 F08 的教训：改写的参数要能被看出。
11. 台架：五个用例，输出网格 `maxstep = strobeperiod = tr/4`，所有 PWL 与 pulse 拐点都在网格上，checker 由行数据读穿越时间没有插值误差。
    - `base`（公开兼终评，默认参数，`T_ref = 4 ns`）：参考时钟 10 ns 才起振；无参考沿时和只有一个参考沿时的 start 被忽略；普通结果 51；未武装的 stop；借位 23；同周期 0 与 15；参考沿后 45 ps 的 stop；重新 start 得 43；第 16 沿溢出后再来 stop；不溢出的 255；清除有效结果的 start。
    - `phase-sweep`（默认参数，4 ns）：12.6 ns（50.4 细步）与 3.85 ns（15.4 细步）两个间隔各平移到 48 个起始相位，结果只取 50/51 与 15/16，含参考沿后 45 ps、沿前 55 ps 的 stop，共 37 次借位。这对应登记的 acceptance。
    - `reset-warmup`（3.2 ns）：上电复位期间参考在跑、start 被忽略；释放后过早的 start；结果有效时复位；测量中复位后的 stop；溢出后复位；同周期 15；重新 start 得 22。p0-fix-b 起参考时钟改为 PWL 两段沿，上升穿越在网格相位 `0.9*g`（3.195 ns 起），其余穿越时刻不变。
    - `param-override`（`vth = 0.3 V`、`vdd = 1.2 V`、`tr = 100 ps`、2.4 ns）：见第10条，另有借位、溢出与沿前 75 ps 的 stop（p0-fix-c 由沿前 100 ps 改，见 p0-fix-c 一节；2026-10-29 已按用户决定（决定单第 1 项）退回为沿前 100 ps，见修正 r7b 一节）。p0-fix-b 起全部事件穿越（含参考上升沿）在网格相位 22.5 ps，start、stop 离参考沿的偏移各加 5 ps 或减 20 ps，细码与结果不变（53、48、23、溢出、43），细码余量最小 50 ps。
    - `two-ref-short`（默认参数，`T_ref = 5 ns`，p0-fix-b 按审核 F07 加入）：记录里只有 2.045 ns 和 7.045 ns 两个参考上升沿，11.95 ns 结束，第三个沿来之前；两沿之间的 start 被忽略（只过一个沿，未就绪）；一个不属于测量的 stop；第二个沿后从 7.745 ns 到 11.145 ns 的同周期测量得 11（`q_s` 2、`q_e` 13）。
    台架由 [build_cases.py（`runs/t3-p0-build-20261027/r04-spec-fine-coarse-tdc/build_cases.py`） 生成，生成时断言台架义务，并用独立的合同模型核对设计结果。
12. checker（[verify.py](tests/verify.py)）不读候选源码或参考解：
    - 从记录的输入按相邻行线性取穿越时间，`T_ref` 取参考上升沿间距，按规则算出每次输出变化；
    - 穿越提取用六题统一的规则（p0-fix-c，审核 R2-01；p0-fix-b 先按 F02 改成按两侧符号变化识别）：每个保存点与 `vth` 精确比较，恰在 `vth` 上的点不属于任何一侧；相邻两个不在 `vth` 上的点分处两侧时记一次穿越，中间恰有一个阈值点时穿越时刻就是该点，否则按两点线性插值；到达 `vth` 后返回原侧的孤立触碰不是穿越；连续两点停在 `vth` 上违反"不停在 `vth`"，抛出异常、不判分；记录末尾单个阈值点按到达方向算一次穿越；记录开头的阈值点不生成穿越（起始离 `vth` 不足 50 mV 本来就是台架错误）；
    - 两个参考上升沿即可确定 `T_ref`；不足两个时转换器不会就绪，输出应一直为低，照此评分（p0-fix-b，审核 F07；原先要求至少三个参考沿，第二个沿后完成的合法短测量报证据不足）；
    - t = 0 的初值必评；
    - 台架义务出错时抛出异常（无判决，不记候选失败）：分辨率、参数超域、输入超出 0–0.9 V、起始电平离 `vth` 不足 50 mV、`ref_clk` 不从低开始或周期不恒定或超出 1–20 ns、穿越不交替、同一输入相邻穿越不足 100 ps、start 与 stop 不足 100 ps、细码边界余量不足 20 ps、`rst` 离其他上升穿越不足 100 ps、相邻两次穿越之间离 `vth` 不足 50 mV（修正 r7b；按保存行判，门槛 49 mV，见该节）；
    - 结果另报测量统计（结果数、溢出、借位、同周期、被 start 取消、被复位结束、被忽略的 start）与最大量化差，量化差应小于 1；
    - 不依赖任何仿真器特有行，旧版 EVAS 只用规则网格行重判时结论不变。
    共用的 `harbor_entry.py`、`v2_runtime.py`、`adc_linearity.py`、Dockerfile 和公开入口与首批逐字节相同。
13. 参考解按 LRM 写，没有为任何 EVAS 版本改写：
    - 四个独立的 `cross` 事件，复位与采样分开，没有用 `or` 合并后在事件里读复位；`cross` 时间容差取 1 ps；
    - 参考沿记录最近两个沿的时间，并按预热计数；
    - start 用 `floor` 截断记下 `q_s`，stop 组合 `16*count + q_e - q_s`，第 16 个参考沿发布溢出；
    - `transition` 零延迟驱动十个输出；只用标量状态，不用数组或 `absdelay`。
14. 校准候选见 [tests/calibration](tests/calibration/README.md)：23 个错误模型、4 个正确替代实现（Nutt 原式、时间戳加定时器溢出、快过渡、延迟后在 tr 内到达），被拒矩阵另存为 `expected.json`。

## 待定项

`metadata.stage = implementation`，`pending = ["grading", "runtime"]`。本题**未仿真**：本机没有 Spectre，没有执行任何 Spectre 电路仿真，也没有运行模型解题。

本轮做了下列开发检查，命令、退出码与结果见 checks.json（`runs/t3-p0-build-20261027/r04-spec-fine-coarse-tdc/checks.json`）：
- 包装检查与阶段静态检查；
- 官方 Harbor 配置解析；
- checker 合成波形控制；
- 旧版 EVAS 0.8.7 冒烟，含参考解、起始模型和全部校准候选（旧版开发证据，EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a，待 Spectre 复跑）；
- EVAS 02dee32b 阶段 a–c 及三个探针；
- Docker 两个镜像实际构建一次并检查。

EVAS 结果只是开发证据，不是 EVAS 能力验收或校准。旧版只给点值，结果可能不准也不报错。

待办：
- Spectre 校准：参考解在全部用例上通过 checker，并记录误差余量与评分起点后第一个点的实际位置；
- Spectre 上记录 `cross()` 事件时刻的定位精度（参考解时间容差 1 ps），确认它远小于 20 ps 的细码余量；
- 样板第4a节的待发事件：参考解没有待发事件（没有延迟过渡，也没有定时器），这一项对参考解不适用。Spectre 运行时仍记录：
  - `transition()` 被打断时的完成方式：`base` 54.295 ns 清零后 150 ps 又在 54.445 ns 发布结果，`valid` 在下降途中转回上升；
  - 校准候选 `alt_timestamp_overflow_timer` 的 `timer` 与同刻参考沿事件的执行次序；
- 作者校准：在 Spectre 上运行 [tests/calibration](tests/calibration/README.md) 的全部候选，按 `expected.json` 比对；
- 上面四个原"待用户确认"选择（建模选择第 1、3、4、5 条，待确认清单第 27–30 项）已定（用户 2026-10-29，决定单第 6 项），都按推荐，修正 r7b 改了状态（F01 已于 2026-10-28 确认）；
- 清单第 38 项已定（用户 2026-10-29 已确认，即决定单第 4 项的 A 收窄版）；p0-fix-c 已按推荐写入题面，见 p0-fix-c 一节，题面不再改；
- `base`、`phase-sweep` 的 stop 恰在 `ref_clk` 穿越上（扫描 B 第 4 节 (g) 项）：现评分不受影响，这两例本轮不改台架，下次改台架时把 stop 挪离参考沿（如再加半个网格），见修正 r7b 一节；
- Spectre 上记录 `base`、`phase-sweep` 中参考沿恰在网格时刻的穿越：pulse 源的上升穿越在网格上，start、stop、`rst` 的 PWL 拐点又有 24 处与参考上升穿越同刻，参考解的 `cross()` 在这些时间点看到 `ref_clk` 恰为门限（p0-fix-c 平局扫描，见处置记录）；
- 记录 `results/reference.json` 与 `results/calibration.json`。

## p0-fix-b 修正（2026-10-28）

依据铺开六题独立审核 r1（`runs/t3-p0-build-20261027/review-p0-r1/astra-review.json`）。本节只记改了什么、为什么改；每个改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-b 处置记录（`runs/t3-p0-build-20261027/p0-fix-b/disposition.md`）。本题**未仿真**：没有运行 Spectre，旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

- F02（穿越提取）：checker 原先把"到达阈值后返回原侧"的孤立触碰记成一次单向穿越，start、stop、`rst` 触及 `vth` 会凭空开始、结束或清除测量，参考时钟触及 `vth` 会使周期检查报错；现按两侧实际符号变化识别，规则见建模选择第 12 条。公开与私有 checker 同时改，逐字节相同。
- F06（迟到可见性）：事件相位改为 `0.9*g`，三个用例的参考上升沿也放到这个相位，逐次统计与只让一种原因变慢的控制见建模选择第 8 条。`base` 与 `phase-sweep` 逐字节不变；`reset-warmup`、`param-override` 改动见第 11 条。
- F07（预热与周期）：checker 用两个参考上升沿确定周期，不足两个时验证未就绪（输出为低），不再另设最小记录长度；新用例 `two-ref-short` 只含两个参考沿，第二沿后完成一次同周期测量。
- 题面、参考解、起始文件、公开用例与公开台架不变；校准候选不变，被拒矩阵加了 `two-ref-short` 一列。

## p0-fix-c 修正（2026-10-28）

依据是 P0 铺开六题的增量复审 r2（astra-review.json（`runs/t3-p0-build-20261027/review-p0-r2/astra-review.json`））的 R2-01 与 F02 剩余部分、Benchmark 维护方 2026-10-28 对清单第 38 项的安排，以及 p0-fix-c 的精确有理数平局扫描。R2-05（批次 README）由Benchmark 维护方改。改动文件改前、改后的 sha256，复现脚本、命令与结果见 p0-fix-c 处置记录（`runs/t3-p0-build-20261027/p0-fix-c/disposition.md`）。参考解、公开用例与公开台架、校准件都没有改。本节的检查都**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

1. 终点事件（R2-01）。p0-fix-b 的写法丢掉记录末尾单个恰在 `vth` 上的行，终点处到达的事件就没有不评分窗。在修正前的字节上复现：参考沿 1.045、5.045、9.045 ns，start 6.145 ns、stop 8.645 ns 得码 10；`rst` 在最后一行（10 ns）恰到 0.45 V，输出在这一行立即清零，被拒 0.9 V；p0-fix-b 之前的写法接受它。现改为六题统一的穿越规则（第 12 条），这条输出通过，提前 1 ns 清零的输出仍被拒。终点事件照样受间隔约束：`rst` 离参考上升沿 50 ps 时报台架错误，正好 100 ps 时照常评分。公开、私有 checker 同时改，逐字节相同；`crossings()` 的函数文本六题相同。
2. 【第 38 项，已按推荐写入；用户 2026-10-29 已确认，即决定单第 4 项的 A 收窄版】输入到达门限时必定穿过。题面合法输入一段在“at t = 0 each input is at least 50 mV away from `vth`.”之后加一句：“An input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side.”“不停在 `vth` 上”和起始 50 mV 原已写明，不重复；checker 不变。另一种读法（决定卡 B）：按 Spectre 的到达语义，把触碰算作一次事件，方向取到达方向，撤回 F02 修正并写进题面；这样按电平比较写的实现遇到触碰会被判错，六题 checker 都要改回并重新校准。读法 C：维持现状，题面不写，合法域对触碰沉默。
3. `param-override` 的平局。最后一个 stop 在参考沿前 100 ps，而 `tr = 100 ps`：码 43 的输出过渡正好在 91.3975 ns 的参考上升穿越上结束，两者精确值只差 443/8·2⁻⁸³ s，落在同一个 binary64 时刻。用例要测的是沿前不远处的 stop 不计入这个沿。
   - 定类（Benchmark 维护方 2026-10-28 定稿的口径）：第 (i) 类，迁就 EVAS，不是题目缺陷。checker 的期望只由记录的四个输入的穿越算出（`tests/verify.py` 第 151 行取穿越，第 184–186 行由这些穿越组成事件并调用 `expected_changes`）；91.2975 ns 的 stop 结束测量后没有武装的测量，91.3975 ns 的参考沿不改变任何期望输出；平局时刻落在结果变化后的不评分窗内（到 91.4225 ns）。两种次序下参考解的波形相同。合成核对（tie-classification.json（`runs/t3-p0-build-20261027/p0-fix-c/evidence/tie-classification.json`））：在原用例上，合同波形通过；全部十个输出从平局时刻到窗口结束加 0.25 V 仍通过；窗口结束后加 0.25 V 被拒。
   - **第 (i) 类，待用户确认是否退回；原件在 p0-fix-c/orig/。** 退回时用原 `tests/cases.json`（`runs/t3-p0-build-20261027/p0-fix-c/orig/r04-spec-fine-coarse-tdc/tests/cases.json`）。2026-10-29 已按用户决定（决定单第 1 项）退回，见修正 r7b 一节。
   - 改法：这个 stop 挪后一个 25 ps 网格步，到参考沿前 75 ps（91.3225 ns），网格相位不变；`q_e` 仍为 15，结果仍为 43，细码余量 75 ps（全用例最小仍为 50 ps）。只改 `Vstop` 最后一个脉冲的拐点与 purpose 文字，其余四个用例逐字节不变。生成脚本是 p0-fix-c 的 build_cases.py 副本，断言全部台架义务并核对设计结果。
   - 第 8 条的逐次统计不变：`param-override` 结果 4/4、清零 4/4、溢出 1/1，余量最小 13.1 mV；1.3·tr 迟到负例在 91.3225 ns 这次变化上超出 23.1 mV，1.2·tr 窗内对照通过。
4. 平局扫描的其余结果（不改）：参考解的过渡终点在全部用例中都不再落在输入穿越上。`base`、`phase-sweep`、`reset-warmup` 另有 start、stop、`rst` 的 PWL 拐点与 `ref_clk` 穿越同刻（50 处，其中 24 处是参考上升穿越，都在 `base` 和 `phase-sweep`，因为 pulse 源的穿越在网格上）。这些不是过渡终点；参考解只在 `ref_clk` 上升穿越动作，Spectre 的到达规则在这些时刻给出的正是穿越时刻。其中 `phase-sweep` 的记录在一次参考上升穿越上结束，`base` 的记录在一次参考下降穿越上结束：按统一规则，最后一行若恰为门限就算一次穿越；把旧版参考解波形的最后一行强制为门限重判，两例判决与误差都不变。公开 `base` 不能改，这些同刻列为 Spectre 记录项（见待办）。按Benchmark 维护方 2026-10-28 的口径，PWL 拐点不是事件，这些不算平局，不挪；事件与事件同刻的没有。

第 38 项的三个前提（Benchmark 维护方 2026-10-28 定的口径，也作复审口径）：
- 内部恰为零：参考解的事件只看外部驱动的 start、stop、`ref_clk` 上升穿越和 `rst` 两个方向的穿越；没有被测模块内部恰为零的信号参与事件或判决，无需核对。执行细则（Benchmark 维护方 2026-10-28 转标准审核口径，p0-fix-d 写入，也作复审口径）：内部信号恰为零时，参考解不得靠 `cross()` 去检出“离开零点”；要么用电平判定，要么在复位或初始时用电平判定设定状态。本题参考解只对外部驱动的 start、stop、`ref_clk`、`rst` 用 `cross()`，符合（p0-fix-d 核对）。
- 相等规则写成输出行为：细码的截断写成输出码的规则（`floor`），合法输入让事件离每个细码边界至少 20 ps，不出现相等；输入恰在 `vth` 上由合法输入排除（第 2 条）。
- 末尾门限行：记录末尾单独一行恰在门限上时，按到达方向记一次事件（统一规则）。这与归档 Spectre 记录 [cross-boundaries-0.4.6.json](../../../../../../../experiments/backends/dvs2-spectre-validation/results/cross-boundaries-0.4.6.json) 中 `terminal_pos`、`terminal_neg` 在 stop 处到达时触发一次的观察一致，保留。
5. 复核：
   - p0-fix-b 的 F02 对照 10 个在新 checker 上判决不变；p0-fix-b 的合成控制与 F06/F07 脚本副本在新用例上全部符合预期，与存档相比判决与误差 0 项变化。
   - 旧版 EVAS：参考解在全部私有与公开用例上通过（6/6，误差 0）；27 个校准候选在 `param-override` 上与被拒矩阵逐项一致（18 拒、9 接受），被拒矩阵不变。
   - 建题以来的旧版存档波形用新 checker 重判，判决与误差 0 项变化。

## 2026-10-29 修正 r7b（p0-fix-r7b）

依据：用户 2026-10-29 答复的决定单（第 1 项：第 (i) 类平局挪动退回原件；第 6 项：P0 清单第 1–37 项）；扫描 B 报告第 4 节 (补p)、(g)、(k) 三项与第 10 节（项目协调方 2026-10-29 批准本轮）；项目协调方的决定：补p 照 C061 补一句与台架判定，逻辑输入取 50 mV；P0 各题写入标准审核定的容差行；U16 只在本轮改台架的用例里顺带把 stop 挪开。改前改后的 sha256、脚本、命令与退出码见本轮记录 runs/t3-p0-build-20261027/p0-fix-r7b/disposition.md（不入库）。本节的检查都**未仿真**：没有运行 Spectre；旧版结果是旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑。

0. 退回 `param-override` 的第 (i) 类平局挪动（决定单第 1 项）。p0-fix-c 为避开 91.3975 ns 的平局（码 43 的输出过渡终点与参考上升穿越在 binary64 下同刻，精确差 443/8·2⁻⁸³ s）把最后一个 stop 后移 25 ps；p0-fix-d 按定稿判据复核为第 3 种、第 (i) 类（此时没有武装的测量，参考沿不改写任何输出的目标）。
   - 退回的字节：`Vstop` 最后一个脉冲的六个拐点各提前 25 ps，回到 `91.275n 0 91.3n 0.333333 91.325n 0.9 92.275n 0.9 92.3n 0.233333 92.325n 0`；purpose 末尾“a stop 75 ps before a crossing (43)”回到“a stop 100 ps before a crossing (43)”。退回后的 `tests/cases.json`（写入容差之前）与 p0-fix-c 原件（`runs/t3-p0-build-20261027/p0-fix-c/orig/r04-spec-fine-coarse-tdc/tests/cases.json`，`b39aaa83…`）逐字节相同；p0-fix-b 的生成脚本副本改为写到别处后重跑，三份输出与原件逐字节相同，脚本里的台架义务断言全部通过。其余四个用例、公开用例与公开台架没有退回的内容，p0-fix-b 的第 (ii) 类修正（相位 0.9·g、参考沿两段沿、`two-ref-short`）都保留。
   - 三项核对（精确有理数，网表数按 binary64 读入）：合同下界有余量（同一输入相邻穿越至少 822.5 ps、start 与 stop 至少 3.4 ns、细码边界余量最小 50 ps、t = 0 离 `vth` 0.3 V、相邻穿越之间离 `vth` 至少 0.1 V，都远大于 2·(1 mV/斜率 + 1 fs)）；迟到可见性：9 次输出变化在 `(t + 1.25*tr, t + 1.3*tr)` 内都有评分行，结果仍为 53、48、23、溢出、43，1.3·tr 迟到负例在本例超出 23.1 mV 被拒、1.2·tr 通过（合成控制）；平局：91.3975 ns 的平局按原样回来，精确差仍是 443/8·2⁻⁸³ s，属第 (i) 类，题目不避开；按平局判据，EVAS 侧自行判定或证明这一平局。
   - 上文建模选择第 11 条与 p0-fix-c 一节第 3 条已各补一句“2026-10-29 已按用户决定（决定单第 1 项）退回”，原文不动。
1. stop 与参考沿（扫描 B 第 4 节 (g) 项）。退回的 `param-override` 的 stop（100 ns）不在 `ref_clk` 穿越上：`ref_clk` 在 100 ns 为 0.5625 V，正从 0.9 V 下降，0.3 V 的下降穿越在 100.175 ns，最近的穿越离 stop 1.4 ns，不用挪。`base`（下降）与 `phase-sweep`（上升）的 stop 恰在参考穿越上，评分不受影响（这次穿越之后没有评分行，最后一行进出两种结局判定相同）；这两例本轮不改台架，下次改台架时挪开（如再加半个网格），记在待办。
2. 补p：相邻两次穿越之间的最小偏离。
   - 题面：第 33 行“They may move between any levels …, and an event is the instant at which the input passes `vth`.”之后加一句“Between two successive crossings of `vth`, each input moves at least 50 mV away from `vth`.”，其余不变。
   - 理由：原合同允许输入“在任意电平之间移动”，两次穿越之间离 `vth` 有多远没有下限。按标准审核 SL-DEC-20261029-05，两根之间的偏离不超过 expr_tol、间距不超过 time_tol 时，报一次、报两次都合 LRM 5.10.3.1，计数（N、溢出、结果）就不能评分。参考解的五个 `cross()` 都写了 time_tol = 1 ps，相邻穿越至少 100 ps，本来就两次都报；但按缺省容差写 `cross()` 的实现（Spectre 的缺省 time_tol 是 1 s，实际只看 expr_tol）遇到偏离不到 expr_tol 的返回根时，计数不确定。加这一句以后，两根之间的偏离远大于任何网表的缺省 expr_tol（下一条），任何合规实现都必须两次都报，计数照常评分。参考解的 1 ps 写法仍合规，与本条不冲突，不需要改。
   - expr_tol 核对（脚本 runs/t3-p0-build-20261027/p0-fix-r7b/scripts/check_exprtol_r7b.py，退出码 0；表达式取四个输入的 `V(x) - vth`，源按 binary64 读入后精确求值）：7 份网表写入容差后 reltol 1e-6、errpreset moderate，最宽 expr_tol 最大 0.601 µV（`param-override`，`vth` 0.3 V，max|expr| 0.6 V），50 mV 是它的 8.32e4 倍以上；缺省容差对照（reltol 1e-3）最大 0.600 mV，仍是 83.3 倍以上。现有台架相邻两根之间离 `vth` 最少 0.1 V（`param-override` 只到 0.4 V 的 start 脉冲），其余 0.3 V 以上；没有触碰、平台或停在门限上的点。
   - checker（两份 `verify.py` 逐字节相同）：在“同一输入相邻穿越不足 100 ps”之后，对每个输入的每一对相邻穿越，取两者之间各保存行上 `|V(x) - vth|` 的最大值，小于 50 mV − 1 mV = 49 mV 时 `raise ValueError`，`v2_runtime.py` 记作 checker_error（不判分、不算候选失败）。余量 1 mV：受约束的量只涉及一个保存节点（输入对地，`vth` 是参数），按样板每个保存样本可偏离 1 mV，与 C061 修正 r2 的算法相同（C061 涉及两个节点，取 2 mV）。通过检查的台架，两根之间的真实偏离至少 48 mV。
   - 局限：只读保存行，极值落在两行之间时会被低估，所以台架的极值要放在平台或保存行上。现有 7 份网表在各自的 strobe 网格上按网表重放的行，与按折点精确求出的值逐对相同（1932 对，差 0）。
3. 容差写入（第 (ii) 类，扫描 B 第 4 节 (k)；标准审核 2026-10-29 给的值）。7 份网表都在 tran 行之前另起一行写 `simulatorOptions options reltol=1e-6 vabstol=1e-8 iabstol=1e-12`，tran 行末补 `errpreset=moderate strobeoutput=strobeonly`，其余字节不变。
   - `base`、`phase-sweep`、`reset-warmup`、`two-ref-short` 与公开 `base` 写入后再加执行路径一行，与预校准包 P0PC-must-01（包 spectre-P0PC-must-01-v1，结果包 sha256 `56bb45ddcc96029e2ee7bd556bdd9b26db70f2186f91bff0653353d43b837ad6`，已核收）的同例参考解作业网表逐字节相同，`visible_test.scs` 与公开用例只差 include 路径；这些用例已核收的结果仍然作数。
   - `param-override` 与 P0PC 作业网表只差退回的 `Vstop` 一行，要重跑：参考解、缺省容差对照与全部 27 个校准候选（作业清单在本轮记录里，本轮不打包）。
4. 复核（都未仿真）：
   - 合成控制 A：建题时的 35 个 Python 模型在 5 个私有用例与公开用例上共 210 次判决，加 11 个证据有效性控制；改前改后的 checker 给出的整份结果逐个相同，不同的 0 个。
   - 合成控制 B（新台架检查；ref_clk 不起振、输出恒低的台架，每个折点都在保存行上）：stop 在两根之间只离开 40 mV、48.9 mV 时报台架错误，60 mV、49.1 mV 通过；start 只升到 `vth` 以上 40 mV 后返回报错、60 mV 通过；rst 只降到 `vth` 以下 40 mV 报错、60 mV 通过。恰好 50 mV（binary64 下 0.04999999999999999 V）通过、49 mV（0.04899999999999999 V）报错，取决于舍入，只作平局诊断。改前的 checker 对这 11 个台架都照常判分。
   - 旧版开发证据（EVAS 0.8.7，legacy/EVAS 提交 6cb6fa7a），待 Spectre 复跑：参考解与 27 个校准候选在退回后的 `param-override` 上重跑（经重负载位取位），28 次全部判分，与 `expected.json` 逐项一致（18 拒、10 接受）；每条波形与 p0-fix-b 在挪动之前的同一用例上的运行逐值相同（旧版不理会容差行）。建题以来存档的 261 条旧版波形（含本轮 28 条），全部行与只用网格行各判一次，共 522 次，改前改后判决逐个相同，没有新的台架错误。
   - P0PC-must-01 已核收的 12 个参考解作业（带容差与缺省容差两组）用改后的 checker 重判，全部通过，判决与误差与改前逐个相同。新检查只读 `vsource` 驱动的输入，同一用例各作业的输入行相同。
5. 决定单状态：建模选择第 1、3、4、5 条（原标“待用户确认 1–4”，待确认清单第 27–30 项）改为已定（用户 2026-10-29，决定单第 6 项），理由原文不动；待办同步。Benchmark 维护方随后照 C109 的写法，把第 38 项（决定单第 4 项）的状态行同步为已定，只改状态行。
6. 参考解、起始文件、校准候选与 `expected.json` 都没有改；校准 README 补了本轮退回、新台架检查与旧版重跑的一段。

## 2026-10-30 修正 v417

依据：只读扫描 v417-bench-scan-r1 列的本题 1 处台架义务检查（U16-05，Benchmark 维护方已核实）；网表约定清单第 4.21 版（sha256 前 8 位 `7d511985`）第 0.5 节第 20 条，第 4.17–4.21 版新增的各点逐条核过（第 4 小节）；项目协调方 2026-10-30 的三项决定：做法甲的范围是起点、停留、碰到、最小偏离四项一起按网表激励定义判，时序守卫、范围与数值 δ 类检查不动；“碰到”在 14 道题里一律报台架错误；strobeonly 不算满足条件 3，要改的清单不变。另据 Benchmark 维护方 2026-10-30 对本轮第 1 次停下的决定（重判的写法与题面依据，第 5、7 小节）。改动文件改前、改后的 sha256，脚本、命令与结果见 `runs/t3-harbor30-20261027/v417-bench-fix-r1/disposition.md`（不入库）。本节的检查都**未仿真**：没有运行 Spectre、EVAS（含旧版）、模型或 Docker；合成控制是 Python 合成行；重判只读已交回的 Spectre 波形。前面各节原文不改。

改动范围：两份 checker（`tests/verify.py` 与 `environment/starter/testbench/verify.py`，改后逐字节相同，sha256 `927f436e21706f829bf643d3486e306c461e09009a6e415a9480b8a485ac341f`，改前 `a04b3538…`）与本文件。题面、参考解、用例网表、`tests/calibration/`、`v2_runtime.py`、`task.toml`、`cases.json` 都没有改；判分逻辑、时序守卫、范围检查与数值 δ 类检查不变。

### 1. 改了什么（编号照扫描）

- **U16-05**（evaluate 第 154 行调用 `crossings`，第 54–56 行）：`start`、`stop`、`ref_clk`、`rst` 的保存行上相邻两行恰为 `vth`（停留）报台架错误 → 按定义判；`crossings()` 去掉这一句，穿越的定义不动。
- 随同改（决定第 1 项，起点与最小偏离）：evaluate 第 149–150 行 t = 0 那一行离 `vth` 不足 50 mV × `REL`；第 161–170 行（修正 r7b）两次穿越之间各保存行的最大偏离不足 49 mV。两项都按定义判，门槛不变。
- 碰到：改前只当“不算穿越”，现在报台架错误（决定第 2 项）。

### 2. 怎么判（做法甲）

- 用哪份定义：checker 读所判用例自己的网表 `case["netlist"]`。它就是 `v2_runtime.py` 写成 `tb.scs` 交给仿真器、跑完再核 sha256 的那一份，被改动就记 evidence_error。私有用例取 `tests/cases.json`，公开检查取 `environment/starter/testbench/cases.json`；`visible_test.scs` 不经 checker 判，本轮用同一读法核过它也读得出。
- 受查量：`start`、`stop`、`ref_clk`、`rst` 各自对 `vth`。`check_stimulus` 放在原来起点检查的位置，在取穿越与判分之前。
- 定义取值：受查量由它涉及的节点自地起串着的 vsource 得出，在 [0, stop]（stop 取网表 tran 行）上于各源的定义点之间是直线：PWL 用各点的时刻与值，pulse 用 val0、val1 与四个拐角（按周期重复），dc 源用 dc 值，sine 用 sinedc ± ampl 与起点值。本题受查量涉及的源：PWL 24 个、pulse 4 个。
- 在门限上：定义点的值与门限按写出的十进制精确相等，或各自舍成 binary64 后相等，任一成立即算。节点由几个源叠成时，“精确和舍入一次”与“各源先舍成 binary64、自地起逐运算相加”两种值都算。
- 判法（都是 `raise ValueError`，`v2_runtime.py` 记作 checker_error：该例不判分，不算候选失败）：
  - 起点：t = 0 的定义值在门限上，报 “starts on …”；离 `vth` 不足 0.04999995 V（`START_MARGIN` × `REL`），报 “starts … closer than …”；
  - 停留：相邻两个定义点都在门限上，报 “rests on …”；
  - 碰到：一个定义点在门限上、前后两侧在同一侧，报 “touches … and returns to the same side”；stop 时刻恰到门限算到达方向的一次穿越，不报；
  - 最小偏离：相邻两次定义穿越之间，各定义点离门限的最大偏离小于 0.049 V（`CROSSING_EXCURSION` − `SAMPLE_SLACK`，50 mV − 1 mV），报 “moves only … away from …”；
  - 读不出：受查量涉及的节点上的全部 vsource 都要读得出，在差里抵消的源也不例外。数字只写字面量，可带一个比例符号；不写参数名、表达式、行尾注释、单位，也不写指数后接比例符号。pulse 写全六个参数，rise、fall 大于 0；PWL 时刻严格递增；sine 写 sinedc、ampl、freq，不带 delay、damp。读不出报 “cannot read the stimulus definition of …”；受查节点不由用例网表的 vsource 驱动，报 “… is not driven by a voltage source of the case netlist”；网表里有只差大小写的节点名也报台架错误（保存信号按小写配对，Spectre 区分大小写）。
- 穿越：判分用的穿越仍由原来的 `crossings()` 从保存行取，穿越的定义不动，只去掉其中“相邻两行恰在门限上就抛出异常”一句。保存行恰在门限上（例如模块在同一输入、同一门限上求根时写下的根处行）不再引起台架错误。

### 3. 余量（数值未改）

- 最小偏离：`SAMPLE_SLACK` = 1 mV 仍从题面的 50 mV 中扣除，报错门槛 49 mV 不变。它原来的理由是保存样本可偏离源 1 mV、保存行会低估两行之间的极值；按定义判以后这个理由不再适用，现在只是容让：定义上只离开 49 mV 到 50 mV 的激励已在题面合法域之外，但不报台架错误。常量注释照此改写，数值未改。
- 起点：50 mV 乘 `REL`（1 − 1e-6）不变，报错门槛 0.04999995 V；按定义精确比较以后相对余量只是容让，数值未改。
- 改不改这些数值由项目协调方另定，本轮不改。

### 4. 清单第 4.17–4.21 版各点（第 6 条）

| 点 | 本题 | 怎么处理 |
| --- | --- | --- |
| 做法甲（v4.17） | 适用 | 受查量（`start`、`stop`、`ref_clk`、`rst` 各自对 `vth`）的起点、停留、碰到、最小偏离按用例网表的 vsource 定义判，不读保存行（第 2 小节）。 |
| “在门限上”的读法（v4.18、v4.20） | 适用 | 门限 `vth` 是用例参数，按写出的十进制与 binary64 两种比；门限不是表达式。合成控制另做了只在 binary64 下才在门限上的变体（第 6 小节）。 |
| 和、差与叠放（v4.18、v4.20） | 不适用 | 受查量是单个节点对地；没有叠放源（本题网表里受查节点各由一个 vsource 直接对地驱动）。代码对叠放照两种舍入处理。 |
| 读得出（v4.18、v4.20） | 适用 | 本题 7 份网表（私有 5、公开 `cases.json` 1、`visible_test.scs` 1）共 28 个 vsource，都读得出，与扫描第 1 节一致；受查量涉及的源 28 个（PWL 24 个、pulse 4 个），都读得出。读不出报台架错误，该例不判分。 |
| 比较式的不同写法（v4.20） | 不适用 | 一种写法：checker 比 `V(x)` 与 `vth`，参考解在 `V(x) - vth` 上求根；binary64 下 `x - vth` 为 0 与 `x == vth` 等价，不另算。 |
| 另一个受查量（v4.21） | 不适用（没有新增受查量） | 参考解 `fine_coarse_tdc` 在 `V(rst)`（两个方向）、`V(ref_clk)`、`V(start)`、`V(stop)` 减 `vth` 上求根，就是受查输入本身。没有台架模块：`cases.json` 不带 support 源码，公开目录没有 `.va`。候选的写法不在此列（合成控制 B 仍按各候选自己的事件插了根处行）。 |
| 模块驱动的受查信号（v4.17–v4.20） | 不适用 | 受查信号都由用例网表的 vsource 直接驱动，7 份网表逐份核过，不由 vsource 驱动的 0 个；没有台架模块，也没有按候选输出生成的受查信号。 |
| 条件 3 与 strobeonly（决定第 3 项） | 适用 | 本题 7 份网表都写 `strobeoutput=strobeonly`；strobeonly 不算满足条件 3，照改。 |
| 碰到（决定第 2 项） | 适用 | 改前只当“不算穿越”，现在一律报台架错误。 |

### 5. 题面依据（不改题面）

- 起点、停留、碰到、最小偏离：instruction.md 第 33 行 “Inputs never rest at `vth`, and at t = 0 each input is at least 50 mV away from `vth`. An input that reaches `vth` always crosses it; it never touches `vth` and returns to the same side. … Between two successive crossings of `vth`, each input moves at least 50 mV away from `vth`.”
- 读不出、不由 vsource 驱动：这两种台架错误都是本方网表的失败保护，候选改不了网表，也就触发不了；清单第 20 条写明该例不判分。题面第 37 行 “A zero that comes from the simulator, the bench, or other infrastructure does not by itself show that the submitted Verilog-A behavior is wrong.”

### 6. 合成控制（未仿真）

- 做法：合成 strobe 行。网表定义在每个 strobe 时刻精确取值、舍成 binary64；候选输出一律给 0 V（沿用扫描 `rowsim.py` 的做法），所以判分结果多为失败，只用来比改前、改后两版 checker 的整份判决与台架错误。导入的是本轮 scratch 下的 checker 副本，字节码关闭。
- A 现有用例网表：7 份网表各两组行，一组只有 strobe 行，一组另在每个受查量的每个定义穿越处插一行恰在门限上的根处行（共 1951 行）。14 次判决：新 checker 都不报台架错误，与改前的 checker 整份判决逐个相同（14/14）。
- B 候选：扫描列出的 27 个候选（`tests/calibration/mutants.py` 在本轮 scratch 生成，不在题包里生成），按各自的 `cross()`、`above()` 事件映射到台架节点，在每份网表上插它们自己的根处行（28 组不同的行，共 26478 行）。改前、改后判决逐个相同，新 checker 不报台架错误（27/27）。
- C 变体（在 `base` 上改 `rst` 的定义；每个变体事先写下预期），14/14 符合预期：
  - `rst` 起点按十进制恰在门限上：报 “starts on”
  - `rst` 起点只在 binary64 下恰在门限上：报 “starts on”
  - `rst` 起点离门限 0.0498999 V：报 “closer than”
  - `rst` 起点离门限 0.0500999 V：不报台架错误（照常判分）
  - `rst` 在 1.4e-07 s 处按十进制停在门限：报 “rests on”
  - `rst` 在 1.4e-07 s 处只在 binary64 下停在门限：报 “rests on”
  - `rst` 在 1.4e-07 s 处按十进制碰到门限：报 “touches”
  - `rst` 在 1.4e-07 s 处只在 binary64 下碰到门限：报 “touches”
  - `Vstart` 在 5.045e-09 s 与 6.045e-09 s 两次穿越之间只离门限 0.0489 V：报 “moves only”
  - `Vstart` 在 5.045e-09 s 与 6.045e-09 s 两次穿越之间只离门限 0.0491 V：不报台架错误（照常判分）
  - `rst` 的源有一个值写成参数名 `vlo`：报 “cannot read”
  - `rst` 的源有一个值写成表达式 `0*1`：报 “cannot read”
  - `rst` 的源有一个值带单位 `0V`：报 “cannot read”
  - `rst` 不由 vsource 驱动：报 “is not driven”

### 7. 已交回作业的重判（未仿真）

- 范围：14 道题全部已交回的 Spectre 作业，以各包 `jobs.json` 的 meta.task 为准，只数正式打包目录（不数 scratch 下的试做包）：34 包 3852 个作业，判了 3848 个，未判 4 个（C266 的执行错误，没到 checker）。
- 做法：每个作业用它发出时的快照判，用例取快照里的那份，只把 checker 换成新版，与原判逐个比；判决相同指 status、passed 与台架错误的有无都相同。P0PC 里有些作业跑的是后来改过的旧网表，只用来比两版 checker，不对现行题包评。快照里的旧 checker 重判，与预读记录的原判逐个相同（status、passed、整份判决 sha256），工具与环境没有问题。
- 结论：本轮改动没有改变任何作业的判决（new 与改前 checker 3848/3848 相同）；与打包时的原判比，3708 相同，140 不同，来自 p0-fix-r9 已记录的激励与规则改动。
- 不同的 140 个全是 U15（`r04-spec-delay-pulse-hold`）：spectre-P0PC-must-01-v1 10、spectre-P0PC-opt-01-v1 26、spectre-P0PC-rec-03-v1 84、spectre-P0PC-rec-04-v1 20。
- 本题：spectre-P0PC-must-01-v1 12、spectre-P0PC-opt-01-v1 27、spectre-P0PC-rec-04-v1 110、spectre-P0PC-rec-05-v1 25、spectre-P0R7-must-01-v1 29，共 203 个。new 与改前 checker 整份判决 203/203 相同。与原判比 status、passed 与台架错误的有无 203/203 相同，整份判决 sha256 也相同。

### 8. 前面各节的相关句子

- 建模选择第 112、115 行（穿越提取里“连续两点停在 `vth` 上…抛出异常”，台架错误里的“起始电平离 `vth` 不足 50 mV”“相邻两次穿越之间离 `vth` 不足 50 mV（修正 r7b；按保存行判，门槛 49 mV）”）：起点、停留、碰到、最小偏离改按定义判，碰到报台架错误；穿越时刻的取法不变。
- 修正 r7b 一节第 197、198 行（按保存行判最小偏离、余量 1 mV 的理由、“只读保存行”的局限）：自本节起按定义判，余量的用途见第 3 小节。
