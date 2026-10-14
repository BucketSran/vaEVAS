# 事件与连续历史补充切片证据

这份草稿回答本地 N02–N21 中已实现切片实际验证到哪里。
实现以 `ce677d592ebcab1b97b9146c3aa560b9810c02dd` 为开发基线，仍是 EVAS 0.17.0 / IR21，未发布。
Astra 报告覆盖各自冻结候选。N07a、N18a/b、N19 已有完整 GLM 报告；其他关键新增项仍待 GLM 复核，不能称整套候选双审完成或合并就绪。
历史 COMPARISON 分数与 #131 保持原状。各项共享或重复的测试不相加成总通过数。

合同归属见[事件手册](../../../evas/docs/math/events.md)、[连续动态](../../../evas/docs/math/continuous.md)、
[历史算子](../../../evas/docs/math/operators.md)与[编译准入](../../../evas/docs/reference/frontend-admission.md)。
此处只保存紧凑证据，不复制完整开发、设计和审查日志。

## 资料可用性与身份

当前原始材料均为 **local-only**，在日常入口 `current/runs/evas-night-20261014/` 下。
下文的 `R/` 表示该目录，不是公开下载地址，也不保证其他 checkout 存在这些文件。
这是待固定归档的 draft；发表前须由主线程补充可取回的固定历史或归档地址、文件清单及摘要。
不能用这里的路径和 hash 声称公开可复现。完整源码补丁、测试与原始失败仍留在原工作区和 runs，未复制进本目录。

[身份索引](provenance.json)记录本次摘录所依据文件的 SHA256 和配对核身份。
它是整理时的索引，不是补造运行前收据，也不是集成核已重跑全部案例的证明。

| 切片 | 实际配对 EVAS 核 SHA256 前缀 | 源码身份及已知限制 |
| --- | --- | --- |
| N05 | `171f10684951` | persistent build 与局部 diff/源摘要匹配；缺统一的运行前完整源码与构建参数 receipt，后补清单标 retrospective |
| N06 | `3ecbe9283839` | transition `16c4e0bf…`、operators `3e01d732…` 与实现审查相同；110 文件构建清单是配对后重确认 |
| N07a | `db41ce63c649` | 运行前 109 文件哈希；核含其他集成切片与 N14，不是 N07a-only 私有核 |
| N07b | `07647d98d1b7` | 运行前 107 文件哈希；三个本包生产文件与独立实现审查一致；父级含 N07a/N14 |
| N08 | `dcc40978d959` | 双后端十组固定核/IR；该批缺对应运行时完整前端与 Rust 源快照，另一颗原 11 条复验核不能替代 |
| N08b 缓存 | 无新增实际配对核 | 修复候选 `54decc0e…`；私有独立测试核 `9fafc1ed…`，不能冒充新 Spectre 配对 |
| N08c / A0 | `6261cf25a667` | 282 项构建前源身份；原批、零 transres 失败与正 transres 批次分别保留 |
| N09a | `5757c226cfe2` | 124 项构建前清单覆盖 111 个生产源；使用绑定精确传输 manifest 的配对结果 |
| N10a | 无成功配对核 | 只改前端，独立审查复用 `a753fa5d…`；原 Spectre 同源材料复用不等于 EVAS 配对成功 |
| N14 | `8cd00f2e1787` | 复用基线 Rust 核，parser `7475607f…` 与 IR 有新身份；没有冒称重新构建 Rust |

实际 Spectre 均为归档中记录的 `21.1.0.509.isr12`。核摘要和版本来自收回证据，各批证据来自本轮实际远端运行或明确标注的固定参考复用；整理索引本身不产生新运行。
各批 conservative 下实际 transient reltol 比请求严格 10 倍；EVAS 使用各自请求值。
因此这些是已记录配置下的比较，不是两个后端生效容差完全相同。

## 数值与原生观测分开计数

“原生查询点”指原 PSF 确实保存的对应时刻；没有插值或用最近点补齐。
N05/N08 审计按十进制 token 精确比对；N06/N07 相关审计采用 token 解析后的 binary64 相等，
不能升级为隐藏物理时刻的零宽证明。数值门槛、观测完整性和事件顺序资格分别报告。

