# 能力 ID 与证据索引

本页供开发和审查使用，登记测试 `GUARDS` 所用的稳定 ID、契约和历史证据。
面向使用者的支持结论只在[四后端支持范围](../COMPARISON.md)维护，详细接受与拒绝条件由所链接的契约维护。
收据只证明其固定执行版本；下表仅登记 ID 与证据，供追溯工具读取，不维护第二份支持状态或当前 main 通过率。

[原 CDS 三例验收](../../../experiments/backends/support/event-runtime-control/README.md#original-cds)
补充 LIN、TIMER、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE、PERFORMANCE 的开发证据。
三条原请求通过原 checker 与实际 Spectre 有限配对；重复工作优化和时间来源修复的执行身份、原失败与限制由收据固定。
有限配对不增加 Q 等级，单次耗时不证明稳定加速。

[同步读出与原时限验证](../../../experiments/backends/support/r01-sync-readout/README.md)
补充 TRANSITION、DYNAMICS、CROSS、COMPOSE、TIMER、EVENT-CONDITIONS 和 EVENT-ORDER。
原物理请求完整执行，保持电压满足原要求；严格阈值引起的整题失败保留。
三张独立乘积卡及普通、中断边沿后的两个滤波消费者均有有限数值和行为证据。
动态系数滤波的原IR准入、历史延续和最终认证失败回退见 `test_live_transition_filter.py`
与 `transient_timer_boundary_tests.rs`；外部取证资格仍不完整，不新增Q资格。

[ANSI 端口声明](../../../experiments/backends/support/ansi-ports/README.md)补充 LANG 的有限证据；
五个正控制共25原生配对点及两个实际拒绝控制保留。原26请求中三项完成并通过冻结旧 checker，23项仍有后续阻塞，不新增Q成绩。

[SCS 时间选择](../../../experiments/backends/support/scs-save-time/README.md)补充 LANG 与 DEV:scs-input 的有限证据；
时间轴、电气同名节点和默认节点保存分别验收，不扩展 Spectre 的完整保存语法或固定 Q 成绩。

[源折点保存修复](../../../experiments/backends/support/scs-source-observation/README.md)补充 DEV:scs-input 的有限开发证据；修复保存插值漏脉冲，不改变原Q成绩。

[Pulse 源误差和保存策略](../../../experiments/backends/support/scs-source-uncertainty/README.md)补充 DEV:scs-input 与 TIMER 的有限开发证据；该历史执行仅支持幅度界。新的[物理源曲线证据](../../../experiments/backends/support/source-shape/README.md)扩展 CROSS、EVENT-ORDER、EVENT-CONDITIONS、TIMED-OPERATOR 与 COMPOSE 的有限组合；347 的已解释兼容差异和未合并状态保留；不改变原Q成绩。[P0逐项收据](../../../experiments/backends/support/source-shape/p0.json)补充同步两例、400五例及#119旧精度反例的当前核销，[固定112家族收据](../../../experiments/backends/support/source-shape/replay112.json)保留完整执行、拒绝与清理分母；[091/320收据](../../../experiments/backends/support/source-shape/diagnosis-091-320.json)补独立完整递推与原件实际参考。分类与后续验收由[统一清单](../COMPARISON.md#replay112)维护，拒绝项继续未支持。
[GAP06有限除法采样](../../../experiments/backends/support/source-shape/gap06.json)补充EVENT-CONDITIONS、TIMED-OPERATOR与COMPOSE：八例独立递推及全部保存量通过，原checker3/8，五例严格根处复位差异及参考观察缺证保留。实际原deck参考8/8通过，有限稳定观察与完整原生波形分别记录；当前112分母及剩余拒绝见[唯一清单](../COMPARISON.md#gap06-sampling)。

[固定候选400与213位置收据](../../../experiments/backends/support/source-shape/evaluation-400-71.json)补充LANG、EVENT-CONDITIONS、EVENT-ORDER、COMPOSE与QUALIFICATION的同源开发证据。两套平台内核、原判据和独立判据分别记录；完整分类、未支持与缺证只在[统一清单](../COMPARISON.md#evaluation-400-71)维护，不改变既有共同Q或合并状态。

[101/314源游标诊断](../../../experiments/backends/support/source-shape/history-101-314.json)补充EVENT-ORDER、TIMED-OPERATOR与COMPOSE的相邻输出阶段修复。独立公开回归和候选隔离检查覆盖真实根之后、执行代表时刻之前的普通及强制观察；两份原件仍拒绝，后续限制见[统一清单](../COMPARISON.md#history-101-314)。没有新增实际参考或合并支持声明。

[GAP20与保持谓词后续](../../../experiments/backends/support/source-shape/gap20-state-predicates.json)补充LANG、TRANSITION、EVENT-CONDITIONS、EVENT-ORDER与COMPOSE的有限开发证据。前端按源码顺序保留默认边沿；保持谓词仅以完整区间证明确定真／假，未认证根窗继续拒绝。314仅设计和正反例准备，未授予生产支持；原件状态及进度见[统一进度表](../COMPARISON.md#progress-board)，没有新增实际Spectre对齐或共同Q。

[101/314共用根窗证书](../../../experiments/backends/support/source-shape/root-window-certificate.json)补充EVENT-ORDER、EVENT-CONDITIONS、TIMED-OPERATOR、TRANSITION与COMPOSE。独立Fraction回归覆盖相异根完整模式、旧历史前缀、根处物理采样及放大、查询和拒绝；同控制器失败重试检查候选隔离。原发现窗口和证明预算保持，连续网络仍用自身局部时钟证书。原件状态见[统一进度表](../COMPARISON.md#progress-board)，有限切片未合并，无新增实际Spectre或共同Q。

[Pulse delay 缺省值](../../../experiments/backends/support/pulse-delay/README.md)补充 DEV:scs-input 的有限开发证据；仅省略 delay 取 0，其他源参数与误差约束保持，原 22 请求仍有后续拒绝。

[隐式 DAE 的动态模型步长](../../../experiments/backends/implicit-step-bounds/README.md)补充 DYNAMICS 的有限开发证据；两条实际参考各33点通过原100nV门槛，不宣称原R01请求新增恢复。

[固定 timer 的隐式 DAE 续算](../../../experiments/backends/implicit-event-restart/README.md)补充 DYNAMICS、TIMER、EVENT-ORDER 和 COMPOSE 的有限开发证据；物理 seed、步长与同控制器回退由独立测试核对，实际参考九点通过原 100 nV 门槛。一般事件窗/约束跳参仍拒绝，不新增 Q 资格。

[初始化节点依赖](../../../experiments/backends/support/initial-node-dependencies/README.md)补充 LANG、LIN 和 COMPOSE 的有限开发证据；三个同源实际 Spectre 对照通过，不宣称原 MUX 任务完成。

[有限整数位运算](../../../experiments/backends/support/integer-bitops/README.md)补充LANG、EVENT-ORDER和EVENT-CONDITIONS的分支开发证据。
IR24保持不变，有限域降低为既有比较选择；常量、顺序XOR和普通掩码的独立回归见
[test_integer_bitops.py](../../tests/test_integer_bitops.py)。原件完整请求及实际Spectre验收独立记录，不从局部通过推导一般整数支持。
同一[分支收据](../../../experiments/backends/support/integer-bitops/evidence.json)补充TRANSITION、CROSS、SLEW和DYNAMICS：
有理点值证明保留真实误差验收，标准算子缺省参数复用原IR；公开正反例分别见
[点值回归](../../tests/test_transition_point_proof.py)和[默认参数回归](../../tests/test_operator_defaults.py)。
最终统一400绑定同一源码；早期核心400与后续三件身份保留在`1de6896b`历史收据。
后续有限点采样的实现与新候选身份见下述低成本闭包证据；原设计保留历史身份。

[有限声明初值](../../../experiments/backends/support/declaration-initializers/evidence.json)补充LANG的分支证据，
并检查既有cross/timer写者上的初始化组合。
初值只为原有事件写者绑定有限实例常量，复用原类型检查、顺序初始化和IR24，
范围见[合同](../math/events.md#declaration-initializers)与[公开正反例](../../tests/test_declaration_initializers.py)。
声明常量不授予一般输入采样、只读设置或ordinary局部量支持。

[低成本闭包](../../../experiments/backends/support/low-cost-closure/README.md)补充 LANG、LIN、ANALOG、CROSS、TIMER、EVENT-ORDER、EVENT-CONDITIONS 和 COMPOSE 的分支证据。
合同分别见[有限点初值与别名](../math/events.md#input-initialization)、[typed整数与有限幂](../math/events.md#typed-integer-closure)及[普通条件与有理输出](../math/solving.md#普通-analog-条件)。
公开控制覆盖源码顺序、精确数组槽、真实根处读取、signed余数、有限pow类型与资源、分支临时量和正分母事实。
当前wave22生产快照 `ab928317` 绑定177份源码／构建输入、IR31、0.24.0和release核 `69c46e155808`，测试辅助提交为 `6d3c8a93`。原始400保持314通过、19失败、67拒绝，333完成；材料r3修订另轨400为317通过、15失败、68拒绝，332完成，两轨均清理400/400、零超时。原件新增027、142；修订轨先由075、再由077新增通过，旧316通过零回退，旧19份原失败checker字典不变。修订轨由同wave22的396份原执行、既有修订012／107／075及新正式执行的077组成。全部PASS仍差83项，350只是节点。
075原相邻样本平滑判据会误拒正确斜坡并放过瞬时跳变，独立Fraction参考与14项正负控制已证。修订仅增加250ps直接观察和必要的有限边沿检查，仍要求完整原checker及其0.40阈值；原VA、物理输入、时长、maxstep、精度和全部预算保持。正式725行保留原365点，32个直接边沿通过，两轴独审闭合；原075仍为FAIL。
077的说明把整个输出保持与实时输入加保持扰动混写。用户审阅具体提案后明确选择后者；修订保留原deck、参数和全部预算，只保持扰动、实时相加输入，完整checker核五性质。正式405直接行、独立Fraction校核、真实registry42项校准及完整400两轴独审通过；原077仍FAIL，未据此推断唯一原意。
[材料r3收据](../../../experiments/backends/support/low-cost-closure/continuation-wave22-materials-r3.json)绑定修订依据、正式执行与完整400映射。
单次完整delivery CI `39193253152` 在精确head `6d3c8a93` 实际15 jobs全部成功，2424个唯一Python方法通过，四分片705/514/634/571，无遗漏、重复、方法或setup跳过；两平台0.24/IR31安装、重装及负控通过。177份运行源码／构建输入与生产快照相同，本地、远端及wheel核各保留实际SHA。两轨输入、源核、预算、checker、覆盖与安装均已独审。
此前CI `39192407319` 的2423PASS及1个旧错误文案断言FAIL保留，coverage因失败分片跳过；同一非法内部电压仍拒绝，一行测试预期修正后18项相关方法通过并双轴复核，再用上述单次完整CI重验，未跨run拼绿。原041仍默认1e9预算拒绝，048仍8192根材料预算拒绝；371、346及369未验收改动不混入本轮。400全部PASS目标未完成，原生Goal已由用户恢复并核实active；既有原生Stop检查在317/400且83项有事可做时的精确命令重放仍阻止结束；用户已信任本地定义，真实原生Stop触发仍未观察到。PR208保持草稿，未合并、未发布公共索引/tag，未新增Spectre或正式共同资格。
[wave22紧凑收据](../../../experiments/backends/support/low-cost-closure/continuation-wave22.json)保留完整执行和独审身份；后续实现继续使用既有scope与400队列。

[IR32恢复证据](../../../experiments/backends/support/low-cost-closure/continuation-ir32-recovery.json)补充LANG、CROSS、EVENT-ORDER与COMPOSE的分支增量。旧函数wrapper的事件、参数和compact消费者保留完整类型义务；[物理区间读取](../math/events.md#paid-shaped-range)减少实际重复工作并沿用原Work。214项Python、188项Rust及8项原生窄检查和两轴集成审查通过；同193输入/release `d4eaadba91fc` 的40原件诊断恢复38项旧通过，369/371仍同预算拒绝。完整400、交付CI及安装待验收，旧317仍只属于上述177份wave22源核。

历史wave21生产提交 `a201378e` 绑定176份源码／构建输入、IR30、0.23.0和release核 `7e7ae92ae2de`。原件400份已完整执行：312通过、19失败、69拒绝，331完成，清理400/400；这不表示400份全部PASS。13+387件同源，旧312、303和基线198通过保留，旧19份失败checker字典相同，相对wave20新增PASS为0。原041在默认1e9证明预算下 `step_budget` 拒绝，checker未运行；R6作者独立PASS不替代统一结果。
修订材料另轨400为313通过、17失败、70拒绝，清理400/400；398份同材料复用本轮原件结果，另两份为修订012通过、107因 `condition_precision` 拒绝。它不替换原件计数。距离全部PASS，原件还差88份，修订轨还差87份；350只是进展节点。
单次完整delivery CI `39169679908` 在辅助修复提交 `8e507c51` 实际15 jobs全部成功，2390个唯一方法通过，四分片621/605/638/526，无遗漏、重复、方法或setup跳过。Ubuntu x86_64/Python3.10与macOS arm64/Python3.12的0.23/IR30安装、重装及负控通过；176份源码／构建输入不变，远端回归和wheel核各保留实际SHA，不声称与本地release字节相同。CI执行身份、完整方法覆盖和两平台安装证据已独立复核。
本轮先前CI `39168731444` 因inventory stale在完整Python前失败（0完整Python、0安装）；`39169086325` 完整失败，2375条为2372PASS及main/point/shaped三个loader ERROR，18个真实方法遗漏，15 jobs为10成功、4失败、1个上游失败导致coverage skip。两份原红记录保留，不跨run拼接全绿。PR208仍为草稿未合并，0.23是开发版本，未发布公共索引或tag；未新增Spectre共同资格，完整EVAS与400全部PASS目标未完成。

历史wave20使用171份输入、IR29/0.22.0、生产 `920d1dd1` 和release核 `d332432d7a94`，原件312/19/69、修订313/17/70；相对wave18新增018、023、061、062、087、147、187、195、202九份，原303及198通过保留，旧19失败字典相同，固定125为94/10/21。辅助测试／包装提交 `d2cba5f0` 的单次CI `39163153008` 实跑2369项全通过及两平台安装通过；首红 `39162066252` 的2367PASS、2非PASS及包装失败记录保留。

[收据](../../../experiments/backends/support/low-cost-closure/evidence.json)保留历史wave18提交 `c8dc2a7b` 的163份生产输入、IR28、0.21.0与release核 `406d7b27da50`，303通过、19失败、78拒绝，322完成，清理400/400。12件与其余388件经collector核验为同一执行身份；相对wave17新增135，原302及198通过全部保留，19份旧失败checker字典相同。原固定125成员从同次结果抽取仍为93通过、10失败、22拒绝，距350还差47份。单次完整delivery CI `39149288332` 在同一提交实跑2320项，四分片为611、574、545、590项，全部通过，无遗漏、重复或方法及setup跳过。Ubuntu Python3.10与macOS arm64 Python3.12的0.21/IR28安装、重装和负控通过；远端回归与wheel核各保留实际SHA，不声称与本地内核字节相同。
[收据](../../../experiments/backends/support/low-cost-closure/evidence.json)保留历史wave17提交 `3c870f31` 的162份生产输入、IR28、0.21.0与release核 `721190664d05`。完整400为302通过、19失败、79拒绝，321完成，10+390件身份一致，清理400/400。新增069、335，原300及198通过保留，19项旧失败字典相同；固定125仍93/10/22，距350差48份。077原checker FAIL及诊断保持。单次完整CI39146347930的2314项全通过、0方法及setup跳过，两平台0.21/IR28安装、重装和负控通过。
[收据](../../../experiments/backends/support/low-cost-closure/evidence.json)保留历史wave16的162份生产源、IR27与release核 `e66a84673d59`，完整400为300通过、19失败、81拒绝，7+393件身份一致，清理400/400。新增324、377，原wave15的298及基线198通过保留，18项旧失败字典不变，077完整运行后仍为原checker失败。两平台IR27安装通过；完整CI2307方法中的1项旧拒绝断言已迁移，30项窄CI加2277项未变旧通过覆盖全部2307项，0方法跳过，原完整CI失败保留。
历史wave12为292通过、18失败、90拒绝，158文件源码、IR25与release核 `83da6b2b521c` 的42+358件身份一致。
原198及有效波10全部278通过保留，新增14份，无回退；18项旧checker失败字典保持。原固定125成员重算为92通过、9失败、24拒绝；历史波11失败候选及波8等旧收据保持原身份。
历史波7逐例比较波6b新增129、137、138、224、233、295、296、380共8份、无回退；相对波5新增35份、无回退。296恢复。
历史wave12的IR25增加native tanh；原checker、精度、证明预算保持。real初态只接有限点包围，integer电压采样仍拒绝。
多项式guard与有限floor已纳入波7，guard乘加中间值溢出在同一冻结release核明确拒绝；历史反例和修复收据均保留。
wave12时111的事件认证仍拒绝；波8纳入[隔离整数输出读取](../math/events.md#settled-integer-reads)及[点held时间证明](../math/events.md#held-time-point-proof)，更广组合仍回退或拒绝。后续Slew、证明缓存和tanh已进入wave12的292。初始化幂乘共享计费与整数证明耗尽退回TOP已独审；Rust457项与2项IR通过，原1项忽略。3项IR身份旧断言已同步为IR25，所属8项重验通过。本地Python2210项收齐，保留旧断言及未优化debug90秒超时原记录；CO-SH-01按既有CI opt1构建和原90秒请求重验通过，1af9772c的完整交付15项CI全部通过，含Python2210项和两平台安装；原漏夹具失败记录保留。原始材料local-only，无新增实际Spectre、正式r53或Q。
四个过时passive夹具已改成真正负start加正period，7/7 private负控通过；合法过去单次timer仍按非正period合同处理。
波5全Python执行2024项、2022通过，一项旧P/2拒绝期待已迁移并复验13方法，CO-SH-01在90秒超时且旧核对照待完成；不报告全绿。

IR21 共同基础已随 [#174](https://github.com/BucketSran/vaEVAS/pull/174) 合入 main，补充 LANG、ANALOG、CROSS、TIMER、EVENT-ORDER、EVENT-CONDITIONS、DYNAMICS、COMPOSE 和 DEV:scs-input。
契约见[局部变量与条件支路](../../validation/ANALOG_CONDITIONS_CONTRACT.md)、
[事件条件与输出记录](../math/events.md)、[连续选路与有理流](../math/continuous.md#selected-flow)。
开发回归包括[顺序初始化和整数类型](../../tests/test_r01_runtime_frontend.py)、
[状态谓词](../../tests/test_r01_event_conditions.py)、[事件选路](../../tests/test_r01_event_select.py)、
[连续选路](../../tests/test_r01_runtime_select.py)、[输出记录](../../tests/test_display.py)、
[事件时间](../../tests/test_event_time.py)、[整数循环](../../tests/test_integer_loops.py)、[模型步长](../../tests/test_bound_step.py)和
[SCS 驱动保留](../../tests/test_scs_driven_nodes.py)。既有[语言](../../tests/test_r01_language.py)与
[纯表达式](../../tests/test_stateless_expressions.py)回归继续保留。
基础有限对照见[最终控制](../../../experiments/backends/support/r01-root-windows/final-controls/README.md)。
原始 70 条件没有最终版本的全量验收；本轮增补与原完整任务结果见下段，历史成绩保留。

[事件数组与独立测量](../../../experiments/backends/support/r01-timing-observers/README.md)
补充 LANG、CROSS、TIMER、EVENT-CONDITIONS、EVENT-ORDER、COMPOSE 的有限开发证据。
契约见[参数与下标准入](../reference/frontend-admission.md)及[独立测量](../math/events.md#passive-observer)，
回归见[原树义务](../../tests/test_event_parameter_specialization.py)、
[事件数组](../../tests/test_r01_event_arrays.py)、[测量事务](../../tests/test_passive_events.py)。
这些控制不增加固定 Q 成绩；原完整 timing 请求的后续连续耦合拒绝单列。

[原70请求的同版复验摘要](../../../experiments/backends/support/r01-main70-summary.json)保留固定 `main@efd17ed6`、0.17.0 / IR21 的工程完成、拒绝与原判据身份，完整资产仍是local-only，不能转为当前 main 的总通过率或论文Q成绩。后续具名交付与未完成项见[工程请求与扩展范围](../COMPARISON.md#engineering-status)。[覆盖缺口](../../validation/paper/COVERAGE.md#engineering-gap-audit)将LANG、DYNAMICS、TRANSITION、COMPOSE及事件需求对应到独立卡规划，不单独授予支持结论。

[隔离事件统计](../../../experiments/backends/support/README.md#event-statistics)补充 LANG、EVENT-CONDITIONS、EVENT-ORDER、TIMER：IR22 的状态分母及 sqrt/abs/min/max 纯事件数学只扩展完整 IR 证明隔离的观察实例。三条原 gain 请求及四个手算控制已实际验收，不新增论文 Q 成绩。合同见[事件数学](../math/events.md#event-math)，独立输入见[统计控制](../../validation/event_statistics/README.md)，回归见[test_event_statistics.py](../../tests/test_event_statistics.py)。

[连续状态与原 timing 请求](../../../experiments/backends/support/r01-causal-timing/README.md)
补充 DYNAMICS、TIMER、TRANSITION、CROSS、EVENT-CONDITIONS、EVENT-ORDER 与 COMPOSE。
契约见[连续因果投影](../math/continuous.md)和[事件条件与观察](../math/events.md)。
原 timing-0 完整执行并通过原 checker，实际有限配对、所有历史失败及未完成原生点分别保留；不增加固定 Q 成绩。
开发回归覆盖[因果状态](../../tests/test_n09_causal_state_readout.py)、[辅助节点](../../tests/test_auxiliary_continuous_roots.py)、[条件步长](../../tests/test_conditional_history_mesh.py)、[时间来源](../../tests/test_held_time_provenance.py)、[精确期限](../../tests/test_exact_transition_deadlines.py)、[等价事件分支](../../tests/test_event_branch_agreement.py)、[被动查询相位](../../tests/test_passive_history_phase.py)与[初始期限](../../tests/test_initial_observer_horizon.py)。

[空循环声明与当前 timer 安全修复](../../../experiments/backends/support/retained-safety/README.md)
补充 LANG、TIMER、EVENT-ORDER、COMPOSE 的 main 适配证据。
非法节点改为编译失败；新生成当前 timer 改为明确拒绝，尚不支持同刻闭包。
五个实际 Spectre 探针和开发回归不改变原表 Q 档及历史成绩。

[旧整链 Q 补验与中断边沿积分](../../../experiments/backends/support/README.md#legacy-chain-q)
补充 TIMER、TRANSITION、DYNAMICS、COMPOSE、QUALIFICATION。
旧整链使用 main `7344e4db` 对应内核代码；[新增前馈积分](../math/operators.md#transition-integral)
纳入 0.15.0 / IR19，支持范围与发布前实际构建、执行身份分别保留。
校准见[完整回调历史](../../tests/test_legacy_chain_precision.py)、
[有向数学包围](../../tests/test_legacy_chain_bounds.py)和[独立边沿面积](../../tests/test_transition_integral_precision.py)，
生产回归见[中断与历史保持](../../tests/test_transition_integral.py)。不覆盖 #131。

[本轮导数与严格组合修复](../../../experiments/backends/support/README.md#capability-gaps)
补充 LANG、DYNAMICS、COMPOSE、QUALIFICATION；两张导数卡与八张组合卡保留实际候选源码、内核、原判据和Spectre对照。
回归见[多项式导数](../../tests/test_polynomial_derivatives.py)、[滤波精度](../../tests/test_filter_precision.py)。
实现已随 #167 合入 main `e028f96d`；原收据的候选身份和成绩保留，不转授任意组合支持。

[新版根窗口实测](../../../experiments/backends/support/README.md#root-window-v3)
补充 CROSS、EVENT-ORDER、DYNAMICS、COMPOSE、QUALIFICATION。固定 SH-X-RAMP 与 EC04-v1 的三档运行，
保留完整回调区间，严格时间语义与有限分辨率验收分别报告；这是判据与证据更新，没有修改 EVAS 求解器。
[新版合同与校准](../../validation/paper/precision-root-v3.json)不覆盖 #131 或其他窗口。

[采样积分与局部 strobe 修复](../../../experiments/backends/support/README.md#sampled-integral-fix)
补充 DYNAMICS、CROSS、TIMER、EVENT-ORDER、COMPOSE、QUALIFICATION。
[独立面积与物理阶段回归](../../tests/test_sampled_integral_strobe.py)、
[非自治强制点负控](../../tests/test_bounded_event_closure.py)及实际五卡三档对照保留原预算。
EC04 的原窗口资格与 #131 冻结范围保留；回调证明只补离散事件，不替代连续输出验收。

[累计测试清单](../../validation/paper/COVERAGE.md)登记历史条件与新 44 组的逐项关系，
涵盖 LANG、LIN、NONLINEAR、TIMER、CROSS、EVENT-ORDER、TRANSITION、ABSDELAY、SLEW、DYNAMICS、COMPOSE、QUALIFICATION。
五层目录整理没有改变实现、判据或成绩。主表按五层固定用例呈现；打勾只表示本行全部必测用例通过，扩展计划和缺证清单分别保留。
L1–L5 是表格导航 ID，不替换下表开发 ID；旧版本、原预算和失败继续保留。

[Q3 支持修复与横线补证](../../../experiments/backends/support/README.md#q3-closure)
补充 LANG、NONLINEAR、DYNAMICS、COMPOSE、QUALIFICATION 的实现与有限证据。
IR19 增加纯数学函数，恒定 PWL 保留原输入位；契约见[纯数学函数](../math/operators.md#elementary-functions)，
回归见[函数测试](../../tests/test_unary_functions.py)、[恒定输入测试](../../tests/test_constant_input_identity.py)，
独立校准见[校准工具](../../validation/calibrate_elementary.py)。
PR208补充[纯输入数学组合的观察点根盒](../math/solving.md#纯输入数学组合的观察点认证)及[公开正反例](../../tests/test_source_math.py)。原237已在wave14完整400通过；该轮295通过；两平台安装通过，完整2245项覆盖经b71317e0窄CI的33项与2212项未变通过复用闭合，原全量CI的两项失败保留。
[无状态 selected-Ln 开发回归](../../tests/test_selected_ln.py)补充 ANALOG、DYNAMICS、COMPOSE 的有限证据：
原源查询、内部 abs/clamp、定义域、隐藏依赖、真实同 owner 预算耗尽与拒绝不提交。
范围见[数学函数](../math/operators.md#elementary-functions)。原135已在提交 `c8dc2a7b` 的163输入、IR28与406d统一400通过原checker；数学与预算、兼容及集成审查和实际root124/11/3检查单列于低成本闭包收据，不据此新增Q计数。
静态输入与回调证书只解除已证明的义务；新旧成绩、具体工具版本和未完组合均在收据中分开记录。
函数修复属于本轮源码交付；#162 的旧运行不计作当前 main 能力，#131 不动。

[原11格后续取证](../../../experiments/backends/support/README.md#evidence-followup)
补充 CROSS、EVENT-ORDER、DYNAMICS、QUALIFICATION 的有限来源证据。
回调记录、实际输入消费者与最终接受状态按固定卡重新核准；新数值分析与旧I并列保存。
这次不修改EVAS生产源码，不将环回侧别或同刻回调直接认定为EVAS缺陷，也不豁免原验收。

[独立基础卡与历史补证](../../../experiments/backends/support/README.md#primitives-main)
补充 LANG、NONLINEAR、DYNAMICS、QUALIFICATION：十卡、三档、四后端共120个新位置，
另重读168份历史配置。新卡固定 main 检查点 `a64c2ad0`，仅验收有限导出值；
不覆盖后续 main、不补造旧事件回调资格，也不回写原成绩。

Q 档精度集的[失败归因复核](../../../experiments/backends/support/README.md#failure-attribution)
补充 CROSS、TIMER、DYNAMICS、QUALIFICATION 的原因证据。它区分事件编译缺陷、已复现的行为错误、
EVAS 回调缺证与严格配置认证拒绝，不改原验收成绩或扩大能力范围。

同日的[严格滤波修复与阈值边界补测](../../../experiments/backends/support/README.md#evas-precision-recovery)
补充 DYNAMICS、CROSS、QUALIFICATION。修复版四个滤波条件通过原 Q3，56 个根附近查询状态正确；
阈值采样的完整回调资格仍未取得。新代码不能直接复用旧源码身份的配置绑定。

[44 组扩展验证](../COMPARISON-METHODOLOGY.md#precision-breadth)补充 LANG、LIN、NONLINEAR、
TIMER、CROSS、EVENT-ORDER、TRANSITION、ABSDELAY、SLEW、DYNAMICS、COMPOSE、QUALIFICATION。
它分别记录数值、行为和取证结果；支持结论仍只在支持总表维护，开发用例不计为独立留出集。

| 能力 ID | 契约或数学入口 | 验证与历史证据 |
| --- | --- | --- |

| LANG | [语法/API](../../README.md#实现范围)、[普通条件契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md)、[局部量旧切片](../../validation/LOCAL_STATE_CONTRACT.md)、[当前顺序初始化](../math/events.md#同块顺序赋值与同刻联立求解)、[编译准入与标准环境](../reference/frontend-admission.md) | [case 开发测试](../../tests/test_case_statements.py)、[局部量/事件状态实际有限配对](../../../experiments/backends/local-state/README.md)、[局部量/事件状态回归](../../tests/test_local_state.py)、[回调临时值与普通别名](../../tests/test_event_ordinary_scratch.py)、[表达式开发测试](../../tests/test_stateless_expressions.py)、[普通边界证书开发回归](../../tests/test_ordinary_boundary_certificates.py)、[EX-01 新 Spectre 有限对照](../../../experiments/backends/input-clamp/boundary-followup.json)、[普通条件历史检查](../../../experiments/archive/pr14-pr15-validation/results/analog-conditions-acceptance-review.json.gz)、[函数开发测试](../../tests/test_user_functions.py)、[函数分支测试](../../tests/test_function_branches.py)、[有限函数 Spectre 配对](../../../experiments/backends/function-branches/README.md)、[循环开发测试](../../tests/test_static_loops.py)、[静态下标源类型与公共内核顺序](../../tests/test_static_loop_integer_type.py)、[事件体循环测试](../../tests/test_event_body_loops.py)、[直接电压整数转换与独立45点oracle](../../tests/test_integer_round.py)、[向量测试](../../tests/test_vector_ports.py)、[测试台适配](../../tests/test_scs.py)、[SCS 向量连接](../../validation/SCS_VECTOR_CONTRACT.md)、[lint 边界测试](../../tests/test_lint.py)、[诊断盘点](../reference/diagnostics.md)、[来源登记](diagnostic-sources.md)、[源码出口清单](diagnostic-inventory.json)、[消费者诊断回归](../../tests/test_diagnostic_consumers.py)、[时序边界原因回归](../../tests/test_timed_boundary_diagnostics.py)、[来源行为回归](../../tests/test_diagnostic_sources.py)、[初始化循环旧切片](../../validation/INITIAL_STATIC_LOOP_CONTRACT.md)、[初始化循环开发测试](../../tests/test_initial_static_loops.py)、[初始化循环实际有限配对](../../../experiments/backends/initial-static-loop/README.md)、[初值/cross 测试](../../tests/test_initial_cross.py)、[输入比较初值](../../tests/test_input_initialization.py)、[八例实际有限配对](../../../experiments/backends/input-initialization/README.md)、[标准数学常量回归](../../tests/test_standard_constants.py)、[未引用私有节点回归](../../tests/test_unused_internal_nodes.py)、[标准头/私有节点实际有限对照与 exact 缺证](../../../experiments/backends/support/frontend-retained/README.md)、[严格准入回归](../../tests/test_compile_admission.py)、[实际准入与观测跟进](../../../experiments/backends/event-alignment/admission-observation-followup.md)；[case 契约](../../validation/CASE_STATEMENTS_CONTRACT.md)；[前端资源预算](../../README.md#frontend-boundaries)、[同请求不可变IR缓存与预算控制](../../tests/test_ir_cache.py) ；[耦合行为源回归](../../tests/test_scs_bsource.py) |
| LIN | [求解](../math/solving.md) | [原矩阵检查点](../../../experiments/runs/parallel-gap-integration/results/event-horizon-checks.json) |
| NONLINEAR | [求解与精度链](../math/solving.md#精度链的已修复反例与边界)、[瞬态契约](../../validation/NONLINEAR_TRANSIENT_CONTRACT.md) | [精度链检查点](../../../experiments/runs/parallel-gap-integration/results/precision-chain-checks.json) |
| SPARSE | [稀疏分支](../math/solving.md#稀疏分支与性能边界) | [当前配对测量](../../../experiments/performance/README.md)、[历史 PR8](https://github.com/BucketSran/vaEVAS/pull/8)；[Issue57](https://github.com/BucketSran/vaEVAS/issues/57) |
| CROSS | [事件数学](../math/events.md)、[根证明](../math/continuous.md#非线性-guard-的根证明) | [精确仿射历史相位回归](../../tests/test_exact_affine_history_phase.py)、[无关滤波、实际依赖与双实例回归](../../tests/test_sample_state_precision.py)、[动态根历史检查点](../../../experiments/runs/parallel-gap-integration/results/dynamic-closure-review-checks.json)、[重定位开发测试](../../tests/test_event_relocalization.py)、[历史重定位回归](../../tests/test_history_relocalization.py)、[精确停止端点及邻接查询回归](../../tests/test_dynamic_cross.py)、[事件/积分拆分对照](../../../experiments/backends/dvs2-spectre-validation/README.md#cross-restart-diagnostic)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[有界局部根及规定拒绝](../../../experiments/backends/ordered-event-sources/candidate-phase/README.md)，不覆盖一般跳变与自换向、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[#70](https://github.com/BucketSran/vaEVAS/issues/70)；[va07 wrong-speed 本地接入](../../../benchmark/material/historyref/tasks/va07-triangle-repair/SOURCE.md#local-evas)；[PR #79](https://github.com/BucketSran/vaEVAS/pull/79) |
| TIMER | [事件手册](../math/events.md)、[定时契约](../../validation/TIMED_OPERATOR_CONTRACTS.md) | [零时刻最终种子实际有限配对](../../../experiments/backends/support/README.md#initial-transition-seed)、[初始化开发回归](../../tests/test_transition_initialization.py)、[固定排序开发回归](../../tests/test_timer_ordering.py)、[近时钟历史组合](../../tests/test_timer_history_order.py)、[有序物理历史续算](../../tests/test_event_history_continuation.py)、[有界因果闭包](../../tests/test_bounded_event_closure.py)、[新容差对照与保留失败](../../../experiments/backends/transient-accuracy/near-clock-history.md)、[SI-01 新参考](../../../experiments/backends/transient-accuracy/core-followup.json)、[动态开发测试](../../tests/test_dynamic_timer.py)、[固定时钟测试](../../tests/test_timer.py)、[同源对照](../../../experiments/backends/dvs2-spectre-validation/README.md#timer-defaults)、[ZOOM 循环事件](../../../experiments/backends/dvs2-spectre-validation/README.md#zoom-static-events)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[有序事件源与物理相位对照](../../../experiments/backends/ordered-event-sources/README.md)，两组各 16 请求满足固定判据，原参考 F/I 保留、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[实际 Spectre 对照](../../../experiments/backends/ordered-event-history/README.md)、[停止边界恢复与实际配对](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#timer-stop) |
| EVENT-ORDER | [生命周期](../math/events.md) | [状态消费者开发回归](../../tests/test_sample_state_precision.py)、[采样/复位新参考](../../../experiments/backends/transient-accuracy/core-followup.json)、[精度链回归](../../tests/test_precision_chain.py)、[历史事件条件对照](../../../experiments/archive/pr14-pr15-validation/results/event-conditions-0.9.0.json)，历史对照不验证本分支新修复、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[有序事件源与物理相位对照](../../../experiments/backends/ordered-event-sources/README.md)，两组各 16 请求满足固定判据，原参考 F/I 保留、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[回归](../../tests/test_shared_counter.py)；[Issue16](https://github.com/BucketSran/vaEVAS/issues/16) |
| TRANSITION | [算子](../math/operators.md#transition) | [零时刻最终种子实际有限配对](../../../experiments/backends/support/README.md#initial-transition-seed)、[初始化开发回归](../../tests/test_transition_initialization.py)、[默认 fall 同源控制](../../../experiments/backends/transition-default-fall/README.md)、[独立回归](../../tests/test_transition_defaults.py)、[历史四参数误差对照](../../../experiments/backends/dvs2-spectre-validation/results/transition-0.6.1.json) |
| ABSDELAY | [算子](../math/operators.md#absdelay) | [两级开发测试](../../tests/test_absdelay_cascade.py)、[专项历史对照](../../../experiments/archive/pr14-pr15-validation/results/operators.json)、[投影开发回归](../../tests/test_history_projection.py) |
| SLEW | [算子](../math/operators.md#slew) | [专项历史对照](../../../experiments/archive/pr14-pr15-validation/results/operators.json)、[投影开发回归](../../tests/test_history_projection.py)、[两级固定前馈](../../../experiments/backends/slew-cascade/README.md) |
| DYNAMICS | [算子](../math/operators.md)、[联合数学](../math/continuous.md)、[限幅候选](../math/operators.md#输入决定的连续限幅候选) | [截止点与矩阵检查点](../../../experiments/runs/parallel-gap-integration/results/event-horizon-checks.json)、[DAE/滤波开发测试](../../tests/test_implicit_filters.py)、[精度细化开发回归](../../tests/test_transient_accuracy_control.py)、[组合筛查与保留回归](../../../experiments/backends/transient-accuracy/composition-screen.md)、[实际容差对照](../../../experiments/backends/transient-accuracy/README.md)、[当前精度复核](../../../experiments/backends/transient-accuracy/precision-audit.json)、[参考精度与观测补测](../../../experiments/backends/transient-accuracy/reference-followup.json)、[单极点独立答案](../../tests/test_laplace_np.py)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[限幅开发回归](../../tests/test_input_clamp.py)、[实际有限 Spectre 对照](../../../experiments/backends/input-clamp/README.md)；[API/manifest/SCS strobe](../reference/strobe.md)；[控制回归](../../tests/test_strobe.py)；[冻结模型](../../validation/strobe/README.md) |
| COMPOSE | [联合数学](../math/continuous.md) | [零时刻最终种子实际有限配对](../../../experiments/backends/support/README.md#initial-transition-seed)、[初始化开发回归](../../tests/test_transition_initialization.py)、[旧根撤销、完整中断边沿与非零历史回归](../../tests/test_al4_lifecycle.py)、[两级调用与回退](../../tests/test_absdelay_cascade.py)、[采样与非线性历史回归](../../tests/test_sample_state_precision.py)、[观察与依赖修复检查点](../../../experiments/runs/parallel-gap-integration/results/lifecycle-observation-review-fixes.json)、[共同验收重构对照](../../../experiments/backends/event-acceptance/README.md)，仅验证行为保持、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md) |
| QUALIFICATION | [验证集](../../validation/README.md)、[追溯矩阵](TRACEABILITY.md) | [提交前审查收据](../../../experiments/runs/capability-completion/review-receipt.json)、[一致初值收据](../../../experiments/runs/capability-completion/joint-dc-receipt.json)、[前一候选收据](../../../experiments/runs/capability-completion/receipt.json)、[合并基线收据](../../../experiments/performance/matrix.json) [实际观察接口](../reference/observation-evidence.md)、[观察证据开发回归](../../tests/test_observation_evidence.py)。；[当前候选表](../../../experiments/backends/paper/candidate-table.md) |
| PERFORMANCE | [求解手册](../math/solving.md#稀疏分支与性能边界)、[只读诊断](../reference/diagnostics.md) | [当前库内与进程测量](../../../experiments/performance/README.md)、[只读输入共享实测](../../../experiments/performance/README.md#direct-input-sharing)、[历史计时](../../../experiments/runs/solver-performance.json)、[事件组合与同机有限对照](../../../experiments/backends/event-alignment/README.md)；[长期候选 Issue138](https://github.com/BucketSran/vaEVAS/issues/138)；[Issue58](https://github.com/BucketSran/vaEVAS/issues/58)；[Issue59](https://github.com/BucketSran/vaEVAS/issues/59) |

旧能力表的逐轮叙事保留在 [整理前的固定版本](https://github.com/BucketSran/vaEVAS/blob/dbeff2f22475ace8644470346a2d097dee6de418/evas/docs/CAPABILITIES.md)。
检查点身份见 [版本记录](../UPDATE.md#检查点身份)。旧 #79、#97 的未完成验收统一由 [#96](https://github.com/BucketSran/vaEVAS/issues/96) 跟踪；关闭入口不表示原差异通过。

2026-10-09 的[当前 main 四后端复验](../../../experiments/backends/support/README.md)补充 LANG、LIN、NONLINEAR、CROSS、TIMER、EVENT-ORDER、TRANSITION、ABSDELAY、SLEW、DYNAMICS、COMPOSE、QUALIFICATION 的有限证据；原边界失败和资格限制保留。

2026-10-10 的[采样到滤波组合](../../../experiments/backends/sample-edge-filter/README.md)补充 TIMER、CROSS、TRANSITION、DYNAMICS、COMPOSE。
同分支的[输入根自动细化](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#adaptive-root)
补充 CROSS、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE；属于有限范围的误差恢复，不改变 timer 的数学日程。
契约见[独立工程条件](../../validation/sample_edge_filter/README.md)，实现数学见[前馈滤波历史](../math/operators.md#transition-filter)，
回归见[公开链路测试](../../tests/test_sample_edge_filter.py)。[后续根窗口修复](../../../experiments/backends/sample-edge-filter/BOUNDARY.md)
保留事件时间到边沿、滤波的包围；4 个新增同源码 Spectre 实验验证容差影响，严格同刻阶段仍有 18 条差异。
18 条记录已于 2026-10-10 按用户决定接受为 [SEF-TIMER-18](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#accepted-timer-18)，
工程对照通过与原严格 FAIL 分开保留；运行身份见收据，实现与本次契约同批交付。任意重叠窗口和其他用例的边界资格未获豁免。
另有 [30 条件回调诊断](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#回调规则的后续实测)，
验证显式正容差下的接受点触发规则；只读回放支持差异归因，不证明 EVAS 独立生成了同一网格，也不需要为本批复制该网格。

[定向生命周期回归](../../validation/sample_edge_filter/README.md#定向生命周期回归)
补充 TIMER、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE 的开发测试：非零计数经过复位闭包、候选丢弃及精度拒绝后只提交一次；
旧边沿持续到延迟激活；保持量复位后滤波状态续存。局部预期由手算给出，不扩大支持范围或 Spectre 边界资格。

[REA 四行边界核对](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#rea-four-boundaries)
保存 EVAS 0.15.0 / IR19、`ff5d0fd9` 本地树的历史诊断，不作为当前 IR23 对齐证据。
该记录涉及 TIMER、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE：原始内存确认 Spectre 在正容差内提前回调，
EVAS 的全部 6,366 行计数符合名义时钟，四行严格差异仍保留；未发现需要修改调度或历史的生产缺口。
该结论限于所测原链路，不授予依赖跳变瞬间先后顺序的新消费者同源码资格。

2026-10-10 增加[按失败原因选择根细化](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#directed-root-recovery)，
补充 CROSS、EVENT-ORDER、COMPOSE 及 DEV:precision-chain 的开发证据。
[恢复测试](../../tests/test_root_recovery.py)检查原预算重验和继承误差保留；
既有路径复用实际 Spectre 数据，新直接非线性采样另完成正向、负向和小幅值三条件的同源码对照。
[12 配置均满足原预算](../../../experiments/backends/sample-edge-filter/direct-sample-receipt.json)，
每个条件均实际触发目标细化。四档只改变 Spectre，有限观测不授予普遍精度或历史重放能力。

2026-10-10 的[采样保持与一阶滤波精度实测](../../../experiments/backends/support/README.md#precision-pilot)
补充 TIMER、CROSS、DYNAMICS、COMPOSE、QUALIFICATION。冻结 8 个条件和四档设置，
保留定时采样的 strobe 拒绝及普通查询补测；不改变 EVAS 生产行为或旧批次验收结论。

后续[固定 timer 强制点修复](../../../experiments/backends/strobe/README.md#timer-fix)
补充 TIMER、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE、QUALIFICATION。
原 12 配置在对应修复的运行快照中重新通过；以强制点回执验收，不把普通查询提升为接受帧。
旧拒绝及 Spectre 请求/原生时间偏差仍保留，完整原始数据为 local-only。

2026-10-11 的[单次滤波链预算分配](../../../experiments/backends/sample-edge-filter/BOUNDARY.md#filter-budget)
补充 CROSS、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE 与 DEV:precision-chain 的开发验证证据。
[数学与准入](../math/events.md#filter-root-budget)区分全响应灵敏度提案和最终数值认证；
新增测试台观测事件补齐原生点后，单案例按原规则选中 `tol`；旧失败和新未达标档位保留。
具体后端覆盖以该记录为准，不扩展一般多事件或历史重放支持。

固定外部多项式输入的滤波直接通路补充 DYNAMICS、COMPOSE：
[数学与准入](../math/continuous.md#固定外部多项式输入的直接通路)、
[开发回归](../../tests/test_filter_direct.py)、[实际 Spectre 有限对照](../../../experiments/backends/filter-direct/README.md)。
这仅交付 #66/C4 的前馈切片，内部非线性反馈与事件仍未纳入。

2026-10-11 的[近邻 timer 强制点](../../../experiments/backends/strobe/README.md#near-timer)
补充 TIMER、EVENT-ORDER、TRANSITION、DYNAMICS、COMPOSE、QUALIFICATION。
固定／精确保持时钟及连续组合共 12 个 EVAS 配置通过；Spectre 10/12，通过范围按固定顺序选档。
连续组合的两个原预算失败和更广局部历史闭包限制保留，不关闭 #96/#119。

2026-10-11 的[当前 main 复验](../../../experiments/backends/support/README.md#current-main)
补充 TIMER、CROSS、SLEW、DYNAMICS、COMPOSE、QUALIFICATION 的集成证据。
复验沿用原判据，未扩展能力定义；逐配置版本和结果见收据，支持结论仍只在支持总表维护。

2026-10-11 的 [v2 精度扫描](../../../experiments/backends/support/README.md#precision-v2)
补充 TIMER、CROSS、DYNAMICS、COMPOSE、QUALIFICATION 的有限证据。
新检查器按同一数学参考验收 Q1～Q3，保留合法回调窗口的全部不确定区间和初始保持阶段；
160 个运行配置与原 v1 成绩分开保存。缺少时刻或生效设置证据时不授予通过，
未修改 EVAS 生产行为，也未迁移旧 core 或其他组合的判据。

同日的[配置绑定与补证](../../../experiments/backends/support/README.md#precision-bindings)
继续补充 TIMER、CROSS、DYNAMICS、COMPOSE、QUALIFICATION 的验收依据。
新增 16 次外部后端运行，EVAS 复用首轮相同实现及原生记录；Q 档位、实际配置和验收要求已绑定。
数值、行为与证据状态分别保存，EVAS 阈值采样的回调缺证及极严配置拒绝继续保留。
原 v1/v2 判据与成绩未改写，#131 未动。

[有界运行期事件控制](../../../experiments/backends/support/event-runtime-control/README.md)补充 LANG、EVENT-CONDITIONS 和 EVENT-ORDER：三个实际 Spectre 控制按原 100 nV 门槛及精确整数答案验收；4096 迭代、signed32 中间检查、数组边界及晚失败回退见 test_event_runtime_loops.py。原 CDS 整题尚未完成，不新增 Q 成绩。

保持目标中的嵌套 held `Select` 补充 TRANSITION 与 EVENT-CONDITIONS，见[原算式、结构负控与有限参考](../../../experiments/backends/support/held-transition-targets/README.md)。这里只验证保持量目标的分支展开，不表示完整 MUX 模型或历史谓词已经支持。

[主动初始化输出的本地回归](../../tests/test_active_initial_output.py)补充 LANG、EVENT-ORDER、
TRANSITION、COMPOSE 的开发证据，覆盖常量初始化快照、analog strobe别名与固定小数格式。
主动模型仍拒绝初始电压/历史观察和状态写入型原始IR；独立审查已闭合，原076已在wave14完整400通过，且在wave15保留；交付覆盖与历史失败见低成本闭包收据。

[受限原生事件floor](../../tests/test_native_event_floor.py)补充 LANG、EVENT-ORDER、CROSS、
EVENT-CONDITIONS、COMPOSE 的本地开发证据，契约见[原生事件floor](../math/events.md#native-event-floor)。
旧有限表IR逐字对照仅排除schema版本差异；同控制器跨bin失败/重试与精确有理取整预算分别由
transient_passive_tests.rs、event_value_proof.rs覆盖。原244已在wave14统一400通过，且在wave15保留；两平台安装与逐ID复用覆盖见低成本闭包收据。

[闭合初始化实数幂开发回归](../../tests/test_constant_initial_power.py)补充LANG、COMPOSE和NONLINEAR-TRANSIENT：初始只读AST经既有Ln/Exp与原关系root boxes消费，保留原除法、所有权及数值误差。只有单条闭合real初始赋值、无其他观察者/writer的有限结构进入新路径；运行期实指数不在此范围。独立审查已闭合，原120在wave15同源完整400通过原checker；实际原请求沿用120秒内核、150秒guardian及原精度，不据此提升Q计数。

[精确DC供电系数与history guard投影](../math/events.md#精确dc供电系数与history-guard投影)补充CROSS、EVENT-CONDITIONS、TRANSITION和COMPOSE。
[test_dc_factor.py](../../tests/test_dc_factor.py)覆盖幅值、符号、非零参考、跨实例所有权与放大后的原误差预算；同owner耗尽与失败重试有私有控制。
原111在wave15同源完整400通过原checker；一般变化供电、非零误差和更广联合仿射历史仍拒绝。

[事件体纯输入别名](../../tests/test_event_body_input_aliases.py)补充LANG、EVENT-ORDER和COMPOSE。
只有原始标量唯一前序写者可进入新body映射，trigger和setting保持原映射；
数组与零次循环原写者不得在展开后绕过资格，旧仿射数组及loop响应有独立字节对照。
原377已随wave16统一IR27候选通过完整原checker；同批324也通过，统一400为300/19/81，不以局部结果另行相加。

[原生事件整数](../../tests/test_native_integer_events.py)与[有界冷Transition种子](../../tests/test_transition_bootstrap_bounds.py)
补充LANG、EVENT-ORDER、TRANSITION和COMPOSE。IR27只扩展事件体typed Add及常量非零Remainder，
每节点signed32检查及预算耗尽沿原owner保持。冷种子桥只借用真实Prepared.bounds初始化全Transition图中的裸同实例real状态目标，
并保留固定timer0调度门、初始电压认证及同Controller失败重试；更广初态和历史组合仍拒绝。原077已完整执行，但原checker仍为FAIL。首个失败是原网格跨边沿插值，实际查询保持值正确；诊断不改变原FAIL，后续性质未重评，未计077新增PASS。

wave17已验收IR28候选的[事件typed余数与减法合同](../math/events.md#事件体运行期余数与二元减法ir28-本地候选)
及[公共正反控](../../tests/test_native_integer28.py)补充LANG、EVENT-ORDER、EVENT-CONDITIONS与COMPOSE。
同源统一候选的原069、335已通过原checker，完整400为302/19/79；单次完整Python2314项及两平台0.21/IR28安装通过，范围仍限上述合同。
历史独立Ln135 pilot固定163输入、IR27与release核 `f1fe352c6c61`；该pilot保留原身份，不参与wave18计分，135只按本轮IR28统一400结果计入。
IR29位运算与纯保持目标、原树事件Floor、无状态源因子和字面零电流支路已合入本地候选，合同见[算子手册](../math/operators.md#native-held-bits29)。新增公开正反控见[整数保持目标](../../tests/test_native_held_bits29.py)、[原树Floor](../../tests/test_source_floor_event.py)、[源因子](../../tests/test_source_factor.py)与[零电流](../../tests/test_scs_zero_current.py)。定向测试和各lane审查不替代同源统一400、完整Python与安装验收，本候选尚不改写历史303。history-forcing仍在隔离快照，0统一原件信用。

[按需期限根与付费精确dyadic包围](../../../experiments/backends/support/low-cost-closure/source-budget-foundations.json)补充EVENT-ORDER、TRANSITION与COMPOSE的局部开发证据。IR31主候选联合控制69个去重Rust方法与25个Python方法通过，默认请求预算耗尽与完整Controller回滚保留；041仍在56.4/68ns处预算拒绝，未运行checker，不新增完整400成绩。独立5089例只验证数学函数，不替代真实owner计费控制。


IR32本地共同候选涉及LANG、COMPOSE、TRANSITION、DEV:scs-input、CROSS、TIMER、EVENT-ORDER：
普通保持历史消费者、受限共享Forcing和解析源值已合批，联合199个唯一Python方法、110个不同lib测试及6个native测试通过。
原369、371完整请求仍在1e9预算拒绝，原346仍未闭合；完整400、完整Python CI及安装待验收，不增加既有317成绩。
全量迭代已观察到旧PASS027因typed目标聚合审计超出原100000预算而回退；修复与重验未闭合，本候选不满足旧通过保留条件。
显式typed源值、PWL根窗采样和direct-held事件，合同见[事件手册](../math/events.md#ir32-private-candidate-explicit-analytic-source-values)。
本条只导航候选合同，不增加成熟支持、共同Q或400通过数；Spectre默认和一般history组合仍未支持。
