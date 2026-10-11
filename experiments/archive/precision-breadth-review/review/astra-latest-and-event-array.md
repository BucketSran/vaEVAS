# 数值与语义增量审查

本轮限定代码审查未发现新的 P1/P2 数值、事件语义或 checker 缺陷。生产文档仍需同步，实际 Spectre 证据将在 collect 后另行复核；当前结论不代表完整数值资格或可合并。

## 固定比较与身份

- 生产修复比较 `4448253a15ea8cf566d88e62be54c3819060648a..55e5f197157bacd2b2cfd282f2547f6ea6b918ab`，独立工作区 `worktrees/precision-event-array`。
- core 比较 `4174866ebe3493e39d786fdc07aba98ca7e46827..08a90bd2e4a8395adea43fed2692d9ba92e19c23`。
- foundation 比较 `4174866ebe3493e39d786fdc07aba98ca7e46827..c986e6e34b344a3a89a852bf5993d48b4e1f4e9c`，包含 `15bba1ea29ee52470c7f9de92b3cff0ff88ce6bc`。
- 集成检查点 `cec42221e0b52e95689c8de77c61445a65bb184b`。上述受审文件与各独立提交的对应文件 diff 为空；checker 测试在此集成检查点运行。

读取项目 review/validation 规则、原 `astra-final-checker-followup.md`、`glm-core-adjudication.md`、当前规格和现有 decisions.tsv。只读 tracked 文件，报告存于 ignored runs；没有启动远端、发布或操作 PR #131。

## 生产机制

`events.rs` 的改动仅把共享自状态读取的系数准入从恰为 1 扩展至有限非零。结构依赖集仍必须只含目标自身，没有电压或算子依赖；系数消除及下溢不会消除其他状态的结构依赖。`q-q`、`0*q`、`n+0*q` 等拒绝测试保留。所有 affine 系数的非有限检查也保留。

沿 `event_circuit`、`apply`、`Bounds::new` 检查同一执行路径，三者均从固定已接受旧状态开始，并在单个块内逐句更新 local；后一个物理事件读取前一个已接受事件状态。同批次不同块实际写同一状态仍由 `check_selection_writers` 拒绝，未新增源码顺序仲裁。整数每句范围检查及失败回滚机制没有绕过。

新增回归直接核对 F07 的手算序列 `(0,1) -> (1,12) -> (11,122)`、观察网格变体、负/分数系数语句顺序，以及同刻 timer/cross 冲突。已有真实控制器回滚测试通过，覆盖未提交状态和重试；本次没有为每个新系数另做私有回滚案例。

配套交付缺口：`evas/docs/math/events.md:532` 一段仍明确写“系数恰为 1”和“非 1 系数不会获得此例外”，与新准入不符。请在生产 PR 收口时更新该段及 EVENT-ORDER 证据记录，并把实际 F07 配对的边界与一般仿射能力分开。这不是当前数值实现的反例，但不能把旧契约当成新实现说明。

## checker 判据

F14 在序列化时间盒触及零点时包围 DC 值 0 和右侧瞬态值 0.5；当时间恰超出该盒时恢复 `[0.5,0.5]`。它没有扩大 undefined 点、删除原始初始行或解除相位/输入拓扑证据义务。手写完整 PWL 轨迹将初值分别设为 0、0.5、0.25、100，全部仍为 Q1/Q2/Q3 evidence_insufficient，105 个输出观察点保留为未获资格，2 个真正导数拐点单列 undefined。异常初值并未被宣告数值合格；在缺少独立输入导数证据时也不作确定失败归因。

core 新校验拒绝未声明 counter、越界事件 index、延伸至负时间的合法窗口，以及不有限/无双侧/输出名非法的 undefined 声明。无 counter 的声明窗口不能再被误称为“实测倒序”，但仍留下缺 counter 的 unknown。跨 counter 有实际观测的顺序规则保持；cross 的 `min(ttol, expression_tolerance/abs(slope))` 合法窗口没有放宽。

负控经过实际 grader：仅原始 phase 增加一周期而正弦保持正确仍判 numerical_error；完整 transition 上/下降时间错误仍判 numerical_error；NaN、缺 start/stop、过大间隔、错误输入与 nextafter 假 undefined 都保留拒绝。F03 仅将非法端口名 logic 改为 logic_out，独立参考与输出接口同步，仍需新执行身份，不能重命名旧 raw 冒充重跑。

冻结预算/分母未改：当前 load_contract 为 44 组、71 变体；Q 与 B/100、B/10 规则沿用原合同。上述控制均为开发校准，不计入科学实测通过数。

## 实际本地检查

在 production 工作区先执行 `cargo build --locked --manifest-path evas/rust_core/Cargo.toml`，再运行：

- `PYTHONPATH=evas/src:evas/tests python3 -B -m unittest -q test_variable_arrays test_shared_counter test_event_body_loops test_event_writers test_settlement`，54 tests PASS。
- `cargo test --locked --manifest-path evas/rust_core/Cargo.toml`，234 passed，1 ignored，0 failed。忽略项是原有 ignored 项，没有改分母或移除测试。

在集成检查点运行 `PYTHONPATH=evas/src:evas/tests python3 -B -m unittest -q test_precision_breadth_core test_precision_breadth_foundation test_precision_breadth_composition test_precision_breadth_runner`，92 tests PASS。另完成上述四种 F14 初始值手写轨迹与零点时间盒的直接校准。

## 证据与审计限制

现有 decisions.tsv 的相关行能解析到固定提交、规格和此前审查材料，且明确保留 F07 原始三档拒绝及待配对状态。本轮未拿到全部历史会话和全部远端 raw，不是全夜间日志审计。生产契约更新、较晚 runner 改动和后续完整矩阵都不在当前代码审查结论内。

协调者告知 F07 的 Spectre 三档已执行并得到 first=11、last=122、y=133、count=2，但本报告此刻尚未独立读取 collected raw。该转述不能替代证据审核。完整 callback bracket 跨合法窗口边界时应保留 unknown，不得裁剪；即使离散值和有限输出误差吻合，也不能称 F07 完整认证通过。待收到实际资料后追加独立证据结论。