| 切片 / 实际配置 | 数值或记录结果 | 原生观察与未定事项 |
| --- | --- | --- |
| N05，6 模型×2档 | 12/12 满足事前 1e-6 V 输出门槛；Spectre y 最大误差 2.2051e-12 V | 60/60 查询点，529 原生行；内部 z 未保存，输出不单独证明 cap 生效 |
| N06，原单边沿 4模型×2档 | 8/8 满足原数值预算；filter 最大误差 base 6.9105e-7、fine 6.9622e-9 V | 29/44 查询点，15 缺失；114,495 原生行不证明严格 deadline/timer 排序 |
| N06，再改目标 4模型 | 主分析器记录两 stable 控制满足预定预算；两 near 仅 characterization，严格顺序 unresolved | 四组均不完整；本索引只摘录新增 summary，没有重新独立审计该批数值 |
| N07a，2 dyadic + 2 decimal | dyadic 两组 12 点误差 0、每后端共 10 条记录一致；decimal 两组 EVAS event_resolution | dyadic 12/12 原生点；decimal Spectre ordinary/strobed 回调为 4/3，不计通过 |
| N07b，4模型×2种观测 | 初始与计数输出精确一致；history z 最大误差见下节，无事前 Q 门槛 | 41/48 查询点，7 缺失；1,414 原生行；无 Spectre 内部 callback 记录逐条对照 |
| N08，5模型×2档 | 事前 1e-6 V 门槛下 6/10 符合：base 1/5、fine 5/5，另四个 base 超限 | 52/90 查询点，38 缺失；完整查询对齐 0/10；该首版原 11 条均拒绝 |
| N08c / A0，正 transres 两组 | 全部 976 原生行满足冻结 1e-8 V；EVAS 20 标量符合 | forced 5/5、ordinary 4/5 原生点；请求 1e-24 s 被自动抬高，最后报告 1e-19 s |
| N09a，10模型×2种观测 | 全部 33,699 原生行及 960 个 EVAS 查询电压满足 1e-6 V | forced 80/80 点、10/10 完整配对；ordinary 34/80 点，缺 46 点 |
| N10a，原两条 core-boundary 复用 | 每份 10,052 原生行的瞬时代数关系残差不超过 3.34e-16 V，无新 Q 判定 | 自身父级不含 N09a，两条 EVAS 仍 jointly-affine 拒绝；不计配对成功 |
| N14，3拼写×2档 | 每后端 108 条记录，实例内顺序、时间、状态与电压符合独立答案 | 记录合同，不是连续波形 Q；final_step 改物理电压的差异保留 |

<a id="n05"></a>

## N05：隐式模型读取动态步长请求

无事件隐式 DAE 在内部接受段起点读取认证请求区间的下界，值可依赖合法节点、已有算子、时间与源。
条件仍限源仿射域；隐式路径活动请求严格为正，普通路径允许零的规则不变。
不增加条件根搜索，不保证捕捉接受点之间任意窄的激活窗口。

独立实现审查验证内部段宽、区间下界、完整坐标与滤波直接通路、raw IR 准入和同对象预算失败重试。
这些 detector 后来迁入 `implicit_bound_tests.rs`，由该 reviewer 编写测试的部分明确不是对自身代码的第二审。
保存的相关执行为 Python 39/39、Rust 264 passed/1 ignored；它们属于切片身份，不是本次整理重跑。
实际模型 `z'=1+2y, y=z-y²` 选择 y(0)=0 分支，答案 y=t、z=t+t²。
Spectre 只保存 u/y；不得把代数反算 z 或 y=t 的正确性当作内部 cap 的独立测量。

本地依据：`R/review/astra-n05-implementation/REPORT.md`、`R/review/astra-n05-evidence/REPORT.md`；
原始实际与摘要在 `R/remote/n05-n07-v1/`，其中 `N05-SUMMARY.json`。

<a id="n06"></a>

## N06：精确期限与 point 事件排序

有精确机器数和的 transition 期限保存最窄包围，上端代表同步供边沿状态、滤波和积分分段使用。
精确有理比较只放行相对 point 用户事件已证明的顺序；不同内部期限重叠、真正非点 cross、
中断后没有精确和的期限仍保守拒绝。没有改变错误候选的原子回退。

独立审查运行 15 项 Rust transition 相关测试、原新增 4 项 Python、8 个敏感再改目标配置，
随后持久测试补入 retarget 与真实非点 cross 负控。旧测试中把合法 point 顺序要求为拒绝的第一段已按新合同调整，
不能把该过时拒绝继续当作实现故障；内部期限拒绝和独立实例同刻控制须保留。
原单边沿实际批次只在第二个 timer 增计数，不能单独验证再改目标时的 origin 选择。

