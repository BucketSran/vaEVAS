# 编译准入契约

默认 `compile_sources` 与 CLI compile/lint 检查预处理后的活跃源码。
依据 VAMS 2.4 §2.6，含小数点的实数字面量必须在两侧有数字；`.25`、`.5`、
`.875`、`1.`、`1.e2` 拒绝，`0.25`、`1.0`、`1e2`、`0.5u` 接受。
未使用的宏定义和 inactive 条件分支不触发字面量检查；实际展开的宏按调用位置诊断。
这些检查也不能被参数覆盖隐藏。

`electrical` 是受支持的 discipline 名称，使用前必须声明。
显式 `include "disciplines.vams"` 可使用 `standard_headers.py` 中的
`evas-voltage-vams-v2` 环境，定义 Voltage/V、Current/I 以及 continuous electrical。
显式 `include "constants.vams"` 提供 VAMS 2.4 Annex D.3 的十四个数学常量：
`M_E`、`M_LOG2E`、`M_LOG10E`、`M_LN2`、`M_LN10`、`M_PI`、`M_TWO_PI`、
`M_PI_2`、`M_PI_4`、`M_1_PI`、`M_2_PI`、`M_2_SQRTPI`、`M_SQRT2`、`M_SQRT1_2`。
例如，显式包含后 ``V(y) <+ `M_TWO_PI;`` 使用标准小数舍入为 binary64 的值。
`M_PI` 保留原 literal 及 binary64 值；数学常量依据标准定义，不读取商业仿真器头文件。
没有该 include 或用户 define 时，数学宏仍未定义。
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

## transition 默认边沿

PR208候选按VAMS 2.4 §10.3接受模块外的 `` `default_transition constant_expression``。
它按活跃源码顺序作用于后续调用，include共享当前值，独立源码根各自初始化，后续指令不追改已解析模块。
时间表达式须为有限正编译常量，可用宏，不能引用模块参数；整数除法与溢出沿用原常量检查。
模块内指令和未知宏仍拒绝。零值指令需要实现定义的非零默认策略，本候选尚未提供，明确拒绝。

依据§4.5.8，缺省或绑定后为零的rise/fall取当前默认。`transition(q)`的delay取0，
`transition(q,td)`保留td，显式非零rise/fall优先；仅给rise时fall沿用rise，包括实例参数覆盖后的值。
例如默认2、`transition(q,0,t,4)`在t=0时使用2和4，t=3时使用3和4。
没有该指令时，原三／四参数调用与rise到fall的缺省规则保持；缺省或零rise仍明确拒绝。

