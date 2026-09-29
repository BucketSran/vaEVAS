# 事件条件赋值与采样复位：第一阶段契约

状态：**分批实现；0.8.0 / IR v8 已接入受限事件 if/else，尚未接入 OR，也无原 8 条件通过结论。**
设计来源 `5b090571c7de7c6ec08a05c803479505c5d745ee`；本轮在分支 `feat/evas-event-conditions`
同步 main `a0c80431278988b66aa6cd8b725b44e1862ece17` 后实现，停止于可 review 的本地检查点。
以下完整目标继续约束后续 OR 接入；原设计阶段事实和校准结果不当作本轮仿真证据。
当前实现、数学与精度边界以[事件手册](../docs/EVENTS.md#event-conditions)为准。
能力归属为 LANG、CROSS、EVENT-ORDER、COMPOSE；依赖已有 TRANSITION。
本地数学检查的组数不是模型条件数，也不改变原 31 条件的分母。

## 1. 固定目标与依据

后续实现目标固定为以下 8 条件，模型、刺激、原检查器和阈值不改；8 是范围而非通过数。

| 条件 | 原始源码及独立契约 | 本次涉及的行为 |
| --- | --- | --- |
| v4-c0、v4-c1 | [d2_v4_01](cases/d2_v4_01/dut.va)、[V4 卡](CASE_CARDS.md#d2-v4-01斜坡采样保持与沿间复位) | 采样、保持、沿间复位、复位期间抑制采样 |
| e2-low、e2-clock-high、e2-reset-high | [n_v4_02](cases/n_v4_02/dut.va)、[E2 卡](NEXT_CASE_CARDS.md#n-v4-02初始高电平与恢复e2) | 初态、持续复位、释放及恢复 |
| c1-main、c1-swapped、c1-no-reset-a | 同一 n_v4_02、[C1 卡](NEXT_CASE_CARDS.md#n-v7-03有状态实例隔离c1) | 双实例的参数、状态和算子历史隔离；声明顺序不变性 |

刺激及参数以 [run_suite.conditions](../../experiments/dvs2-spectre-validation/run_suite.py)
和其引入的 [suite.conditions](../../experiments/dvs2-starter-pilot/suite.py) 为固定入口。
原判据为 [check_results](../../experiments/dvs2-spectre-validation/check_results.py)、
[history](../../experiments/dvs2-history-validation/history.py) 及原 v1 checker。
保持平台目标仍为 1 mV；原观察误差预算、事件时间允许域、原单位和两档设置全部保留。
这些原条件没有精确同刻时钟/复位竞争；不能用其通过证明同刻去重或优先级。

2026-09-29 从官方地址读取了
[Accellera Verilog-AMS LRM 2.4.0（2014-05-30）](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)。
PDF SHA-256：`621b2a1a3751e7685600f180fe8f362766fe13e952023ded3d7ae48314337c03`。
正文不分发规范全文。来源层次如下：

| 层次 | 本契约使用内容 |
| --- | --- |
| 规范 | §4.2.5 关系运算及其低于算术的优先级；§5.3 块内顺序；§5.7 过程赋值；§5.8.1 if/else；§5.10、§5.10.1 事件 OR；§5.10.2 初始化；§5.10.3.1 cross 方向与定位窗口；§4.5.8 transition |
| EVAS 首版选择 | 仅 cross 的 OR；可认证的状态独立谓词；同根同块一次执行；不同块分别执行；同刻仿射联立；歧义拒绝；严格的单写者范围 |
| 数学推导 | 下述集合、顺序代入、依赖证明、区间判真及有理数样例 |
| 固定源码事实 | 下述入口均指上述基线，不是 idt 分支将来交接后的接口 |
| 后端观测 | 只引用仓库已有身份明确的历史证据；本次没有执行 Spectre 或旧 EVAS，也不据此推断其内部算法 |

LRM 的 OR 说明支持任一子事件触发后续语句；它本身不提供本实现的浮点同根证明、
批次去重算法或所有模拟器的回调次数保证。以下一次执行是明确的 EVAS 首版契约。
初始 cross、PWL 触零/平台到达沿用[事件手册](../docs/EVENTS.md)的已审查边界；
手册中尚有旧版本叙述，实际身份和历史认证范围以本基线源码及
[算子手册](../docs/OPERATORS.md#历史误差与电压精度)为准。

## 2. 从首个失败到完整路径

原源码只读 Parser 探针在本基线给出：

```text
d2_v4_01/dut.va:18:30: unsupported or invalid token '>= 0.5)…'
n_v4_02/dut.va:16:30: unsupported or invalid token '>= 0.5)…'
```

词法器预先扫描全文，故先遇到比较 token 的失败，不能由此认为前面的 OR 已能解析。

| 层 | 已有事实 | 必要增量 |
| --- | --- | --- |
| syntax.py | token 不含比较符；Event 为 kind/arguments/assignments；body 只解析平铺赋值；一个 @ 仅一个调用 | 比较词法最长匹配且保留 `<+`；事件 OR；递归顺序 body、if/else、空语句、最近 if 的 else 绑定、源码位置 |
| frontend.py | 单事件 lower；常量 initial_step；instance state；integer 限定；算子在贡献中 | 递归绑定谓词和两臂；保留顺序/结构依赖；路径的写集合；独立调用点身份；不可把两臂拼为都执行的 assignments |
| Python/Rust IR | schema v6；单 trigger；平铺 assignments；serde 拒绝未知字段 | 一次协调的 schema 变更；触发叶子身份与单 body；有类型的谓词/语句；版本与恶意原始 IR 验证 |
| events.rs / event_accuracy.rs | 单 guard 对齐 event 索引；状态/算子结构依赖检查与 guard 区间传递 | 叶子索引与 block 索引解耦；谓词独立性及真值证书；遍历所有路径的写者/类型检查 |
| schedule.rs | 每一 ScheduledEvent 对应 event；同根认证后规范化时间 | 保留每个子触发的定位证据/容差，再按 block 去重；不能先丢掉重复叶子证据 |
| settlement / bounds | 三条路径分别顺序代入、数值重放、原 IR 区间重建；缓存仅按 event IDs | 三条路径必须一致选择分支；缓存包含分支路径；不让选支绕过原方程和误差验收 |
| transient.rs | 候选帧克隆算子；assignments 用于 changed-state；原子提交记录和游标 | 接收已选 body 和实际赋值集合；一块一条记录及子触发证据；失败时所有新数据均不提交 |
| transition | 已有连续边沿与实例内调用点历史 | 接收通过认证的新 held 目标；保持误差区间、重复目标及中断历史；本任务不重新实现算子 |

比较支持不等于采样器支持。贡献继续进入联立方程；过程赋值只更新离散变量，
不能将 `V(vout,vref) <+ transition(...)` 改成节点写入或把 cross 换成预定 timer。

## 3. 触发集合、初始化与观察

事件块身份 B=(实例身份，源码事件控制位置/编译后 block ID)。每个 cross 调用是
叶子 L=(B，调用点 ID)，具有自己的 guard、方向、容差及出现序列。身份不以变量名代替。
设叶子 j 的已证明根事件集合为 E_j。单个 `@(cross(...) or cross(...))` 的触发集合为
`E_B = union_j E_j`。OR 是事件集合合并，不是电压布尔或，也不短路禁用后面的 cross 监测。

- 同根证书证明两个子触发代表同一数学根，并且统一代表时间满足每个叶子的容差时，
  一次执行该 B 的 body。记录完整 fired-leaf 集；重复相同叶子表达式也不能重复执行。
- 全局同刻批次包含不同 B 时，每个 B 执行一次。即使代码文本、guard、目标值相同，
  两个独立块也不能合并。不同实例尤其不能因变量都叫 held 而合并。
- 去重键是 `(B, certified occurrence)`，不是 `(B, rounded time)`、表达式字符串、
  模型名或“落在 ttol 内”。保留实际发生过但未改变 held 的事件。
- 不同根可证明有序时分别执行，即使距离小于 ttol。定位区间重叠但既不能证同根又不能
  证顺序，或两个不同根无法用可表示时间有序执行，返回 `event_resolution`。
  同根后选代表时间仍须复核全部叶子；去重不降低候选数量预算，防止 OR 放大逃过预算。
- 安装 initial_step 常量和算子初值后求初始电压。cross 不因 t=0 已高或等于阈值而触发；
  初始高 clk 不取样。初始高 rst 下 held 仍取源码初值；后续 clk 触发时执行复位臂。
  rst 下降只释放，本模型的 +1 cross 不在释放时取样。
- 本基线到达精确零的规则保持：非零到零按到达方向产生一次；零平台和零到非零不产生
  新事件；stop 处到达同样处理。这不是用 `abs(guard)<tol` 代替精确零。
- `output_times` 只规定观察；恰在事件时刻返回提交后状态。transition 正边沿保证目标改变
  时电压连续，所以事件后 held 可以已改变而 y 尚等于旧电压。稀疏网格不能删事件。

## 4. 条件与顺序赋值的数学对象

首版接受事件体内 `if (lhs <|<=|>|>= rhs) statement [else statement]`；算术两侧须为
实例常数或可认证的状态独立仿射电压表达式。可嵌套 if/else 与 begin/end；无 else 表示不执行
该分支的赋值。先支持四种关系比较足够覆盖目标，不默许布尔算术、`==/!=`、`&&/||`、
三目、循环、事件嵌套或普通 analog 限幅。initial_step 仍为每个状态一次常量初始化。
事件体中的贡献及有历史算子继续拒绝。所有分支都做静态合法性检查，运行时只执行选中臂。

令 e 为整批接受的事件时间，q−、H− 为此前已接受状态/历史。先在候选副本中推进到 e 的
到期历史，得到 H_e 及其区间。同刻系统为：

```text
q+ = Phi_path(q−, v+, u(e))
F(v+, q+, H_e, u(e)) = 0
```

**条件和赋值都在 e 的同一电压视图上定义**，不是上个输出点、上个接受时间或旧节点 v−。
每个 B 从同一 q− 建立自己的局部状态，沿选中语句顺序代入；后句读到该块前句的新值。
没有被选中路径写入的状态保持 q−；每次实际 integer 赋值都要通过精确性/范围检查，
后句写回合法数值不能掩盖中间溢出。
相同状态可在同一块两臂及多个顺序位置出现；收集全部路径写集合后，它仍只有一个 B 写者。
不同块写同状态及直接读别块所写状态仍拒绝，不按源码顺序偷偷决定优先级。

### 4.1 为什么可以先判分支

固定拓扑的仿射方程写成 `A v = D u + B q + C H + b`。若可认证唯一解，
谓词差值 `p=aᵀv+c` 可写为 `p=αu+βq+γH+δ`。首版要求结构检查排除到 q/H 的依赖，
并用原 IR 的区间系数消元证明 β=γ=0；系数“很小”、浮点抵消或一次数值解相同都不是证明。
实现可复用 `check_guard_dependencies` 的支路分组、排除已驱动节点/地的保守连通性，
再复用 `GuardBounds` 的独立消元思想；不能把一个 input 端口方向声明等同于实际固定驱动。
无证明时拒绝，即使另一个精确代数方法本可消除依赖。

因此对于任何候选 q+、H_e，p 的值都相同；在**当前 e** 求得的无状态子系统电压可以用于选支，
证明其等于最终 v+ 在该谓词上的投影。以前时间的电压没有这个性质。首版连直接读取 q− 的
谓词也暂不支持，避免把前句赋值后的局部变量或候选电压反馈伪装成固定前态。
普通赋值 RHS 保留当前已支持的同块状态算术和仿射电压采样，谓词限制不倒退这些能力。

这足以覆盖两份共用源码：rst/vref 为固定 PWL 驱动及地，谓词与候选 held 无依赖；
采样 vin 在目标 8 条件中也为固定输入。允许的内部节点例为 `z=2*rst-1/4`，
`z>=3/4` 与 `rst>=1/2` 等价，但必须实际证明其无状态依赖及电压唯一性。

### 4.2 等号与不可判定

令差值的可靠包围为 P=[l,h]，比较阈值为 0：

| 比较 | 可证真 | 可证假 | 其他 |
| --- | --- | --- | --- |
| p >= 0 | l >= 0 | h < 0 | 不可判定 |
| p > 0 | l > 0 | h <= 0 | 不可判定 |
| p <= 0 | h <= 0 | l > 0 | 不可判定 |
| p < 0 | h < 0 | l >= 0 | 不可判定 |

精确 [0,0] 下 `>=` 为真、`>` 为假；[0,h] 的非严格比较可判真，不能一律要求区间不含零。
跨零包围不能用代表值、固定 epsilon、expr_tol、vabstol 或源码优先级选支。
允许有界精化或可靠的精确零/符号证书，仍不能判定时明确失败。只有确切同一仿射关系在
**当前代表时间 e** 被证为零，才可复用根证书；“本次 cross 触发了”并不证明此时表达式等于零。
实际 cross 时间可能位于根后的允许域，故严格 `>` 在根后可以为真。

为避免 PWL 插值舍入在等号边界翻支，本设计要求谓词认证包含 `Trajectory::value_bounds(e)`，
以及无状态网络消元误差。浮点 `values(e)` 是求解代表输入，不能独自充当精确真值。
若使用精确符号证书，重放时也须验证证书，不能又用裸浮点比较推翻它。

### 4.3 复位优先来自代码，不来自调度器

在共用模型中，每次 B 触发均执行 `if (rst>=.5) held=initial; else held=vin`。
两个上穿精确同刻时只有一次 body，rst=.5 或已在高侧，所以执行复位臂。
持续复位时每个 clk 仍会触发 body，只是 held 不变；这不等于停用时钟 cross。
将谓词改为 `>` 会改变精确根处结果；不能靠“reset 子触发优先”覆盖源码差异。
若 clk 上穿恰逢 rst 下降到 .5，只有 clk 是激活叶子，但 `>=` 在该时刻仍选择复位；
这也是源码比较的边界，不可将“释放发生了”解释为立即采样。
两个独立块分别对 held 赋复位和采样的编码仍属于多写者拒绝域。

同刻反馈谓词首版一律拒绝。例如 `V(o)<+q; if(V(o)>=.5) q=1; else q=0`
有两个自洽解；把两臂改为 0/1 则无解；改为 .75/1 虽有唯一解，仍超出本次谓词依赖域。
不能从旧 q 选一个臂再声称唯一解。相比之下，选支已由独立输入确定后，赋值 RHS 与电压的
仿射反馈可沿用已有同刻联立求解；无唯一解、原关系不一致、误差界超预算均拒绝。

## 5. 历史误差与原子提交接入

旧状态和算子历史已带误差包围。一次事件的正确性至少有两个不同义务：
**分支真值已证明**，以及**该分支下的解/新历史误差已认证**。残差不能替代任一义务。

1. 从 accepted 帧克隆候选历史；在 e 推进到期算子，冻结连续 transition 当前值及区间。
2. 对所有激活 B 沿所选路径实际到达的谓词，在当前输入/无状态电压包围上认证真值，生成只读 path 证书；
   若任一不可判定，不执行/提交任何 body。
3. 沿选中路径构造 Phi，保持逐句赋值和中间 integer 检查；同批代入原贡献方程求 v+。
4. 独立重放原 body 和谓词证书，检查原方程、状态一致性。区间路径从原 IR 重建，
   不能直接信任数值执行器给出的线性化系数或 unchecked 路径位。
5. 用 q−、H_e 的原包围传播到 q+ 和 v+；更新 transition 目标及其区间，并检查队列次序。
   仅实际执行的赋值参与 assigned-state 集，无 else 的不写路径不能伪造新目标。
6. 所有条件通过后才整批提交时间、状态/包围、电压/电路、算子队列/历史、所有叶子游标、
   去重消费状态和事件记录。错误、丢弃或重试必须保持旧帧及记录长度不变。

实现增量：0.8.0 的含条件模型将 `Trajectory::value_bounds(e)` 传入谓词和 `Bounds::check`，
数值解使用代表输入，候选认证使用原 PWL 包围。该模型在普通步和跨事件中也保留旧状态包围，
即使没有 transition。无条件旧路径维持原精度契约，不宣称已补齐所有连续时间误差链。
电压 `vabstol+reltol*abs(v)`、real 状态仅相对项和 integer 精确等预算不变；
源到 IR 舍入、名义事件定位允许偏移与连续时间观察资格仍分别说明。

每个 EventModel 内的证书缓存键为激活块 ID、选中赋值索引及分支决定；只缓存系数。
每次试算/重放重新认证路径；原程序身份由缓存的模型所有权固定。空分支不伪造写目标。

## 6. 完整目标的语义 IR 与接口边界

下列为完整目标草图。当前 IR v8 已实现 ordered body、Assign、If 及四种 Compare，
实际 JSON 见[迁移说明](../README.md#ir-v8-migration)；AnyCross 仍是下一批目标。

```text
EventBlock(origin, trigger, body)
trigger := existing single Cross | existing single Timer | AnyCross(nonempty Cross leaves)
body := ordered Statement list
Statement := Assign(state, existing Expression)
           | If(Compare(relation, lhs, rhs), then_body, else_body)
relation := lt | le | gt | ge
```

单触发器语义保留；AnyCross 首版不含 timer、initial_step、嵌套 AnyCross 或逗号别名。
空 body 合法，空 AnyCross 非法。当前赋值用事件来源及 body 索引定位，比较另有源码来源；
AnyCross 的叶子来源和记录是后续交付内容。
比较是控制节点，不塞进可数值求值的通用 Expression，也不新建另一套算子/历史类型。
静态合法性应在 Python 和原始 IR 的 Rust 入口都执行，未选中的非法分支不能逃过验证。

内部流建议为 `leaf occurrences -> certified same-time group -> unique active blocks ->
certified selected paths -> settlement candidate`。选择结果带原 IR 路径与实际写集合，
分别供数值代入、独立区间构造、重放和 transient 的目标更新使用。
记录一条 block 执行及其 fired leaves；根包围、代表时间、方向/容差均能追溯到叶子。
事件体执行次数、叶子命中次数、状态变化次数是三个不同数，不混在一个计数里。

| 层 / 文件 | 当前实现与后续边界 |
| --- | --- |
| `syntax.py`、`frontend.py` | 已有递归 body、比较及实例绑定；OR 语法仍待补 |
| Python/Rust `ir` | 已协调为 schema v8；body 有 assign/if 类型；EventRecord 沿用单触发格式 |
| `event_conditions.rs`、`events.rs` | 全分支合法性、保守依赖、可达选支、重放及路径缓存 |
| `event_accuracy.rs`、`schedule.rs` | 前者复用仿射包围证明谓词；后者未改，OR 叶子去重待补 |
| `settlement.rs`、`settlement_bounds.rs` | 选中路径与原 IR 区间重建，接收 PWL 输入区间 |
| `transient.rs` | 仅选中赋值参与目标更新，候选帧整批提交；3 项新实际帧恢复测试 |
| `test_event_conditions.py` | 20 项开发回归；不是原 8 条件动态回放 |

本轮复用 `pwl.rs`、`operators.rs`、`affine_bounds.rs` 的既有接口；没有修改矩阵求解算法。
`solver.rs` 和旧事件测试的变化仅为内部选择/结算签名及 IR v8 fixture 迁移。

## 7. 独立答案、覆盖与缺口

原 8 条件的答案继续复用独立卡与既有 checker，不复制原刺激、不覆盖原结论：

| 组 | 名义执行/保持答案（x=t/T） |
| --- | --- |
| V4 | clk=.5,1.5,2.5,3.5；rst=1.15；vin=.2+.15x。C0 平台为 .1,.275,.1,.425,.575,.725；C1 在 1.5 仍执行但保持 .1 |
| E2 | clk 同上；后段 rst=2.15；vin=.8−.1x。low/clock-high 的 2.5 事件保持 .1；reset-high 的 .5 事件也保持 .1；释放不执行 |
| C1 | A 同 E2；B 在 .75,1.75,2.75,3.75 取 .275,.375,.475,.575，初态 .3；A reset 不影响 B；no-reset-a 的 A 在 2.5 取 .55 |

它们的 nominal root 不是强制后端实际事件时间。每个实际时刻 e 必须在原合法窗口内，
取样目标、边沿起点、后继保持平台共用 e。窗口宽度：clk 为 T/25000，rst 为 T/50000；
V4 采样偏移电压至多 6 µV，E2/C1 至多 4 µV（另外计输入/观察误差）。
`histories()` 主要记录改变输出目标的事件，会省略复位期间不改变 held 的 clk；
它不能独自证明 body 次数。新运行须同时校验内部记录或独立计数探针，探针不替代原模型。

已有覆盖只读核对：`test_events` 有初始高/零、平台/终点、方向、实例、网格和近邻事件；
`test_settlement` 有顺序赋值、联立反馈、原关系/前向误差；`test_transition` 有重复目标、
中断边沿、调用点隔离；Rust transient 有丢弃、误差失败及重试回滚。
`test_checks` 已有 E2/C1 手算锚点、错误输出、输入/导出校准；history 测试已有
共同事件见证与逐点合法但整条不相容的反例。上述现有测试均不证明新条件 IR 已执行。

本次新增校准采用标准库 Fraction，无 EVAS import、无旧执行器、无求解内核。
全部新样例是开发数学样例，不新增正式条件，不更改 8 条件：

| 新样例 | 独立答案与检错目标 |
| --- | --- |
| EC-OR | 同 B 的 clk/reset/重复 clk 在 e=1 合为一次，保存全部叶子；两个 B 则两次，两个实例也不合并 |
| EC-BOUNDARY | rst(e)=.5：`>=` 复位、`>` 采样；当前时间输入与上次观察值不同，检出旧值猜分支 |
| EC-SINGLE | clk 单独取样、rst 单独恢复初值；下降释放不执行；初始高没有伪事件；持续复位期间 clk 仍计数 |
| EC-NEAR | clk=1、rst=1+δ，δ=1/2000 或 2^-20，顺序两次；反向次序两次但均复位；不能按 ttol=.001 合并 |
| EC-WAVE | 上述近邻例初态 .1、vin=.25+.125x、D=.025；先升至 .1+11δ，复位后斜率 −11，于 1+2δ 回到 .1；精确同时则全程 .1 |
| EC-PREDICATE | 真/假/不可判定及精确等号；任意小的确切正负数仍有符号；仿射输入变换；微小状态依赖不能忽略 |
| EC-SEQUENCE | 选中臂前后都保留顺序赋值及中间值；无 else 的不写路径保持原值 |
| EC-FEEDBACK | 上述两解、无解、唯一但超域的谓词反馈；说明不能盲猜分支 |
| EC-INVARIANCE | 声明/叶子顺序置换及观察网格变化，对同一精确事件历史/保持函数答案不变，并各自核对绝对答案 |
| EC-CALIBRATION | 正确序列接受；漏/重复/额外释放事件、错分支、错实例拒绝；事件/谓词区间歧义保持不可判定 |

EC-WAVE 仅手算这个相等上/下沿的两次目标变化，不另造通用 transition 执行器。
δ=2^-20 的尖峰可能低于原 1 mV 阈值且落在稀疏观察之间：数学样例知道它存在，
不能据稀疏相同输出声称实际 checker 检出了它。事件次数和波形精度分开验收。
精确根样例的区间单点是**给定数学证据**，不能替代未来 Rust 的同根证书生成测试。

### 后续实现必须补的动态检查

- 直接运行原 8 条件，原模型/刺激/阈值及失败分母不变；报告每条件编译、执行和数值结论。
- 新合法/拒绝 VA 与恶意 raw IR；OR 两子触发/重复叶子/两块/实例置换；边界 `>=`/`>`；
  条件嵌套/无 else/顺序中间值；极小依赖、非线性及状态/算子反馈谓词拒绝。
- 同一 B 交替选择复位和采样，验证证书缓存随路径变化；改变观察网格/max_step，绝对答案仍成立。
- **同一 EventModel、Trajectory、accepted Frame 上**，分别注入不可判定谓词、选中臂中间
  integer 溢出、原关系/前向误差失败、历史队列次序失败；断言时间、q/包围、电压、调用点
  历史、游标、叶子消费及记录未变，再从该帧重试成功并仅执行一次。新进程重跑不是此回滚证据。
- 既有全 Python/全 Rust 的共享 IR gate 及相关事件/transition 回归随接入运行。
  pure math/checker 成功不能抵销这些未运行项；本次不运行远程矩阵。

## 8. 原设计阶段的历史复核

```sh
python3 -B evas/validation/check_event_conditions_math.py
PYTHONPATH=experiments/dvs2-spectre-validation python3 -B -m unittest -v test_checks
PYTHONPATH=experiments/dvs2-history-validation python3 -B -m unittest -v test_history test_recheck
git diff --check
```

新脚本输出数学组/校准结果、检查器 SHA-256，且明确 `simulators_executed=[]`、
`engine_rollback_verified=false`。既有 checker 校准的重跑不构成历史后端结果的新执行或重判。
本阶段本地检查结果：新增数学/序列校准 **14 个 unittest 方法通过**；既有 `test_checks`
**8 个方法通过**；`test_history test_recheck` **17 个方法通过**。它们不是 39 个仿真条件。
两份原模型的只读 Parser 探针均复现第 2 节的词法拒绝；没有执行任何模拟器内核。
本文件的本地链接/章节锚点已核对；最终提交前检查两文件 diff 的空白与写入范围。
该设计提交结束在契约与校准，没有 push、创建 PR 或合入 main。

<a id="current-checkpoint"></a>

## 9. 当前实现检查点

本地实现入口及新增独立答案在[事件手册](../docs/EVENTS.md#event-conditions)。
已同步 IR v8、输入区间接口和实际赋值集合；受影响的旧版本/原始 IR 测试协调迁移。
新检查覆盖精确等号、舍入伪等号、嵌套/空分支、交替采样复位、状态独立内部电压、
同刻反馈赋值、结构反馈拒绝、transition 联动与实际已接受帧回退。
尚未完成：OR 叶子证书/去重、原 8 条件动态回放、所有调度器故障点的系统性注入。
范围继续排除 idt reset、连续积分反馈、通用非线性 guard、多块同状态写入及普通 analog if。

本轮本地全量 **250 Python / 55 Rust** 通过（分别新增 20 / 3 项），条件数学 14 项、
既有动态数学 9 项通过。新静态回放 **22 配置、484,022 点**通过原判据，11 条支持、20 条明确拒绝。
构建使用 locked/offline，all-targets warnings-as-errors、格式与 diff 检查通过；
Clippy 未安装，未把 compiler warnings 检查冒充 Clippy。没有执行 Spectre、原矩阵瞬态或性能计时。

```sh
cargo build --locked --offline --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m unittest discover -s evas/tests -v
cargo test --locked --offline --manifest-path evas/rust_core/Cargo.toml
RUSTFLAGS='-D warnings' cargo check --locked --offline --manifest-path evas/rust_core/Cargo.toml --all-targets
cargo fmt --manifest-path evas/rust_core/Cargo.toml -- --check
python3 -B evas/validation/check_event_conditions_math.py
python3 -B evas/validation/check_dynamics_math.py
python3 -B evas/validation/check_design_math.py
PYTHONPATH=evas/src python3 evas/tests/run_static_regression.py --kernel evas/rust_core/target/debug/evas-kernel --output runs/event-conditions-080/static-replay
```

最后一项需新的输出目录。此执行的原始日志与波形仅本地保存于 `runs/event-conditions-080/`；
测试源码、独立答案及输入在仓库内。3 项新 Rust 测试检查 prepare 阶段和已接受帧：
不可判定条件、失败采样认证、成功弃步、修正未来输入、非零 transition 历史及无算子状态误差保留。
完整日程游标/消费状态的任意故障点注入仍未完成，不能用新进程重跑冒充这类证据。