追加四模型中，stable 两例用约 ±4 ps 间距保持中断/结束分支，主摘要 filter 原生误差分别约
1.0184e-8、5.6302e-9 V，预定预算为 y/f 2e-6 V、z 3e-12 V·s。
near 两例间距约 1e-22 s，小于允许回调偏移。near-active 的 Spectre 波形更接近 finished 家族，
与 EVAS 名义 active 家族最大 y 差约 .5 V；这必须保留为分支观察，不能拟合波形后反证严格时序。
本段数值摘录主 summary，尚未由本次文档工作重做独立审计。

本地依据：`R/review/astra-n06-implementation/REPORT.md`、`R/review/astra-n06-evidence/REPORT.md`、
`R/review/astra-n06-retarget-plan/REPORT.md`；原批次 `R/remote/n06-history-v1/`，
追加批次 `R/remote/n08-n06-v1/N06-SUMMARY.json`。原 C08 本地执行另存 `R/n06-original-c08-v1/`，不改其历史成绩。

<a id="n07a"></a>

## N07a：固定 timer 显式零容差

固定 timer 的精确时钟 `Q(start)+k·Q(period)` 在域内须可表示为单点，普通与 strobe 均同样验收。
已经证明同刻的混合正/零容差组可共同收紧到该单点；不把相邻不同根合并，不修改纯正容差组策略。
负容差、保持状态 timer 零容差仍拒绝，缺省仍为 1 ps。这个严格时钟是 EVAS 选择，非 LRM 强制算法。

独立实现审查保存 72 项 Python、6 项 Clock Rust、1 项事务检查及 24 个探针结果。
最终负例也在固定旧前端和旧核执行，未把短小数字面量或整数溢出的错误夹具当作红证据。
实际 v2 的四份源仅将 v1 不准入的 `%0.17g` 改为 `%.17g`，并重新真实运行 Spectre；
不能冒称原 v1 同源码成功。dyadic k/8 时钟对齐，decimal `3·Q(0.1)` 非点而拒绝。

本地依据：`R/review/astra-n07a-implementation/REPORT.md`、`R/review/astra-n07a-evidence/REPORT.md`；
实际四次在 `R/remote/n07-zero-v2/`，配对 `paired-n07a-v1/` 与 `N07A-PAIRED-SUMMARY.json`。
原格式拒绝日志 `R/remote/n05-n07-v1/pair-n07a.log` 保留。

<a id="n07b"></a>

## N07b：单固定 timer 共用初始化

共享体初始化一次后才建立历史。零起点正周期 p 的未来 timer 从 p 开始，保持精确时钟序列；
单次零 timer 或 disabled 只初始化。独立 initial 与独立 timer(0) 仍分别执行。
只接受现有合法初始化、单固定 timer、无 mixed display；raw IR 生命周期 OR 明确拒绝。

独立实现审查保存 98 项相关 Python、18 个源码探针和4个 raw disabled-body 负控。
实际八组复用原相同 VA 的 Spectre 执行，EVAS 日程只有 .25/.5，原生初值及计数输出一致。
history 初值 y/h/z=1/1/0；h 全部原生行误差0，z 的 Spectre 最大误差 ordinary
1.3214191296739841e-8 V、strobed 1.3426263323346177e-8 V。EVAS六查询最大 z 误差分别0与2.220446049250313e-16 V。
没有事前 Q 门槛，因此这些误差不产生新 Q 通过成绩。

history 目录含 marked 标签，但实际固定源码没有 display/strobe。它不代表准入带贡献的初始化输出。
Spectre 未直接保存内部 n/m 或显示回调，本批计数结论依据源模型输出，不冒称内部 callback 逐条配对。
本地依据：`R/review/astra-n07b-implementation/REPORT.md`、`R/review/astra-n07b-evidence/REPORT.md`；
实际复用 `R/remote/n05-n07-v1/raw/`，配对 `pair_n07b.py` 与 `paired-n07b-v1/`。

<a id="n08"></a>

## N08：连续嵌套谓词的完整候选根

嵌套 Select 的每个完整仿射候选都贡献潜在根，包含不活动候选；子根与父根共同分段。
模式切换延续积分/滤波历史。无法严格隔离的根窗口、不同根窗口重叠、没有可表示内部探测点，
或枚举预算耗尽均拒绝。源/保持态/owner 及未选分支限制不变，不推广为原 R01 全组合支持。

