# 第二批23题Harbor迁移

首批30题以外的23道v2/v3纯Verilog-A草稿的Harbor迁移集合；保留原ID和唯一活跃题包目录，不增加独立题目计数。题包仍由原批次维护。R01两题保持独立身份，三道需要SPICE的草稿不在本批。

2026-10-27约17:45Z用户要求提速后开始：分诊通过的题不等确认直接迁移，有疑点的题等用户。分诊结果、处置与每题状态见[selection.json](selection.json)，证据在本线runs/t3-batch2-20261027/（git忽略）。

| 状态 | 题数 |
| --- | ---: |
| 已迁移（implementation，未仿真）：A组9题与B组7题的审核发现全部关闭（A组F01的三条在f01-r2增量复审中关闭；B组两道校准题经四轮复审） | 16 |
| 按用户决定（2026-10-28）新迁移：071、370、online-gain、segmented。首轮独审的 11 条 P2 已修正（fix-dec-r1：新增 4 个私有用例，071、370 的参考解按合同各改一处）；增量复审 dec r2 新提的 370 两条（R2-01、R2-02）已在 F01 同步后的合并复审中关闭；370 的 `alpha` 范围（决定单第 8 项）用户 2026-10-29 按推荐确认；segmented 的等号读法（第 9 项）用户选甲，author-r2 已写入题面、checker 的台架检查与台架容差 | 4 |
| 用户已确认（2026-10-28）记为segmented的变体、不迁：nonideal、subradix、thermometer | 3 |

已迁移的题：结构、官方Harbor配置、边界夹具与合成波形控制通过。A、B组16题的迁移本身没有改任何checker、用例、参考解或激励的数值；按用户决定新迁的4题（decisions-r1）有三项获批的数值改动：071拉伸用例的sample延迟、370首个clk斜坡（公开台架同步）、online-gain参考解的起点裕量，checker未改，见迁移记录（`runs/t3-batch2-20261027/decisions-r1/disposition.md`）。之后各轮按独审的修正另记在各题SOURCE。旧版EVAS 0.8.7上A组参考解32/32用例通过（旧版开发证据，待Spectre复跑）；EVAS 02dee32b上三道修复题参考解跑通，其余停在已知阻塞。本机没有Spectre，完整Harbor端到端执行与校准尚未进行，正式录取为0。

迁移后的独审查出的多是原草稿遗留的缺陷，例如checker漏查、终评覆盖不足、题面没写现有容差。主控决定按各题已有合同修正，修正记在各题SOURCE页：
- A组：12条发现中F02–F12已修正，新增7个私有用例，改了8个用例的激励。183只改本题checker副本，并补了题面。增量复审后只剩308合法域漏写vcm范围一条，主控已补，B组复审确认关闭。参考解不变。
- B组：11条发现已修正，新增2个私有用例。两道校准题加密了观察网格，改为按每次码变化计时。占空比、校准题只改本题的checker副本，家族副本不动。参考解不变。增量复审关闭9条；两道校准题的B02、B05未关，另查出两条P1（保持段端点、cal-low检查的插值），在修。

评分口径F01：
- A组：v2_spec.py在目标变化后等1.15·tr（091为4.1·tr）才恢复评分，题面写的是tr。
- B组：4道测量题在事件前后都有不评分区，题面只写了事件后的过渡。

用户2026-10-28确认“全部按推荐”：
- F01：题面写明checker实际的观察起点，checker不动；每题加迟到负例，测量题另加提前负例。
- 071：拉伸用例的sample延迟加0.25 ns，避开tick网格；C055-S1并入本题，不另建。
- 370：首个clk斜坡改为9.1–10.1 ns，并写明全局k·tick轮询。
- online-gain：写明起点样本计入，参考解留半个采样周期裕量。
- 四道converter只留segmented作代表，其余三题记为变体。

4题已按决定迁移（旧版判分：071 2/2，370 由1/2到2/2，online-gain 由2/6到6/6，segmented 3/3；均为旧版开发证据，待Spectre复跑）。C055-R1经独立性检查停在设计说明，用户2026-10-29定不建（决定单第3项），C055只计一题。受F01影响的10题已同步题面（2026-10-28，f01-r1，同轮另改了370的措辞），合并复审后又补了三处（f01-r2）：duty-cycle的评分句改为按`vth`、checker在用例`threshold`与`vth`不符时报台架错误，并新增非默认`vth`私有用例；duty-cycle与sampled-rms各加一个细网格私有用例，让迟到与提前负例看得出来；375按乙方案定稿（用例写`tr=1e-10`，评分起点115 ps；用户2026-10-29选乙，退回脚本不再执行）。f01-r2的增量复审已关闭F01B-01、F01B-02、F01B-03，没有新发现（审核记录（`runs/t3-batch2-20261027/review-f01-r6/astra-review.md`））。

2026-10-29 author-r2（未仿真）：online-gain 的 `strict_start_no_margin` 改为随后端而定的探针（Spectre 上通过，旧版拒 4/6）；uvlo-brownout 题面写明门限是 0.65、0.55 的 binary64 值；两道伺服题与 segmented 的台架写了容差（reltol 1e-6、vabstol 1e-8、iabstol 1e-12，与 B2PC 作业同一行）并补了 dc 的 `type=` 与 PWL 到 stop。见 author-r2 记录（`runs/t3-batch2-20261027/author-r2/disposition.md`）。

2026-10-29 记：`tests/v2_next_converter.py` 有分叉（总协调 2026-10-29 定现在不同步）。segmented 的两份（tests 与 starter，`2ba60eb0…`）在 author-r2 加了只在 `kind == 'dac'` 时运行的台架检查；v3-01 里其余 7 份仍是原字节 `b390ea0b…`：首批 slot 8 dac-linearity、slot 9 adc-spectrum 各两份（用例 kind 为 scan、spectrum，同步过去新检查不运行），nonideal、subradix、thermometer 三个变体各一份（只有 tests，用例 kind 都是 dac，同步过去新检查会真的运行）。以后同步时，先重跑这几题的判决核对，不能直接覆盖。
