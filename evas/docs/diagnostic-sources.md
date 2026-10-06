# 诊断来源与出口登记

本页承接 [诊断合同](diagnostics.md)：下方行为表记录已实际验证的有限来源，
完整源码观察见 [机器清单](diagnostic-inventory.json)。身份由模块、函数和源码结构组成，
不依赖行号。源码登记不表示所有出口都已实际触发，也不代表外部 E3 消费适配完成。
“实际触发”指经过公开编译/执行入口得到该失败；“源码审计”只确认构造分支的条件与类别。
后者不计为实际执行覆盖。没有可靠归因的出口仍为 `unknown`。

## 输入和来源

| 来源身份 | 条件与出口 | 分类、阶段、能力 | 来源及验收 |
| --- | --- | --- | --- |
| `lowering.voltage.undeclared` | 完整电气声明环境中，电压访问引用未声明节点；`undeclared_node` | invalid_input / lowering / LANG | 原电压表达式 token；绑定实例上下文。实际 API/CLI 触发并断言原文本、行列与实例 |
| `frontend.module.duplicate` | 源库存第二份同名模块；`duplicate_module` | invalid_input / parse / LANG | 第二份模块的原声明 token。实际 API 触发，不改变旧重复模块文本 |
| `hierarchy.connections.top` | 顶层 manifest 端口键集合与声明不符；`connection_mismatch` | invalid_input / binding / LANG | 实际实例名；manifest 无 VA token，不补行列。实际 API 触发 |
| `hierarchy.connections.child` | 子实例有序端口数错误，或命名端口/电气连接不符；`connection_mismatch` | invalid_input / binding / LANG | 实际 child token 与层级实例名。实际 API 触发有序端口数错误；命名连接分支复用既有层级回归并由源码审计确认 |

`Model.declaration_token` 仅保留解析器已取得的模块 token，不进入求解 IR。
在已绑定的 `InstanceCompiler` 返回 CompileError 时，前端补缺失的实际实例名；已有实例信息优先。

lowering 的 `node_declarations` 仅描述诊断来源：只有实际完整声明环境才标 true，
递归表达式保留该标记；默认 false，不从字典是否为空或 message 推断声明有效性。
transition 输入、absdelay 设置、idt reset 等调用故意不给电压映射。已声明的 `V(u,r)`
在这些上下文中仍被原边界拒绝，保留旧文本与真实 token，code 为 compile_error，
category 为 unknown，hint 为 null。三例都经 API/CLI 实际验证；这不把上下文限制归因于
缺少节点声明，也不新增连续电压支持。普通/嵌套表达式、可读电压的 waveform 输入和贡献
目标中确实缺声明的节点，仍为 invalid_input。

## 编译资源

以下来源均保留原阈值、控制流和错误文本，code 为已有 `resource_budget`，分类为 resource，
阶段为 compile，能力为 LANG。resource_budget 沿用 v1 的编译资源阶段，覆盖词法/解析与
展开预算；更细阶段由来源身份说明，不在本批改变 schema。包装函数不按文字分类，调用来源显式传入 code。
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

## 完整源码观察与维护

[diagnostic-inventory.json](diagnostic-inventory.json) 枚举本库 Python 前端/CLI 与 Rust workspace
生产源码，包括 `ir` 子 crate；排除构建产物、测试文件与 `cfg(test)` 项。当前源码审计确认
Python 工厂为 CompileError、KernelError 及迁移编码子类；错误包装为各模块的 fail/_fail。
Rust Error 由 IR crate 的 `Error::new` 构造。当前返回 Error 的额外包装有四个：
continuous.unsupported 明确构造 unsupported_operator；event_accuracy.unresolved、
dynamic_roots.unresolved 和 transition.invalid 明确构造 event_resolution。
event_accuracy.unresolved 还被 affine_bounds、pwl、schedule、slew 导入使用。
当前这四个函数的包装调用数为 continuous 11、continuous_derivatives 2、
continuous_initialization 1、implicit_dynamics 3、nonlinear_dynamics 4、dynamic_roots 20、
event_accuracy 2、transition 13、affine_bounds 7、pwl 2、schedule 10、slew 7，共 82 个。
另有两个直接返回 Error 的具名局部闭包：continuous_derivatives 的 reject 委托
continuous.unsupported，pwl 的 invalid 构造 invalid_inputs；各调用两次。合计 86 个包装调用。
逐项源码计数与机器清单核对；
slew 在生产实现中间有 cfg(test) 构造器，不能在首个 cfg(test) 处截掉整个文件。
当前没有 Error 类型别名或其他 Error 结构体直接初始化；扫描器同时验收导入别名与限定调用。
未来引入新的类型、间接函数值或条件编译约定，需要同步扩展扫描和源码审计。

```sh
python3 -B scripts/diagnostic_inventory.py --write
python3 -B scripts/diagnostic_inventory.py --check
```