独立首版审查检出非线性消费者把相邻浮点区间冻结成端点模式的反例，修复 v3 后明确拒绝。
v3 独立执行25个Python、1个共同预算Rust测试，以及分段积分/atan/滤波答案和raw IR负控。
该首版证据中的原11条完整 R01 配置在另一 integration 身份 `f79eed0d…` 上仍全部返回拒绝，保存原刺激与结果。
新增五个模型不能替代原11条，也不能改写其旧成绩。

实际十组用事前 1 µV 门槛，数值结果如下；每组都有缺失原生查询。

| 模型 | base Spectre 最大误差/V | fine Spectre 最大误差/V | 每档原生查询点 |
| --- | ---: | ---: | ---: |
| parent | 1.46488e-6（超限） | 1.64256e-8 | 4/9 |
| boolean | 1.46488e-6（超限） | 1.64256e-8 | 4/9 |
| held | 3.66910e-7 | 2.41733e-9 | 4/9 |
| nonlinear | 1.42489e-6（超限） | 1.61045e-8 | 7/9 |
| filter v2 | 1.46200e-6（超限） | 3.53570e-8 | 7/9 |

EVAS 九查询最大解析误差不超过6.675e-16 V。fine 五组符合数值门槛，不解除38个原生查询缺口。
实际尝试共12次Spectre：v1十次均完成，v2两个filter完成；合格双后端配对是v1八组加v2两组。
原v1 filter 源缺数组字面量撇号，EVAS解析拒绝而该版Spectre实际成功。
原v2 PLAN 的“双后端编译失败”文字不准确，此处记勘误，原签名文件不改写。

本地依据：`R/review/astra-n08-implementation/REPORT.md`、`R/review/astra-n08-evidence/REPORT.md`；
实际在 `R/remote/n08-n06-v1/` 与 `R/remote/n08-filter-v2/`，合并摘要 `R/remote/N08-COMBINED-SUMMARY.json`；
原11条在 `R/n08-originals-candidate-v1/`。

<a id="n08b"></a>

## N08b：只缓存完整成功的谓词根分析

同一 Roots 只复用结构相同的左右 Expression 已完成的全 PWL 扫描，不缓存模式或历史。
缓存不跨源轨迹、held 状态或新 Roots；命中仍检查准入和 owner。不同表达式不合并，8192 预算不增加。
独立审查发现首版提前写缓存会掩盖失败，修复后 6 个针对性 Rust 探针、26 项 Python 和 4 个公有入口探针通过。
64 个不同阈值仍因预算耗尽拒绝。没有新增重复项模型的实际 Spectre 对照，不把旧 N08 五模型当作这项新证据。

本地依据：`R/review/astra-n08-cache/REPORT.md`，包含失败旧版、修复身份、调用不变量与回归建议。

<a id="n08c"></a>

## N08c / A0：从原源表达式证明精确端点

只有原 PWL 源与单点 held 值能证明 discovery box 内的精确可表示根时，才把根收紧为 singleton。
不使用舍入后的仿射系数冒认精确根，generated source 不成为原源证明；根重叠、无可表示内部点仍拒绝。
独立 6 项 Rust 探针和 2 项公开 Python 回归通过，覆盖 source 映射、非点 held、域外、错误包围和相邻根。

实际 ns midpoint 模型沿用 1e-8 V、同一 VA 与五个观察时刻。原批 ordinary/forced 均数值符合、均只有 4/5 原生点。
后续 `transres=0` 被 CMI-2049 拒绝，forced 未运行。正值批次请求 `1e-24 s` 后，forced 达到 5/5、ordinary 仍为 4/5；
两组全原生数值均符合，但运行中自动抬高 transres，最后日志报告 `1e-19 s`。
这不是固定 effective transres=1e-24 的证据，也未证明唯一内部机制或普遍精度提升。

本地依据：`R/review/astra-n08c-exact/REPORT.md`、`R/review/astra-n08c-actual/REPORT.md`、
`R/review/astra-n08c-transres-positive/ACTUAL-AUDIT.md`；实际分别在 `R/remote/n08c-exact-v1/`、
`R/remote/n08c-transres-v1/`、`R/remote/n08c-transres-positive-v1/`。原根缺失与零值失败保留。

<a id="n09"></a>

## N09a：独立定时读出与连续历史分开求解

