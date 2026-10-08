# 初始化体内的静态 genvar 循环

本开发切片接受 `@(initial_step) for(...) ...`，也接受一个无分析限定
`initial_step` 与 cross OR 共用体内的同一静态循环。它复用已有 genvar
展开与常量初始化，不新增运行时循环、IR 字段或 Rust 状态生命周期。
[原始最小输入](cases/initial_static_loop/original-minimal.va)和
[reviewed main 上的公开失败](cases/initial_static_loop/original-failure.json)保留原身份。
实际配对探针是另外冻结的明确条件，不覆盖原输入的默认 cross 设置。

循环控制限已声明、未被外层遮蔽的 genvar 与 signed 32-bit 实例常量；
支持递增、递减、嵌套和零次迭代。体内只允许无条件标量/静态数组元素赋值，
初值限可降为无节点标量的实例常量算术表达式，可引用参数与当前 genvar；
不开放循环内的比较/三元初值。不得依赖输入、状态或历史。
普通初始化体已有的受限输入比较初值规则保持原样，不因循环获得扩展。
条件初始化、动态索引、一般运行时循环、循环包围 initial_step 事件和嵌套事件仍拒绝。

`syntax.py::monitored_event` 保存初始化树并检查体形状；参数绑定后，
`elaboration.py::elaborate_loops` 用同一展开过程处理 initial 和 analog 树。
两者共享总迭代与叶子语句各 4096 的预算。mixed body 同时作为初始化赋值
和事件赋值保留，所以两种展开用途均计入语句预算。
展开前检查初始化循环的原树，零次循环不能隐藏动态初值/控制、历史调用、
未声明目标、数组整赋值或非法下标；空循环下标也须在其入口常量环境中合法。
随后节点及变量数组沿既有路径标量化。
`instance_compiler.py::initialize_states` 继续保证每个持久状态唯一、完整初始化。
重复写同一元素仍拒绝，未写局部 real 的已有边界不变。

对 `q[i]=SEED+i`，第 i 个初态是 `SEED+i`；cross 后该共享体将每个元素
恢复到相同值。初始化安装一次且不产生事件记录；只有 cross 叶子进入运行时。
普通事件体原有顺序赋值与 OR 块去重仍适用。纯初始化循环后，
`q[i]=10*q[i]+i+1` 对 `[0,1]` 一次更新得到 `[1,12]`，输出和为 13；
误执行两次会得到和 133，因此开发测试不只用幂等的恢复赋值检查执行次数。

[公开回归](../tests/test_initial_static_loops.py)检查这些手算答案、原最小输入、
两个不同参数/数组长度实例的交换与重复运行、稀疏/稠密查询相同结果、
纯初始化的递减/嵌套/空循环、重复/缺失初始化与非法输入、共享预算。
未修改事件定位、提交/回退、历史或算子方法；相关既有组合回归仍须通过。

## 冻结实际配对条件

[VA](cases/initial_static_loop/dut.va)、[deck](cases/initial_static_loop/table.scs)、
[手写 manifest](cases/initial_static_loop/manifest.json)与
[哈希](cases/initial_static_loop/SHA256SUMS)固定为一项 Spectre 配置、两个实例。
输入 `u=t`，timer 名义时刻 0.25，向上 cross 名义时刻 0.5。
第一实例 N=2、SEED=0、POLLUTE=40，和分别为 1、81、1；
第二实例 N=3、SEED=10、POLLUTE=70，和分别为 33、213、33。
qzero/qone/qlast 是独立保存的元素观察量，避免只检查总和而漏掉元素错误。

电压预算冻结为 `1e-7 + 1e-5*|独立期望|`；timer 窗口
`[0.25,0.250000001]`，cross 窗口 `[0.499999999,0.500000001]`。
每个后端分别对手算三阶段检查，同一实例的观察量必须共享阶段。
不跨跳变插值；原生阶段差、精确要求点/初态/stop 缺口分别保留。
[实际有限配对](../../experiments/backends/initial-static-loop/README.md)记录一个配置、两个实例、原 stop=1 内 80 行/720 配对电压在冻结预算内通过；显式延长 stop 一 ULP 的补充请求配对全部 81 行/729 值。原生严格覆盖 5/9 与 stop 缺口仍为 I。
单侧 timer 窗口是更严格的 Spectre 开发 probe 条件，不代表所有 LRM 允许时间；见该入口审查说明。
本切片不完成 #65 总项、原 SAR 动态索引或一般初始化/事件语义。

## Review boundary clarification

A legal zero-trip mixed body expands to no assignments in both initial and event
trees. It initializes no element. Its cross leaf remains an empty-body event,
just as `@(initial_step or cross(...)) begin end`. A declared real that has no
remaining writer stays local; reading it before assignment still rejects.
This is the existing writer classification, not a new persistent state.
`test_legal_zero_trip_mixed_loop_matches_empty_or_body` checks that equivalence.

Entry-environment index validation protects zero-trip bodies. Each nonempty
iteration then passes `array_elaboration.py::scalarize_arrays` through
`element()`, which checks the expanded index against the bound array range.
`test_initial_loop_index_diagnostic_and_later_iteration_bounds` checks a later
iteration out of bounds through public compilation. Public frontend hierarchy
calls `hierarchy.py::bind_hierarchy` and `scalarize_nodes` before InstanceCompiler's
array scalarization and state initialization.