`preprocessor.py`把默认值附于活跃Token，`syntax.py`补缺少的参数，
`instance_compiler.py`在实例常量绑定后替换零边沿，继续使用原IR与内核。
[独立回归](../../tests/test_default_transition_directive.py)核对默认斜坡、include顺序、源码根和实例隔离及拒绝边界。
这是未合并候选，尚无本切片实际Spectre对齐证据；原件结果另在[统一进度表](../COMPARISON.md#progress-board)维护。

## ANSI 端口声明

模块头部可逐端口声明方向，并可附 `electrical` 和一维范围。例如：

```verilog
`include "disciplines.vams"
module m(input electrical [1:0] u, output y, inout electrical r);
  electrical y;
  analog V(y,r) <+ V(u[0],r) + 2*V(u[1],r);
endmodule
```

头部只有方向的 `y` 由正文补 discipline；已在头部写 electrical 的端口不能再在正文重声明。
同样必须显式包含或声明受支持的 electrical 环境，不默认为电气端口。
方向、节点类型与范围归一化后进入原绑定层；端口按头部顺序连接，向量按声明方向展开。
范围可用实例常量参数，覆盖和上下界一致性检查沿用原规则；相反方向的两个向量不会因此交换位。
按序、按名子实例与普通 non-ANSI 模型使用同一绑定流程。

依据为 VAMS 2.4 §6.2、§6.5.2.2 及 Spectre 21.1 手册的逐端口形式。
LRM 允许共享名字列表，但本次有限实现要求每端口显式 input/output/inout；
`input electrical a,b` 的实际 Spectre 控制也拒绝，因此本次标为不支持，不称其为非法 Verilog-A。
混用裸端口和方向、重复端口/方向/discipline、缺 discipline、初始化式、多维端口，
以及 wire/reg/wreal/signed 等本次未实现的类型形式均拒绝。
这不增加参数化模块头部或完整数字端口支持。

实现由 [syntax.py](../../src/evas/syntax.py) 的 module_ports 生成已有 Model 元数据，
[node_elaboration.py](../../src/evas/node_elaboration.py) 与 [hierarchy.py](../../src/evas/hierarchy.py)
继续负责范围、顺序和实例隔离。没有新增求解方程、历史状态或 IR 字段。
[独立回归](../../tests/test_ansi_ports.py)覆盖标量答案、向量与层次顺序、参数实例隔离、
timer/积分消费者及拒绝位置；[实际有限对照](../../../experiments/backends/support/ansi-ports/README.md)
保留正反例、精度与原请求后续阻塞，不等价于完整语言合规。

## 模型编译

`cos`、`exp`、`ln`、`sqrt` 接受受限连续表达式。它们是保留的数学函数名，
不能声明为用户函数、参数、节点或变量。负平方根、非正对数及认证域外的请求明确拒绝；
具体定义域与数值认证见[纯数学函数](../math/operators.md#elementary-functions)。
在连续数学调用点中，输入或运行时状态决定的条件分支不能屏蔽数学算子的定义域检查。例如 `if (V(u)>0) q=sqrt(V(u)); else q=0;`
在负输入下仍会拒绝，即使该时刻选择了 `else`。这类分支需要后续运行时支持。

事件体中，只有最终绑定的模块参数可以在编译时确定分支。例如 `mode=1` 时，
`if(mode==0) x=sqrt(q); else x=2;` 不要求计算永不执行的 `sqrt(q)`。
编译器先检查全部原语句的名字、类型、节点、下标、函数义务和资源预算，再裁剪未选赋值与显示。
未选分支里的控制条件仍交给原内核检查。输入、初值和运行时状态不能作为裁剪依据，
这项编译时裁剪不增加物理事件的一般非线性数学支持。

IR22 的隔离观察事件另支持执行时的 `sqrt`、`abs`、`min`、`max`、变量分母与原有四则及整数幂。
实例须通过完整 IR 的隔离判定，事件不能含 `initial_step` 或固定 start=0 timer 叶子。
真 `if` 与三元表达式只认证和求值选中臂的数学定义域，所有臂仍检查声明、类型、结构和资源预算。
例如 `if(n>0) mean=sum/n; else mean=0;` 在可证明 n=0 时不求未选的除法。
这是事件顺序求值，不是连续历史算子；其他函数和非隔离数学仍明确拒绝。
已有可求值的仿射表达式及常量数学保持。完整行为、区间规则与边界见[事件数学](../math/events.md#event-math)。

模型按以下绑定规则生成 IR23。支持总览见[四后端支持范围](../COMPARISON.md)；本节定义具体编译约束。

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
- 已有 cross/timer 写者的标量 `integer`、`real` 可在声明中给有限实例常量初值。
  先完整验证声明种子，再执行原 `initial_step` 覆盖；声明本身不能制造事件状态角色。
  只读设置、ordinary 局部量、数组和输入采样不纳入，类型及常量降低限制见
  [声明初值合同](../math/events.md#declaration-initializers)。
- `initial_step or initial_step("dc")` 等只含初始化叶、且至少含一个无分析限定叶的 OR，
  归并为一次初始化体。重复叶不重复执行，也不生成零时刻 timer。
  纯初始化中的 real/integer 还接受[实际 driven 输入比较](../math/events.md#input-initialization)，
  初始化语句按源码顺序执行，后续语句读取先前写入；没有显式初值的持久状态从零开始。
  受限条件、逻辑与三元表达式可以组合已接受的初值。
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
  未提供时采用版本化的有限 `evas-voltage-vams-v2` 环境，数学常量范围见本页的十四个标准定义。
  `electrical` 使用前必须有支持的 discipline/nature 定义；缺失定义与不兼容头文件拒绝编译。
  实数字面量的小数点两侧必须有数字，例如 `0.5`、`1.0`；`.5`、`1.` 均拒绝。
  具体范围及迁移见本页的编译准入规则。
  语法位置、包含路径及宏展开路径会进入 Origin；支持边界见[预处理契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md#preprocessing)。
- `parameter real` 默认值、实例覆盖以及参数依赖，有限实数与 SI 后缀。
- 一个 `analog begin ... end`，含 `V(p)` / `V(p,n)` 贡献及受限事件块。条件贡献要求每条电压支路在所有路径都持续存在；
  可能断开的支路仍拒绝，见[普通条件契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md)。
- 接受无状态电压表达式中的 `< <= > >= == != && || ! ?:`，比较返回 0/1，有限非零值为真。
  所有分支先检查支持范围，数值认证只访问选中路径。谓词限外部输入仿射电压，分支限分段仿射；
  输出反馈与新历史调用仍拒绝；持久状态谓词及连续选择的范围见[事件条件](../math/events.md#event-conditions)与[连续选择](../math/continuous.md#selected-flow)。见[普通条件契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md)。
- 在连续表达式与原有物理事件路径中，`abs(x)`、`min(a,b)`、`max(a,b)` 降低为同一受限比较选择，数值与结构认证沿用所在上下文的谓词规则。
  隔离观察事件将这些调用降低为纯数学 `event_math`，按函数上下界认证，不要求内部选择符号可判定。
  这不新增任意内部电压反馈或历史谓词支持。
- 标量 `case` 使用精确相等和源码首个匹配分支，最多 16 个非 default 标签，至多一个 default。
  互异数值字面量标签采用平衡比较树；参数标签或重叠标签保留首匹配顺序，仍检查表达式展开预算。
  独立回归见 [case 选择](../../tests/test_case_statements.py)。
- 普通 analog 体接受 [`$bound_step(expr)`](../math/events.md#bound-step)，按顺序局部环境记录请求。
  初始化体、事件体及新历史调用仍拒绝；具体运行路径和动态值限制见链接契约。
- 表达式支持括号、单目正负、加减、乘法和除法。变量分母的连续认证见[有理连续流](../math/continuous.md#selected-flow)。
- 普通局部 `integer` 赋值要求所有路径可证明为 signed 32-bit 整数。整数 `/` 向零截断，
  `%` 满足 `a=(a/b)*b+a%b`；分母须为非零整数常量，有限值域最多展开 256 个商区间。
  无法界定的递归状态值域不能用于上述商区间展开；溢出和隐含 real 到 integer 转换拒绝。
  每个整型中间算术须单独证明 signed 32-bit 范围。未知状态值域时，只有赋值根表达式可交内核检查最终值，
  因此 `n=n+1` 可保留，但 `(n+1)-1`、`(n+1)>0` 的隐藏中间值无法证明时拒绝。
  整型贡献 `n+m+k` 也可能因中间范围拒绝；显式 `1.0*n` 提升为 real 后沿用实数规则。
  `n/2.0` 使用实数除法；
  返回 real 的函数即使返回 `7`，`f(0)/2` 也为 3.5。
- 本分支接受有限整数值域中的 `& | ^ ~ << >>`，适用于整型参数默认值、初始化、事件赋值和普通 analog 表达式。
  具体32位语义、值域证明和拒绝范围见[有限整数位运算](../math/events.md#integer-bitops)。
  该切片不增加IR指令，仍使用IR24的常量和比较选择。
- 本分支的三参数`idtmod(expr,ic,modulus)`将offset缺省为0，
  两参数`slew(expr,rise)`将fall缺省为`-rise`。显式参数优先，设置仍须是满足定义域的有限实例常数，
  其余输入和组合限制见[算子合同](../math/operators.md)。
- 事件中的 `$display` 与受限被动初始化、`final_step` 输出见[记录契约](../math/events.md#display-records)。
  实际选中的显示参数也受同刻跨块读写限制；未选分支不产生显示记录。
  `$abstime` 为内核驱动的合成时间节点，不再创建积分历史；调用者不能覆盖它。
- `pow(base, exponent)` 的指数须在实例绑定后为 **1–32 的整数常数**，支持负数、零和正数底数；
  该界限是本内核的实现范围，不声称覆盖完整 `pow`。另接受常数指数 `0.5`，编译为 `sqrt`。其他分数、变量、零和负指数仍拒绝。
  数学函数的语言来源见 [LRM 2.4 数学函数表](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)。
- manifest 指定顶层实例和端口到全局网络的映射；可展开模块内层次实例。
  命名/位置端口及参数覆盖进入同一关系 IR；内部节点与动态身份按完整实例路径隔离。
- 全局 `0` 为固定地；其他驱动节点由调用者显式指定。每个样本提供完整驱动值。
- 只声明、从未引用的私有 electrical 节点不进入 `Program.nodes` 与电压未知量。
  例如 `electrical dead;` 不参与任何表达式或子实例连接时，`V(y)<+2*V(u);` 不因它成为奇异系统。
  编译器先验证所有声明，再裁剪私有节点；端口、地、子实例连接及任意结构引用都保留。
  `0*V(dead)`、未选中分支和零次静态循环中的引用也保留；向量任一位有引用时保留整个向量。
  引用而未约束的节点仍会导致奇异系统，不赋予隐式地电压。
- 支持 real 输入的纯 `analog function`：局部顺序赋值、模块参数和受限嵌套调用。
  接受 `< <= > >=` 谓词的有限 if/else 分支，保留条件进入时的局部值及所有支路结构校验。
  函数在绑定前展开为同一关系 IR；不含电压访问、历史调用或递归。范围与独立答案见
  [函数展开契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md#纯函数的分支候选)。

同时允许实例常量控制的 `genvar for`，在编译时展开顺序赋值、累加贡献和 `cross/timer` 事件（含 OR）。
事件参数与体内表达式代入各层循环下标，再进入既有事件内核；不同展开事件保留独立来源，
同刻冲突写入仍拒绝。监测事件体内支持实例常量控制的静态 `genvar for`，
保持顺序赋值与实例隔离；条件赋值可用。事件体贡献、历史调用和嵌套事件仍拒绝；
运行期循环仅开放下述隔离观察路径。空循环不隐藏非法事件体。循环展开前还检查原树中的电气节点声明，
因此零次循环里的 `V(missing,r)` 也会编译失败。名称检查不授予新的动态下标或物理循环能力。
纯初始化体内的静态 genvar 赋值循环遵循默认零与源码顺序覆盖规则；
初始化/cross 共用循环体仍限实例常量赋值。原切片的唯一初始化限制和固定成绩见
[初始化循环旧合同](../../validation/INITIAL_STATIC_LOOP_CONTRACT.md)。模拟条件下的事件及
循环包围 `initial_step` 事件仍未支持。数学与 ZOOM 对照见[静态循环事件](../math/events.md#static-loop-events)。
IR21 引入了声明为标量 `integer` 的固定边界 `for`，初始化、终止边界和步长均须为实例常量整数。
编译展开仍保留控制变量每轮的赋值、退出值及零次循环的初始值。例如
`for(i=0;i<3;i=i+1)` 退出后 i=3，`for(i=2;i<2;i=i+1)` 不执行循环体但 i=2。
循环体不得写自己的控制变量，运行期状态边界仍拒绝。
独立回归见 [整数循环](../../tests/test_integer_loops.py)。
静态代入保留scalar integer和genvar下标的源integer类型，余数等后续表达式继续按源类型检查，
不按常量数值推断real为integer。独立正反控及实际内核顺序见
[静态循环类型回归](../../tests/test_static_loop_integer_type.py)。
总迭代与展开语句各限 4096，事件及其体内叶子分别计数；每个展开的历史调用分别占用一个算子槽。
也支持一维 real/integer 变量数组：实例常量范围和静态下标，总元素数限 4096，
数组元素在绑定后展开为独立标量。事件体还接受可证明范围内的 integer 动态下标。
例如 b 的全部写入可证明为 0 或 1 时，`a[b]` 对 `a[0:1]` 可编译；仅初值在范围内不够。
下标按声明类型检查，不把值恰为整数的 real 当作 integer。读写保留语句顺序与实例隔离，
动态写入最多展开 4096 个目标叶，整数除余最多 256 个商区间，赋值选择树最多 4096 项。
普通 analog 体的动态下标、多维与参数数组仍缺。零次循环和未选分支不隐藏非法下标或整型中间溢出。
独立回归见[事件数组](../../tests/test_r01_event_arrays.py)、
[参数裁剪与原树审计](../../tests/test_event_parameter_specialization.py)。
范围与独立答案见[循环展开契约](../../validation/ANALOG_CONDITIONS_CONTRACT.md#静态-genvar-循环的分支候选)。

动态算子的参数与组合契约见[算子手册](../math/operators.md)和[事件手册](../math/events.md)。
实现拒绝不等于语言标准禁止。
仍拒绝超出范围的循环、generate/实例数组、通用数组、命名支路、电流贡献、宏拼接/字符串化及其他编译指令等。
不同本地贡献支路因端口连接成为同一节点对的情况也明确拒绝，等待独立契约验证。

## 标准头与私有节点的实际有限对照

十四个常量复用同源实际 Spectre 记录；未引用节点的四个控制保留基线拒绝、候选结果及实际参考。两个动态控制的原 exact query 配对仍缺证，v1 product 超预算仍保留。另立的有界近点对照满足原预算，只认证实际样本与原 query 解析值的有限比较，不能认证缺失的 Spectre(q)，也不授予 Q 或完整原任务资格。输入、设置、独立解析界与可复核小证据见[前端有限对照](../../../experiments/backends/support/frontend-retained/README.md)。

<a id="runtime-event-loops"></a>

### 有界运行期事件循环

IR23 允许独立测量实例在普通 timer/cross 回调及正常 final_step 中执行有界 integer 循环，
并按当前下标读写声明数组。实例必须满足[隔离观察者条件](../math/events.md#passive-observer)。
例如 n=3 时，for(i=0;i<n;i=i+1) 按顺序执行三次，退出后 i=3；循环体不反复展开进 IR。
这不开放物理反馈、初始化或历史算子内的运行期循环。

每次条件、数组下标和赋值都读取本次候选已有的顺序写入。循环控制变量是标量 integer，
步长为方向一致的非零整数常量，循环体不能再写控制变量。
一个事件中的全部循环共用 4096 次循环体执行预算；仍需继续而预算耗尽时明确失败。
每个源整数算术中间节点检查 signed32 范围；抵消后的结果合法不能隐藏中间溢出。
整数除法、余数向零截断：-5/2=-2，-5%2=-1。下标在每次读写时检查原声明边界，不夹边界或跳过写入。

一次事件的数组、标量和输出记录共同提交。下标、定义域或循环预算失败时整批回退，
不能发布部分迭代。原始未选分支仍检查名称、类型、来源及资源，运行时只求选中值。
线上的 loop、checked_integer、checked_index、array_read 和 array_write 字段及 raw IR 防御
见[固定接口合同](../../validation/event_runtime/IR23-CONTRACT.md)。
[三个实际 Spectre 控制](../../../experiments/backends/support/event-runtime-control/README.md)
验证顺序数组、嵌套循环与整数商余；它们不代表原 CDS 整题已通过。