对 grounded、唯一 branch 定义，结构依赖闭包证明 transition 不反馈到连续历史后，允许独立定时读出。
检查包含所有条件臂、同 branch 贡献和 step_bound；不靠零乘或未活动臂剪除反馈。算子索引和完整输出验收保持。
独立数学探针覆盖非线性积分乘 transition、alias、交错索引、source/held 谓词；反馈、浮动 branch、读出依赖 cap 与高增益精度负例仍拒绝。

实际 10 模型的 20 组全原生最大误差约 2.0141e-8 V，满足冻结 1e-6 V。
只有 forced 10/10 完整同刻配对；ordinary 缺 46 点，不能合写 20/20。
精确 source 谓词边界 .3125 s 也按点值检查，没有窗口豁免。本批不证明任意动态系数反馈或原 R01 全组合支持。

本地依据：`R/review/astra-n09-plan/candidate-review/REPORT.md`、`R/review/astra-n09-actual/REPORT.md`；
实际为 `R/remote/n09-readout-v1/raw/`，采用 `paired-evas-transmitted/` 与 `ANALYSIS-transmitted.json`，未采用旧空分析文件。

<a id="n10"></a>

## N10a：不分配从未引用的私有节点

前端只省略完整内联 AST 中没有任何结构引用的非端口内部声明。保留子连接、显式 external_nodes、所有条件臂、
零乘、零次循环、初始化、事件、display、算子与支路端点；数组只要一位被引用就整组保留。
这些无用名字不再出现在 Program.nodes 中，也不提供伪造的零电压查询。raw IR 的无约束节点仍拒绝。

独立实现审查运行 22 个私有探针、1 个 raw IR 负例和 59 项相关回归。
后续测试合同核对保留真实 floating 节点拒绝，并用独立解析式确认原被无用 z 遮蔽的两条 Laplace 正例。
原两条 core-boundary 中 memory 只有声明，复用 Spectre 波形支持其瞬时代数关系；N10a 单独审查所用父级不含 N09a，
EVAS 仍返回 jointly-affine 拒绝。该局部证据不建立原两条完整配对或模型物理唯一性。

本地依据：`R/review/astra-n10-models/REPORT.md`、`R/review/astra-n10-implementation/REPORT.md`、
`R/review/astra-n10-test-contract/REPORT.md`、`R/review/astra-n10-laplace-test-contract/REPORT.md`。
复用实际源为 `current/runs/r01-evas-compat-20261013/spectre/<task>/core-boundary/run/work/verifier/core-boundary/`，
`<task>` 分别为 `r01-integrate-sync`、`r01-repair-sync`；输入和 PSF 身份见模型报告。

<a id="n14"></a>

## N14：模拟域 strobe 记录别名

`$strobe` 在既有模拟事件域复用 Display IR、有限格式与接受事务，不引入数字域 postponed 调度。
初始化贡献、层级、格式和 mixed 事件的既有拒绝保持；失败试算不提交输出。
本地13项相关回归由主线程执行，Astra另做8次编译负控和实际归档独立复算，没有冒称另跑13项。

mixed/all_display/all_strobe 三种拼写各两档，共6配置、每后端108条记录。
独立分析保持出现次序，仅按实例检查合同允许的独立序列，没有排序掩盖同实例源序。
实际 supported 源在 final_step 只改变不驱动物理节点的局部状态。
`n14-phase-v1` 中 final_step 改物理电压的不同结果保留，不因 alias 实现而宣布修复。

本地依据：`R/review/astra-n14-implementation/REPORT.md`；实际在 `R/remote/n14-supported-v1/`，
含 `pair.py`、`PAIRED-SUMMARY.json`、`raw/`；未准入差异在 `R/remote/n14-phase-v1/`。

<a id="n08d-research"></a>

## N08d 实现前的语义研究记录

以下仅为 Spectre 参考实验，不提升为 EVAS 支持，也不重评旧批次。
source-transition v3 保留原 VA、oracle 与 1 µV 预算，在独立源根两侧增加观察点后，6 个 forced 正例全原生数值符合、119/119 请求齐全。
单独缩小 maxstep 的控制仍失败，最大误差约 .002 V，13 个请求缺 10 个。v1 全失败与 v2 导入失败、零次仿真均保留。

生命周期批次在相同 1 µV 预算下为 6/7，15,624 原生行与 88/88 请求全部核验。
`root0_timer_disable` 实际两输出全程零，与冻结先种子后 timer 的 oracle 相差 1 V；不能改答案后写成通过。
正常与前向滤波初值均为 2，完整 VALUE 段字节相同；同刻积分与滤波历史两条符合。
这些结果不唯一确定内部初始化顺序，B1 合同及 EVAS 配对仍未完成。

