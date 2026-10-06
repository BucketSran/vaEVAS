# 已审计的诊断来源切片

本表记录 #64 的有限 E1 切片，承接 [诊断合同](diagnostics.md)。身份由模块与触发条件组成，
不依赖行号。它不是所有 CompileError/KernelError 出口的完整清单，也不代表 E3 消费适配完成。
“实际触发”指经过公开编译/执行入口得到该失败；“源码审计”只确认构造分支的条件与类别。
后者不计为实际执行覆盖。没有可靠归因的出口仍为 `unknown`。

## 输入和来源

| 来源身份 | 条件与出口 | 分类、阶段、能力 | 来源及验收 |
| --- | --- | --- | --- |
| `lowering.voltage.undeclared` | 电压访问引用未声明电气节点；`undeclared_node` | invalid_input / lowering / LANG | 原电压表达式 token；绑定实例上下文。实际 API/CLI 触发并断言原文本、行列与实例 |
| `frontend.module.duplicate` | 源库存第二份同名模块；`duplicate_module` | invalid_input / parse / LANG | 第二份模块的原声明 token。实际 API 触发，不改变旧重复模块文本 |
| `hierarchy.connections.top` | 顶层 manifest 端口键集合与声明不符；`connection_mismatch` | invalid_input / binding / LANG | 实际实例名；manifest 无 VA token，不补行列。实际 API 触发 |
| `hierarchy.connections.child` | 子实例有序端口数错误，或命名端口/电气连接不符；`connection_mismatch` | invalid_input / binding / LANG | 实际 child token 与层级实例名。实际 API 触发有序端口数错误；命名连接分支复用既有层级回归并由源码审计确认 |

`Model.declaration_token` 仅保留解析器已取得的模块 token，不进入求解 IR。
在已绑定的 `InstanceCompiler` 返回 CompileError 时，前端补缺失的实际实例名；已有实例信息优先。

## 编译资源

以下来源均保留原阈值、控制流和错误文本，code 为已有 `resource_budget`，分类为 resource，
阶段为 compile，能力为 LANG。包装函数不按文字分类，调用来源显式传入 code。
原 token 提供来源；层级预算由实际 child token/实例上下文提供，顶层实例无 token 时仍不补猜。

| 来源身份 | 实际触发 fixture | 其他已审计同组分支 |
| --- | --- | --- |
| `syntax.tokens.count` | 100001 个合法单字符 token，到 source token budget 出口 | tolerant 未支持字符的同一计数分支 |
| `syntax.nesting` | 65 层括号，到 syntax nesting limit 出口 | statements 嵌套出口 |
| `preprocessor.expansion.count` | 二十层二倍宏，到 preprocessor token expansion budget 出口 | 宏展开深度、宏/参数替换调用身份深度 |
| `preprocessor.include.depth` | 65 级 include 库，到 recursive or over-budget source include 的深度分支 | include 身份深度 |
| `preprocessor.conditional.depth` | 65 个活跃 ifndef，到 conditional directive nesting budget 出口 | 无 |
| `functions.expansion.size` | 二十层二倍函数，到 function expansion exceeds expression depth/size budget | 无 |
| `functions.expansion.depth` | 64 级函数，每层含十二个加零项，到 function expansion exceeds expression depth budget | 过多非递归函数调用的 stack 深度分支 |
| `genvar.iterations.single` | 单循环 5000 次，到 nonterminating or over-budget static loop 的预算分支 | 无 |
| `genvar.iterations.total` | 65 × 65 次空循环，到 total static iteration budget | 无 |
| `genvar.statements.total` | 2050 次展开 timer 及赋值，到 elaborated statement budget | 静态嵌套与表达式/事件调用身份深度 |
| `hierarchy.instances.count` | 根实例加 4096 个 child，到 hierarchical instance count/depth budget | 无 |
| `hierarchy.instances.depth` | 66 个非递归模块组成链，到 hierarchical instance count/depth budget | 无 |
| `arrays.elements.total` | 4097 个变量数组元素，到 total array element budget | 无 |

每个 fixture 检查真实 message 含目标出口说明，避免先撞其他限制后误算覆盖。
未声明节点与宏展开预算另经真实 compile CLI，完整诊断必须与 API 一致。
具体行为验收在 [test_diagnostic_sources.py](../tests/test_diagnostic_sources.py) 的
`test_real_expansion_limits_are_resources` 和 `test_deep_and_aggregate_resource_origins`。
同组未单独执行的深度/身份分支只提供源码审计，不声称执行覆盖。
宏递归、include 环、重复 genvar 值、递归函数调用仍保留旧 unknown；这些条件不能从
混合错误文本推断为资源耗尽。宏递归/include 环/重复 genvar 值有实际负控。

## 内核 kind 的适配

本切片只改 Python 适配映射，不改变 Rust 生产构造、算法、数值阈值或 kind。
code 仍为 `kernel.<kind>`，stage 为 kernel，未有特定能力归因时 capability 为 null。
`KernelError.detail`、原 message、sample 以及未来附加字段均保留。

| 来源身份 / kind | 构造条件与分类 | 验收与限制 |
| --- | --- | --- |
| `nonlinear.newton` / `nonconvergence` | Newton 停滞、线搜索失败或迭代耗尽；numerical | 原非收敛多项式经实际 solve 到 nonconvergence，保留 sample/source 文本。没有证明候选源码错误或内核缺陷 |
| `schedule.calendar` / `event_budget` | 实际日程或重算日程超过事件预算；resource | 实际周期 timer 到日程预算出口。CROSS 日程与调度重算来源为源码审计 |
| `main.stdin` / `input_io` | Rust stdin 读入 I/O/编码失败；infrastructure | 非 UTF-8 字节经真实内核 stdin 到 input_io；经适配保留原载荷 |
| `main.sidecar` / `diagnostic_io` | 原求解成功，但 sidecar 无法新建/写出；infrastructure | 真正执行 solve，sidecar 指向已存在目录。CLI 返回 2 且不输出成功 stdout；原内核 exit 3 经既有适配保留错误 |
| `batch.spawn` / `worker_start` | OS 拒绝 spawn_scoped；infrastructure | 源码审计与载荷保真测试，未强制真实 OS 线程创建失败，不算实际出口覆盖 |

`worker_failure`、`invalid_state_space`、`state_space_limit`、`nonfinite_arithmetic`、
`event_condition`、`event_accuracy`、`event_consistency`、`event_conflict`、`state_range`、
`condition_precision`、`numerical_failure` 等尚未在本切片细分类。
它们有多种来源或尚缺明确受审合同，仍为 unknown；未来 `unsupported_*` 也不会由前缀自动分类。

## 剩余范围与证据复用

#64 仍需要所有直接出口/包装调用/错误转换的完整清单，以及实际 CLI/API/benchmark 消费适配。
本切片没有改 argparse 文本错误、运行产物/身份入口、外部 harness、benchmark 评分或协议。
lint_passed 仍只表示既有静态检查通过。diagnostic_version 仍为 1，支持范围与精度资格没有升级。

此修改只改变失败元数据，新增声明 token 不参与数值 IR；所有拒绝条件、预算、Rust 数值源码均未改。
因此不要求重跑 Spectre 来验证本切片的元数据。原基线已记录的 Spectre 对比可用于其原有数值结论，
不据此声称本批新做了 Spectre、扩大了动态支持或通过了新精度资格。若后续修改数值/事件控制流，
必须重新选择相关实际 Spectre 对比。源审与本地失败回归不替代行为对齐证据。
