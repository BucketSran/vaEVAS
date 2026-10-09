# 编译准入契约

默认 `compile_sources` 与 CLI compile/lint 检查预处理后的活跃源码。
依据 VAMS 2.4 §2.6，含小数点的实数字面量必须在两侧有数字；`.25`、`.5`、
`.875`、`1.`、`1.e2` 拒绝，`0.25`、`1.0`、`1e2`、`0.5u` 接受。
未使用的宏定义和 inactive 条件分支不触发字面量检查；实际展开的宏按调用位置诊断。
这些检查也不能被参数覆盖隐藏。

`electrical` 是受支持的 discipline 名称，使用前必须声明。
显式 `include "disciplines.vams"` 可使用 `standard_headers.py` 中的
`evas-voltage-vams-v1` 环境，定义 Voltage/V、Current/I 以及 continuous electrical。
显式 `include "constants.vams"` 提供有限数学宏 `M_PI`。
没有该 include 或用户 define 的 `M_PI` 不再隐式预定义。
调用者提供的同路径文件总是优先，空头文件不等价于标准定义。
不搜索机器文件系统，不隐式为没有 include 的模型添加 discipline。

也可在源文件或自定义 include 中声明同样的 nature/discipline。
当前接受 `nature Voltage` 的 `units="V"; access=V;`，`nature Current` 的
`units="A"; access=I;`，可选有限正 `abstol`，以及
`discipline electrical; potential Voltage; flow Current; domain continuous; enddiscipline`。
重复定义、不兼容属性和更广 nature/discipline 语义明确拒绝。
声明随活跃 include 展开按顺序生效，头文件不会同时作为独立编译根。
每个独立源码根是一个编译单元，宏、include guard 和 nature/discipline 声明不会
跨根传播；同一根的 include 图内共享这些环境。两个独立根都使用 electrical 时，
各自必须通过自己的源码或 include 声明它。编译后模块汇入同一实例绑定库存。
该规则依据实际 Spectre 独立 ahdl_include 对照：A 声明 electrical、B 未声明时，
两种 include 顺序都拒绝 B；A/B 各显式 include 的正控接受。
Voltage/Current 的声明承认电压域所需类型环境，不增加电流贡献的执行支持；
nature 的 abstol 也不改变 manifest 的求解容差。

旧测试夹具的简化 VA 字符串已显式补 include 并改用有效字面量。
冻结 `evas/validation/`、实验源、结果、收据和哈希不改写；旧归档需其原提交前端复现。
其中 event_relocalization、projected_history、pure_function 的开发回归使用
[显式 successor](../../tests/fixtures/README.md)，仅修正头文件与数字拼写。
公开准入测试同时确认冻结原版本拒绝和 successor 接受；这不把原验证收据重标为通过。
当前前端拒绝非法归档源码是预期结果，不证明历史波形的数值正确性。

实现入口是 `frontend.py`、`preprocessor.py`、`syntax.py` 与
`standard_headers.py`；独立公开编译回归在 `tests/test_compile_admission.py`。
该有限准入修复不等价于完整 Spectre/VAMS 语法兼容性认证。

## 模型编译

模型按以下绑定规则生成 IR18。支持总览见[四后端支持范围](../COMPARISON.md)；本节定义具体编译约束。

- `parameter integer` 首批接受精确的有符号 32 位值；非整数实数的隐式转换仍明确拒绝。
  涉及 integer 参数的整数除法和溢出表达式也拒绝，避免把整数语义静默换成实数运算；
  新增的整数默认值/子实例覆盖、范围约束及电气向量下标也检查只含字面量的整数运算。
  如需实数除法，显式写 `N/2.0`。已有 real 参数表达式的行为保持不变。
  `from` 的多个区间取并集，随后扣除 `exclude` 的区间或单值；支持开闭端点、
  无穷端点及其他参数构成的边界。检查每个实例最终生效的值，覆盖值可以替换越界默认值，
  但不能掩盖非法的约束表达式。
- 一维 electrical/端口向量在实例参数绑定后按声明方向展开。Python/manifest 使用
  `{"u[0]":"a", "u[1]":"b"}` 的显式位连接；模块内部的整向量连接按各自声明顺序配对。
  `V(bus[index])` 接受实例常量或展开后的 genvar 下标。每个节点与贡献保留独立身份；
  electrical 与方向声明必须有相同范围。含向量模块展开后的节点上限为 4096，动态位选、切片、拼接仍拒绝。