本地依据：`R/review/astra-source-transition-actual/REFINEMENT-AUDIT.md`、
`R/review/astra-n08d-lifecycle-probes/ACTUAL-AUDIT.md`；实际在 `R/remote/source-transition-v3/raw/` 与
`R/remote/n08d-lifecycle-v1/raw/`。GLM 独立复核仍待完成。


<a id="n18"></a>

## N08d/N18：源目标与零时刻种子

后续候选实现了受限源条件目标，并根据实际初始化实验采用零时刻最终状态种子。
这修正了上节“先建旧种子再执行 timer”的设计假设。上节原 6/7 及反例保持不变，没有换答案重评。
零时刻 timer 把 q 从0改1时，transition 从1开始；直接滤波使用同一初值，积分保留自己的显式 IC。
初始化反馈、非点种子、新创建的未消费零事件及未证明的混合历史仍拒绝。

冻结 root-v8 的五个固定/held 零起点模型完成原样请求配对，最大原生误差6.2e-15 V，低于原1e-6 V预算。
第六个正起点控制仍不符合冻结假设：timer名义时刻.25，Spectre首个变化为.24904632218567713，
计数瞬时差1、边沿最大差约.001907 V。这不是零初始化修复已解决的范围。
动态 timer 自禁用、改起点、改周期与其他未来事件的更新另做独立日程验收，不外推这五个结果。

依据为 `R/review/astra-n18b-final-v2/REPORT.md`、`R/remote/n18-dynamic-zero-v1/`。
root-v8 核 SHA256 为 `bbcbd7138476465b89fbcab88e9cb9ef364ac4b5c84b2c374509a54969d8b153`，
746项源身份见 `R/n18-compat-work/root-v8/IDENTITY.json`。相同 EventModel 失败后重试的独立私有检查见
`R/review/astra-n18b-future-probes/local-only/PREPARE-RETRY-REPORT.md`，不冒充完整控制器验收。
原六条兼容模型以 root-v7 公有CLI重新运行，6/6通过原checker及有限Spectre输出比较，共同输入输出4/6。
它沿用原501点与5ns边沿排除窗口，因此不是全边界或Q档验收；见 `R/originals-public-v7-six/regrade-summary.json`。
其后 root-v8 重跑全部70原条件，12条完成，12/12原checker及有限Spectre输出比较通过，共同输入输出6/12。
余下12条编译失败、46条内核拒绝或超时保持原分母，见 `R/originals-public-v8/`。这也不是Q档验收。

<a id="n19"></a>

## N19：保留跨预测终点的根窗口历史

旧实现会漏掉窗口内的一小段积分，甚至返回错误的零宽包围。修复保留原根证书，
对可行流场做共同包围，再将终点交给事件状态更新。另一个独立窄脉冲反例要求两侧观察点与所有邻根隔离；
无法证明时明确拒绝。没有降低原误差门槛，也没有修订 #131。

原六例实际参考中，EVAS root-v7 五个物理模型达到原请求精度，数学答案包含于输出区间。
Spectre秒尺度两例在原1e-6 V工程门槛下完整通过，最大误差分别约1.744e-7与3.376e-7 V。
三纳秒模型已有点的误差小于6.33e-8 V，但各缺4/7原生时刻且stop漂移，原批不算完整通过。
高增益亚ULP反例在EVAS明确拒绝；Spectre参考未证明能分辨该面积，始终不评分。

后续设置控制只改变 Spectre 配置。仅缩小 transres 仍缺少原生时刻，Spectre 还会自动调整该参数。
将 maxstep 从 100 ps 改为 70 ps 后，三个纳秒模型均有 7/7 精确原生查询，并通过原 1 µV 门槛。
最大误差依次为 0.02467、0.06324、0.95386 µV，最紧的一例仍有约 46.14 nV 余量。
VA、查询、数学答案和门槛均未改变。复用原 EVAS v7 请求与结果的三组新配对也通过；
EVAS 的 max_step 未改，不声称两个后端采用相同网格。旧缺测和失败记录保留。
新证据见 `R/remote/n19-strobe-refinement-v1/PAIRED-v2.json` 与
`R/review/astra-n19-refined-pair/REPORT.md`。Astra 独立重算 9,263 条原生记录，并校准错值、近点冒充与缺点均被拒绝。
依据为 `R/review/astra-n19-root-v7/REPORT.md`、`R/review/astra-n19-paired-v7/REPORT.md`、
`R/remote/n19-root-window-v1/`、`R/remote/n19-strobe-controls-v1/RESULTS.json`。
数学与证据分析经 Astra 独立校准；后续完整 GLM 实现审查见 `R/jobs/n19-glm-review-v1/REPORT.md`。
N18a/b 的完整 GLM 审查见 `R/jobs/n18-glm-review-v1/REPORT.md`；报告发现的旧漏事件由 N21 单独处理。