工具使用 Python AST 和 Rust token/平衡项边界，过滤注释、字符串与测试项；保留完整归一化
构造表达式，id 由路径、词法函数、表达式哈希及同表达式重复序号组成。源码改动后重新生成；
CI 检查新清单，不能只更新数字。所有条目的 evidence 都是 source_audit，执行覆盖另由本页
行为表及开发测试说明。动态 reason/code 为 null，category 为 unknown；不靠 message 或名称前缀
猜测，包装默认 code 从声明读取，显式实参优先。已有登记的 stage/capability 同步写入；
Rust 函数包装由显式返回 Error 的签名发现，模块身份按 mod 声明及 #[path] 解析，
调用按本模块、导入项/别名、限定路径与传递的 super::* 解析；lib/bin 根使用独立命名空间。
factory 字段保留解析到的路径，factory_crate 标明所属 lib/bin（IR 子 crate 带 ir/ 前缀）。
只有整个函数体是唯一直接 constructor 返回时读取字面 kind；条件/委托/动态函数返回为 null，
不从其中一个分支推断整体 reason。具名局部闭包只在完整表达式直接构造 Error 或调用已确认
工厂时登记，调用限制在声明后的词法作用域内。它不是完整 Rust 编译器，当前闭集另外通过
源码审计确认；普通同名函数/闭包、测试工厂、混合返回、导入遮蔽有维护负控。
来源位置是否可提供仍由构造表达式中的原 token/instance 决定，工具不补运行时位置。

| 源码观察 | Python | Rust | 合计 |
| --- | ---: | ---: | ---: |
| CompileError 及其子类构造 | 94 | 0 | 94 |
| KernelError / Error::new 构造 | 13 | 314 | 327 |
| fail/_fail / Rust 返回 Error 包装调用 | 172 | 86 | 258 |
| metadata 构造 | 9 | 0 | 9 |
| Python 异常类 / Rust 返回 Error 函数或闭包定义 | 3 | 6 | 9 |
| 错误处理器 | 36 | 0 | 36 |
| map_err 转换 | 0 | 31 | 31 |
| 元数据改写 | 8 | 5 | 13 |
| 具名重抛 | 3 | 0 | 3 |
| 全部观察 | 338 | 442 | 780 |

其中 372 条观察为 unknown，包括未解析动态 reason、宽泛处理器及明确保持 unknown 的
旧代码。观察有意分别记录构造、调用和转换，同一路径会出现多条；780 不是独立错误种类数，
不是失败执行次数，也不是覆盖率。词法函数身份不推导 Rust trait/impl 类型身份。
Rust map_err 包括保留/转换错误的包装；analog 的 event_accuracy→waveform_accuracy、
batch/transient 的 sample 赋值及初始化上下文 message 改写单独登记。转换不修改本批 Rust 源码。

## 本库消费者与兼容

实际文件/API/CLI 验收见 [test_diagnostic_consumers.py](../tests/test_diagnostic_consumers.py)。
compile/solve/transient 与 lint 共用 manifest/source 读取及结构校验，因此同一输入来源的
编码/I/O/结构错误保持 manifest_input/manifest_io/source_input/source_io。results 和 capture
复用同一字节读取、解码、解析边界；原文件哈希、快照和编译/求解输入不变。

命令参数失败通过共用 ArgumentParser 在 stderr 输出 input_error JSON，返回 2；帮助仍是
argparse 的帮助文本与成功退出。compile、results、identity、diagnostics 和 MCP 启动入口采用
该边界。diagnostics CLI 优先处理 CompileError/KernelError，保留实际 message/token/instance；
MCP 运行中的 JSON-RPC 方法/工具错误仍遵守既有 JSON-RPC 与 isError 协议，不当成编译异常。

results 在拥有新输出目录后的普通输入异常转为 CompileError，API diagnostic 与失败 marker、
CLI 一致；不再转成 kernel.input_error unknown。现有输出目录在取得所有权前仍抛 OSError，
CLI 转为 input_io，保留不触碰已有目录的契约。迁移结果新增可选 error 字段，同时保留旧
自由文本 diagnostic 与源哈希；sha256_file(path) 保留原有效 UTF-8 文件调用和返回哈希。
成功为 error=null，failure 不改变批次失败分母。

capture 保留 payload.error 原内核载荷，新增 error_diagnostic，status 查询（及 MCP status）
一同传递；旧会话没有附加字段时返回 null，不能把缺字段解释为成功。会话版本仍为 1，哈希
覆盖实际完整 payload，旧会话仍按原哈希校验。内核未给诊断版本的旧 kind/message 载荷按旧
兼容边界适配为 v1；明确给非 v1 版本时保留原版本/载荷，分类 unknown、capability=null，
不能用已知 kind 反向套 v1 规则。真实子进程负例保留 sample 与未知附加字段。

内核 diagnostic 的 code/stage/category/capability 由适配器登记表或 unknown 规则生成，
不能直接信任未来载荷同名值。原载荷值与规范元数据冲突时，diagnostic.raw_payload 保存
完整原载荷，包括原载荷自身的 raw_payload 字段；KernelError.detail 继续原样保留。
没有冲突时不新增此包装字段。

## 剩余范围与证据复用

#64 外部 benchmark/harness 的分类读取与评分分母验收仍待其拥有者交付，不能据本库清单
关闭总 Issue。PR87/88 是并行用户工作，本批未改其文件或接口。旧 Python API 的普通
ValueError/OSError（如 query 校验、输出目录所有权、数值请求参数校验）继续保留原异常类别；
调用者可选择现有 CLI 取得结构化边界诊断。完整源码清单不把这些异常猜成新的 CompileError
原因，也不声称所有出口已做实际执行覆盖或所有 unknown 已细分类。
lint_passed 仍只表示既有静态检查通过；支持范围与精度资格没有升级。

此修改只改变输入失败与诊断运输元数据，新增声明 token 不参与数值 IR；所有 VA 拒绝条件、
编译预算、Rust 数值源码和求解控制流均未改。沿用原基线的实际 Spectre 对比所支持的原有
数值结论，不据此声称新做 Spectre、扩大动态支持或通过新精度资格。相关本地 timer/DAE/vector
回归用于守住此边界。若后续改变数值/事件控制流，必须重新选择相关实际 Spectre 对比。