- `initial_step or initial_step("dc")` 等只含初始化叶、且至少含一个无分析限定叶的 OR，
  归并为一次初始化体。重复叶不重复执行，也不生成零时刻 timer。
  纯初始化中的 real 还接受[实际 driven 输入比较](../math/events.md#input-initialization)，
  每个状态仍须初始化一次；常量初值保持原规则。
  另支持一个无分析限定 `initial_step` 与 cross 叶子的共享常量赋值体：初始化安装一次，
  后续 cross 触发时执行同一体。赋值须无条件，所有状态合计初始化须唯一、完整且为实例常量。
  混合体中的 timer、多个或分析限定初始化叶，以及电压/状态/历史相关初值仍拒绝。
  纯初始化 OR 保持已有规则；详见[初始化/cross 契约](../math/events.md#initial-cross)。

依据是 [Verilog-AMS 2.4 LRM](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
的参数范围、向量连接和全局事件规则（§3.4、§5.10.2、§6）。整数隐式转换与分析生命周期
是本子集的限制，不是语言标准禁止。独立回归见
[参数约束](../../tests/test_parameter_constraints.py)、[向量端口](../../tests/test_vector_ports.py)、
[初始化事件](../../tests/test_initial_events.py)。参数绑定、节点展开和初始化降低分别位于
`parameters.py`、`node_elaboration.py` 和 `instance_compiler.py`。

- 允许一个源文件多个 module；端口需显式方向与 electrical 声明，内部节点需 electrical 声明。
- 预处理器支持对象/函数宏、续行、define/undef、条件编译和 include guard。
  include 只读取调用者在 sources/manifest models 中提供的文件，不搜索外部目录。
  显式包含标准 `constants.vams` / `disciplines.vams` 时，优先使用调用者提供的同路径头；
  未提供时采用版本化的有限 `evas-voltage-vams-v1` 环境，数学常量仅保留 `M_PI`。
  `electrical` 使用前必须有支持的 discipline/nature 定义；缺失定义与不兼容头文件拒绝编译。
  实数字面量的小数点两侧必须有数字，例如 `0.5`、`1.0`；`.5`、`1.` 均拒绝。
  具体范围及迁移见本页的编译准入规则。
  语法位置、包含路径及宏展开路径会进入 Origin；支持边界见[预处理契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md#preprocessing)。
- `parameter real` 默认值、实例覆盖以及参数依赖，有限实数与 SI 后缀。
- 一个 `analog begin ... end`，含无条件 `V(p)` / `V(p,n)` 贡献，以及受限事件块。
- 接受无状态电压表达式中的 `< <= > >= && || ! ?:`，比较返回 0/1，有限非零值为真。
  所有分支先检查支持范围，数值认证只访问选中路径。谓词限外部输入仿射电压，分支限分段仿射；
  历史、事件状态、输出反馈谓词与非线性结构仍拒绝。见[普通条件契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md)。
- 表达式支持括号、单目正负、加减、乘法及非零常数分母。
- `pow(base, exponent)` 的指数须在实例绑定后为 **1–32 的整数常数**，支持负数、零和正数底数；
  该界限是本内核的实现范围，不声称覆盖完整 `pow`。变量、分数、零和负指数仍拒绝。
  数学函数的语言来源见 [LRM 2.4 数学函数表](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)。
- manifest 指定顶层实例和端口到全局网络的映射；可展开模块内层次实例。
  命名/位置端口及参数覆盖进入同一关系 IR；内部节点与动态身份按完整实例路径隔离。
- 全局 `0` 为固定地；其他驱动节点由调用者显式指定。每个样本提供完整驱动值。
- 支持 real 输入的纯 `analog function`：局部顺序赋值、模块参数和受限嵌套调用。
  接受 `< <= > >=` 谓词的有限 if/else 分支，保留条件进入时的局部值及所有支路结构校验。
  函数在绑定前展开为同一关系 IR；不含电压访问、历史调用或递归。范围与独立答案见
  [函数展开契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md#纯函数的分支候选)。

同时允许实例常量控制的 `genvar for`，在编译时展开顺序赋值、累加贡献和 `cross/timer` 事件（含 OR）。
事件参数与体内表达式代入各层循环下标，再进入既有事件内核；不同展开事件保留独立来源，
同刻冲突写入仍拒绝。监测事件体内支持实例常量控制的静态 `genvar for`，
保持顺序赋值与实例隔离；条件赋值可用。事件体贡献、历史调用、嵌套事件和运行时循环
仍拒绝，空循环不隐藏非法事件体。允许纯初始化体或初始化/cross 共用体内
的静态 genvar 赋值循环，初值仍须是实例常量并唯一初始化每个持久状态，见
[初始化循环契约](../../validation/INITIAL_STATIC_LOOP_CONTRACT.md)。模拟条件下的事件及
循环包围 `initial_step` 事件仍未支持。数学与 ZOOM 对照见[静态循环事件](../math/events.md#static-loop-events)。
总迭代与展开语句各限 4096，事件及其体内叶子分别计数；每个展开的历史调用分别占用一个算子槽。
也支持一维 real/integer 变量数组：实例常量范围和静态下标，总元素数限 4096，
数组元素在绑定后展开为独立标量。动态下标、多维及参数数组仍缺。
范围与独立答案见[循环展开契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md#静态-genvar-循环的分支候选)。

动态算子的参数与组合契约见[算子手册](../math/operators.md)和[事件手册](../math/events.md)。
实现拒绝不等于语言标准禁止。
仍拒绝超出范围的循环、generate/实例数组、通用数组、命名支路、电流贡献、宏拼接/字符串化及其他编译指令等。
不同本地贡献支路因端口连接成为同一节点对的情况也明确拒绝，等待独立契约验证。