<a id="n02"></a>

## N02：事件数组的顺序读写

有限整数范围转换与顺序读写已进入本地候选。独立审查发现并修复了余数范围、负除数、
普通赋值读取动态数组，以及仅用作下标的默认零状态四项问题；原失败保留。
修复后 11 个独立探针和 6,500 组整数区间包含检查通过。

七个同源实际 Spectre 模型在原生 0、0.75、1 秒得到与 EVAS 相同的 24 个输出值，
满足原 1 nV 门槛，最大差为零。实际 Spectre 为 moderate、traponly、reltol=1e-6、
vabstol=1e-9、maxstep=0.125 秒，完整身份见 `R/review/astra-n02-implementation/ACTUAL-AUDIT.md`。
这是远离 0.5 秒事件的读写结果，不是边界回调或 Q 档验收。原九个 R01 模型仍先被其他
谓词编译限制挡住。v4-178 的原 VA 现已通过编译，得到 17 个状态与 1 个事件；原 deck 仍被 pulse 源入口挡住，未取得整题运行成绩。
运行时循环与完整 GLM 复审未完成。v4 原入口复验见 `R/review/astra-v4-entry-v9/REPORT.md`。

<a id="n09b"></a>

## N09b：补齐辅助内部电压依赖

四个步长控制/数学输出模型在相同原请求下完成。EVAS 相对数学答案的最大差约 5.15e-15 V，
与实际 Spectre 最大差约 6.98e-10 V，均满足原 1e-8 V；返回区间也覆盖答案。
实际参考见 `R/remote/n09b-auxiliary-v1/`，候选审查见 `R/review/astra-n09b-implementation/REPORT.md`。
该证据使用 release 核；原 debug 超时保留。未声称所有原二十条模型恢复或证明内部接受网格。
两个新测试原本因无关语法/节点错误提前失败，修正后的合法负例另存记录。GLM 独立审查待完成。

<a id="n18c"></a>

## N18c：独立连续状态与初始边沿共存

四个固定请求共 144 个 EVAS 节点值通过原 1 µV 门槛，区间覆盖独立数学答案。
实际 Spectre 原配置为 1/4；仅增补预算推导出的两处 strobe 后，完整原判据为 4/4。
旧配置失败未重评。新配置实际原生点及回传身份已独立核实，不能从此推断原 R01 整链恢复。
见 `R/review/astra-n18c-implementation/REPORT.md`、`R/remote/n18c-independent-strobe-v2/`。
构造器必须使用最终有限单点状态新建历史，不能重新播种已经推进的历史；GLM 独立审查待完成。

<a id="n20a"></a>

## N20a：显式标准数学头文件

14 个标准数学常量的同源输出经 Spectre 实跑，224 个原生值及 56 个精确查询均满足原
1e-14 V，最大误差 5.074e-16 V。配置请求 reltol=1e-9，实际为更紧的 1e-10；
vabstol=1e-12、maxstep=0.125 秒、traponly 及输出精度均已核实。
依据为 `R/review/astra-n20a-headers/ACTUAL-AUDIT.md`。这解决 v4-299 的 M_TWO_PI 宏入口，
模型随后仍因 ANSI 端口声明不支持而拒绝；不记为 VCO 已支持。GLM 独立审查待完成。

<a id="n21"></a>

## N21：新生成当前 timer 的安全拒绝

旧日程可能把尚未执行的新当前事件直接跳过。候选要求证明本批确实消费了同一触发叶，
否则明确拒绝。15 项独立调度/事务义务覆盖 OR 叶身份、精确时钟、未来日程及失败重试。
实际两个模型可在 Spectre 执行，但 EVAS 当前仍拒绝，不能写成新增支持。
见 `R/review/astra-n21-controller-acceptance/REPORT.md`、`R/remote/held-current-boundary-v1/`。
完整同刻闭包仍待设计，GLM 独立审查待完成。

