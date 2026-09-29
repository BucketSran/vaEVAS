# 事件条件赋值与采样复位：第一阶段契约

状态：**设计与独立数学校准；尚未实现，也没有 EVAS 或远程矩阵通过结论。**
基线为 `5b090571c7de7c6ec08a05c803479505c5d745ee`，专用分支
`feat/evas-event-conditions`。本阶段只新增本文件和
[check_event_conditions_math.py](check_event_conditions_math.py)，不修改共享接口。
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
2. 对所有激活 B 的谓词，在当前输入/无状态电压包围上认证真值，生成只读 path 证书；
   若任一不可判定，不执行/提交任何 body。
3. 沿选中路径构造 Phi，保持逐句赋值和中间 integer 检查；同批代入原贡献方程求 v+。
4. 独立重放原 body 和谓词证书，检查原方程、状态一致性。区间路径从原 IR 重建，
   不能直接信任数值执行器给出的线性化系数或 unchecked 路径位。
5. 用 q−、H_e 的原包围传播到 q+ 和 v+；更新 transition 目标及其区间，并检查队列次序。
   仅实际执行的赋值参与 assigned-state 集，无 else 的不写路径不能伪造新目标。
6. 所有条件通过后才整批提交时间、状态/包围、电压/电路、算子队列/历史、所有叶子游标、
   去重消费状态和事件记录。错误、丢弃或重试必须保持旧帧及记录长度不变。

本基线 `Bounds::check` 把采样 `inputs: &[f64]` 作为点量；算子手册明确不覆盖 PWL 求值误差。
谓词边界认证必须更严格。建议在共享接口交接时给该证书路径增加输入区间参数：
数值解仍用代表输入，分支及候选认证使用原 PWL 包围，避免两个证明针对不同的数学输入。
这是必要接口问题，**没有在本分支自行改签名**。若协调者保留旧条件性认证，必须同时限定
可接受谓词样本的插值为已证精确，或证明输入包围内真值不变并明确 RHS 误差的条件性范围；
不能遗漏这项义务后宣称任意等号边界已支持。

当前无算子模型仍把旧状态当点量；本次有 transition 的采样器应继续携带历史包围。
不得为了新分支返回名义值而把区间重置成点，也不改变电压 `vabstol+reltol*abs(v)`、
real 状态仅相对项、integer 精确等既有预算。源到 IR 常量舍入、名义事件定位允许偏移与
连续时间观察资格仍分别说明，不能夸大证书。

当前证书缓存键仅为 event IDs。新增条件后相同 B 在不同时间可选择不同分支，
键必须至少包括程序身份、激活 block IDs 和选中语句路径；缓存只存系数，不存本次状态/真值。
每次重试重新验证 path；绝不能用前次“复位”臂的常数映射去认证后次“采样”臂。

## 6. 最小语义 IR 与接口移交

以下是语义草图，**不是新 JSON schema 或另一个版本承诺**。idt 线程交接后以其实际头部
和协调者确定的共用 IR 为准，Python/Rust 同步完成一次迁移。

```text
EventBlock(origin, trigger, body)
trigger := existing single Cross | existing single Timer | AnyCross(nonempty Cross leaves)
body := ordered Statement list
Statement := Assign(state, existing Expression)
           | If(Compare(relation, lhs, rhs), then_body, else_body)
relation := lt | le | gt | ge
```

单触发器语义保留；AnyCross 首版不含 timer、initial_step、嵌套 AnyCross 或逗号别名。
空 body 合法，空 AnyCross 非法。赋值、比较和叶子均保留来源及可诊断身份。
比较是控制节点，不塞进可数值求值的通用 Expression，也不新建另一套算子/历史类型。
静态合法性应在 Python 和原始 IR 的 Rust 入口都执行，未选中的非法分支不能逃过验证。

内部流建议为 `leaf occurrences -> certified same-time group -> unique active blocks ->
certified selected paths -> settlement candidate`。选择结果带原 IR 路径与实际写集合，
分别供数值代入、独立区间构造、重放和 transient 的目标更新使用。
记录一条 block 执行及其 fired leaves；根包围、代表时间、方向/容差均能追溯到叶子。
事件体执行次数、叶子命中次数、状态变化次数是三个不同数，不混在一个计数里。

| 下一阶段需要协调移交的精确文件 | 必要变化及责任边界 |
| --- | --- |
| `evas/src/evas/syntax.py`、`frontend.py` | 新 AST/绑定；idt 完成固定检查点后才可写 |
| `evas/src/evas/ir.py`、`evas/rust_core/src/ir.rs` | 共用 schema、serde 和 EventRecord；版本号由协调者单独定，不并行发明版本 |
| `evas/rust_core/src/events.rs` | 全路径校验、单写者、依赖检查、选支、重放及缓存身份 |
| `evas/rust_core/src/event_accuracy.rs`、`schedule.rs` | leaf 级证书与 block 级批次；谓词仿射包围接入 |
| `evas/rust_core/src/settlement.rs`、`settlement_bounds.rs` | 选中路径的三路一致性、输入区间及历史认证接口 |
| `evas/rust_core/src/transient.rs` | 原子候选、实际赋值集合、记录/游标、同引擎回滚测试 |
| `evas/tests/test_event_conditions.py`（新） | 8 条件入口及新增语义端到端回归，正式运行仍保留原 checker |
| `evas/tests/test_contracts.py`、`test_events.py`、`test_event_accuracy.py`、`test_settlement.py`、`test_timer.py` | 协调修改旧拒绝断言/版本断言，补原始 IR 与共用路径回归；不删除仍有效的拒绝边界 |

`pwl.rs`、`operators.rs`、`affine_bounds.rs` 优先复用已有接口，是否必须改动需由输入区间
接入结果决定，不能视为本阶段写授权。assembly/linear/solver 属 PR8 线程，本方案不要求
改求解器；如新增需求必须另行移交。版本包文件及共享 README、CAPABILITIES、EVENTS 手册
更新由协调者分配；语义线程的 DYNAMICS 文件不在此清单。本阶段所有核心文件均只读。

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

## 8. 本阶段复核及停止点

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
当前交付结束在这份可 review 的契约与校准；不 push、不创建 PR、不合入 main。

接口交接待协调者确定：idt 固定头部和共用 schema；body/leaf 的最终表示；分支证书与
输入区间的接入签名；记录格式及版本文件/手册的写者。无需为上述等待伪造另一版 IR。
范围继续排除 idt reset、连续积分反馈、通用非线性 guard、多块同状态写入及普通 analog if。