## 观测证据工具

新增 N04 工具将保存值、精确查询时刻、来源 PWL、回调和区间分开记录，不替代行为 checker。
区间必须按时间、节点和数值绑定；缺列保留在分母，非法资料不能被覆盖为有效。
独立校准及修复见 `R/review/astra-n04-helper-v3/REPORT.md`。旧 6/12 共同输入输出结果和
12/12 输出结果不变；新工具的重分析单独记录。GLM 独立审查待完成。


## 统一候选 v9 的复验

新执行核为 `998e1a9403abcee5afc6e733e4a391220f9587b36b0e92e83cabcb5a0321e173`。
固定身份见 `R/integrated-v9/IDENTITY.json`，不以此前各切片的独立核替代整合验证。

N09b 与 N18c 已在这个核上重新执行，分别以固定身份复用同源实际 Spectre 波形，均为 4/4 通过原预算。
独立重算见 `R/review/astra-integration-pairs-v9/REPORT.md`。
N18c 原 144 个评分值不变；新增 180 个普通查询证书检查与 32 个额外 strobe 值分开报告。
新版分析器补上了宽包围、错列标签与缺 strobe 的漏检，52 个故障校准均拒绝。
这些漏检没有出现在保存的真实响应中；原版分析与校准失败仍保留。

原始 70 条 benchmark 请求也按各自原 120 秒上限重新运行：12 完成、12 编译失败、46 运行拒绝或超时。
完成的 12 条通过旧输出 checker；有限 Spectre 输出对照为 12/12，共同输入输出为 6/12。
见 `R/originals-public-v9/REGRADE-EXECUTION.json` 与 `regrade-summary.json`。
这说明新增最小切片尚未打通其余原始模型，不能将切片通过数写成整题支持率。

事件早检扩展的一个候选没有采用。独立探针发现它漏查零次循环内的非法索引，
并让共享函数表达式反复展开。原失败与后续设计见 `R/review/astra-n02-event-decisions/REPORT.md`。
实现与原验收门槛保持分离，不能为放开九条编译失败而删除这些结构检查。


## 长序列与交付检查

N13 增加 256 周期的采样、边沿、积分和滤波链，以及 32 周期的疏密查询和尺度变体、直接输入复位。
独立答案用有理面积和高精度卷积，另一位审查者用斜率变化的阶跃响应重新推导；6 个测试方法通过。
独立追加的 33 个边界查询和 39 个故障校准也通过，见 `R/review/astra-n13-candidate-review/REPORT.md`。
归一化 1e-12 是这组 EVAS 开发回归的要求，没有换算成四后端 Q 档或 Spectre 通过结论。
不包含中断边沿、同 Controller 失败重试或完整输出区间证明；GLM 待审。

统一 v9 完整检查为 Rust 312 通过、1 忽略；Python 1656 项中 1655 通过，1 项缺原 Git 夹具。
补齐稀疏 checkout 遗漏的 va03 原文件后，该项复验通过。原全量 exit=1 保留，
见 `R/source-v9-full-checks/ENVIRONMENT-FOLLOWUP.json`，没有伪装成一次全绿运行。

后续 v10 只增加持久测试、标签并澄清 FlowFacts 注释，未改数值实现。Rust 315 通过、1 忽略，
受影响 Python 59 项通过。release 核与 v9 逐字节相同，33 个前端模块除 docstring 外 AST 相同，
因此可复用上述范围内的 v9 配对；见 `R/source-v10-increment-checks/REUSE-v9.json`。
最后一次 GUARDS 更正只将未登记的 AFFINE 改为已有 LIN；追溯矩阵和诊断清单已重新生成并检查。

macOS arm64 安装包从新的源码包重建，库外安装、卸载和重装检查通过，
见 `R/package-v10/result.json`。安装核为 `e913eee74dbaaeea36162e1d527de0df98e07ee98686f4682e3965f8a4fc0b9d`，
并非实际 Spectre 配对所用 v9 核；本检查不产生新的后端配对、Linux 验收或发布结论。
同一 wheel 又通过 11 项库外 CLI 检查：四个动态模型各做普通查询和 strobe，
另查非点零容差 timer 拒绝、数组与标准常量执行，以及越界索引拒绝。
详见 `R/package-features-v10/RESULT.json`；这些是安装后功能检查，不是新增 Q 档成绩。
