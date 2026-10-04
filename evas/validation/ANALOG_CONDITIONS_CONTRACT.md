# 普通 analog 条件与局部 real 契约

本文维护 IR15 的限定实现契约，说明普通 `analog` 语句中的顺序局部 `real` 赋值、
比较和 `if/else` 如何形成电压方程 RHS；不改变原 31 条件分母，也不声明完整条件语句支持。

## 行为范围

本切片只支持无事件、无 `initial_step` 的组合局部 `real`：

```verilog
real y;
analog begin
  y = 1.5 * V(vin, vref) + 0.125;
  if (y > 0.875) y = 0.875;
  if (y < -0.75) y = -0.75;
  V(vout, vref) <+ y;
end
```

局部变量按程序顺序赋值；每次赋值替换该局部名后续读取到的表达式。电压贡献仍是
关系贡献，同一支路多条 `V(...) <+ ...` 继续相加；局部赋值不会写节点，也不会覆盖贡献。

`if` 谓词只接受由输入或参考端口驱动的仿射表达式，以及既有条件赋值产生的分段仿射
局部表达式。加法与无电压依赖的常量乘法可组合；两个输入依赖表达式相乘、输入的
二次及更高次幂均拒绝，不能靠相消、空分支或不可达分支消除这个限制。这个结构检查
在 Python 编译端和 Rust 内核分别执行；两侧都检查所有条件臂。分支体目前只允许局部 `real`
赋值；不支持在普通 analog `if` 内贡献方程、调用动态算子、访问事件状态、数组、
循环或让谓词依赖输出/内部待解电压。纯函数的分支候选见本页末段；手写 IR 若让 `select` 谓词依赖未驱动节点，
内核也会拒绝。输入选择的分段常数仍按输入依赖处理，暂不允许它作为标量乘另一个
输入依赖表达式；此限制是本切片的保守边界，不是声称该表达式必然非仿射。

## 数学含义

令局部环境 `E_k(x)` 保存第 `k` 条语句后每个局部变量对应的表达式，`x` 是当前样本的
驱动电压向量。赋值

```verilog
y = f;
```

更新为 `E_{k+1}(y)=lower(f,E_k)`，其他局部变量保持不变。

条件

```verilog
if (a R b) S1 else S2
```

先在当前环境下降低谓词 `p(x)=lower(a,E_k) R lower(b,E_k)`，分别执行两条分支得到
`E_t` 与 `E_f`。对每个局部变量 `z`，合并为

```text
E_{k+1}(z) = select_R(p_left(x), p_right(x), E_t(z), E_f(z))
```

两条分支若保留同一个已有绑定，该变量直接沿用该绑定，不再增加 `select`。
这保证空条件和对其他局部变量的赋值不会使未改变的表达式指数复制。

其中 `R ∈ {<, <=, >, >=}`，等号边界按关系本身决定，不引入容差翻转。内核先认证
`p_left - p_right` 的符号，再选择分支；直接仿射谓词使用二进制浮点常量与样本值的精确
有理乘积和判符号，避免 `V(u)+1e16 > 1e16` 被左右分别四舍五入后误判。结构保留后的
`1.5 * (V(u)-V(r))` 也可以进入这条精确路径，但只有当外层标量乘法以及标量与每个
仿射系数的乘法都能证明为精确 binary64 乘积时才折入原始乘积和；否则退回外扩区间，
不能把 rounded coefficient 当成精确数学系数。更一般的已支持谓词使用外扩区间：区间
完全在零的一侧才选择，无法证明符号时以 `condition_precision` 拒绝，而不是任意选择
一侧。缺失 `else` 等价于 else 分支保持原环境；若某个局部变量在可选路径中没有定义且
之前也没有定义，前端拒绝。

D2-V1-01 的独立答案为

```text
y0 = 1.5 * (vin - vref) + 0.125
vout - vref = min(0.875, max(-0.75, y0))
```

当 `y0 == 0.875` 时第一条 `>` 条件不触发，结果仍为 `0.875`；当 `y0 == -0.75`
时第二条 `<` 条件不触发，结果仍为 `-0.75`。

## 实现入口

解析器将普通 analog body 保存为顺序语句。前端把无状态局部 `real` 与事件状态区分开：
没有事件/初始化的声明变量是组合临时量；有事件或初始化时沿用状态变量规则。

前端把普通 `if` 合并成 IR v15 的 `select` 表达式。旧 IR 1–14 须从原始 VA
重新编译；v15 保留三参数 idt 复位字段及滤波/相位算子。Rust 工作点求解器在表达式求值时
只求被选中的分支及其梯度；由于谓词被限制为驱动输入，Newton 不需要求解不连续反馈
边界。事件仿射认证、历史算子和 transient 事件方程仍明确拒绝普通 analog `select`。

无事件、无状态、无算子的瞬态入口在每个请求时刻处理输入驱动的分段仿射关系。
没有 `select` 的仿射模型也进入同一个误差认证入口；是否有空条件或是否被优化掉
不能决定模型是否接受认证。普通局部变量模型即使没有 `if` 也保留电压相关运算树，
保证局部表达式不会因加入空条件/无关赋值而改变折叠策略。没有局部变量、条件或
算子的旧纯仿射源仍沿用原前端折叠及静态矩阵路径；认证针对传输的原 IR，不能恢复
参数计算、纯常量折叠或旧前端折叠之前的实数运算信息。
`pwl.rs::value_bounds` 按原始 binary64 时间与端点计算向外舍入的插值区间：
`U(t)=a+(b-a)*(t-t0)/(t1-t0)`。谓词使用这个区间，不把 `values(t)` 的舍入结果
当作精确输入。源结点处是点区间，保留精确乘积和判定；非点区间不能证明关系真值时
返回 `condition_precision`，只访问实际可达的嵌套条件。例：端点 `(0,0),(3,1)`
在 `t=1` 的精确值是 `1/3`，大于 binary64 的 `0.3333333333333333`；舍入值虽然
等于阈值，却不足以证明 `>` 不成立。当前区间方法在此明确拒绝，尚未采用精确有理 PWL 判定。

`analog.rs` 先完整检查两臂 IR，再选择分支。选中的仿射关系复用 `EventModel` 的
方程绑定和 `settlement_bounds` 对原始 IR 的输出误差认证；输入区间经电压网络传播，
以 `vabstol + reltol*abs(v)` 检查每个节点的输出误差上界。不能认证时返回
`waveform_accuracy`，不能仅凭舍入输入下的残差为零接受输出。缓存仅保留最后一个分支的
方程及误差映射；各样本重新计算输入、分支、解和误差，不保存物理历史。

## 独立验证

`evas/tests/test_analog_conditions.py` 固定以下开发回归：

- D2-V1 风格限幅公式与上下边界；
- 顺序局部赋值不是贡献累加；
- 独立贡献换序后仍相加；
- 大数消去、相邻阈值、结构保留标量乘法和嵌套 `select` 的分支选择用 `Fraction` 独立答案检查；
- 输出反馈谓词、条件体中的动态算子调用和手写坏 `select` IR 明确拒绝；
- 非线性源谓词在编译时拒绝；手写 IR 谓词即使符号明显或位于不可达臂，也以 `unsupported_condition` 拒绝；
- 原始 PWL 与舍入阈值的反例、大增益误差放大、源结点等号、未执行的嵌套条件；
- 无条件直接贡献、局部赋值、空条件、无关赋值和冗余重赋值均检查同一个 PWL 大增益
  反例；严格容差均拒绝，放宽实际电压预算后按独立有理数答案检查可接受的误差；
- 空条件/无关局部赋值保持表达式，增加输出采样点保持原时刻的解。

这些测试是开发证据，不是新的正式验证条件，也不自动增加原矩阵通过数。
在历史候选 `3fd58da` 上，302 Python / 64 Rust 回归与 Clippy、格式检查通过；原 `v1-main`
两档专项新执行复用冻结输入及现有 checker，4,001 / 40,001 点均符合有限观测判据，
最大输出误差约 `6.66×10⁻¹⁶ V`。来源、配置、工件可用性及限制见
[历史结果](../../experiments/archive/pr14-pr15-validation/RESULTS.md#analog-conditions-review)和
[收据](../../experiments/archive/pr14-pr15-validation/results/analog-conditions-review.json)。该检查点未新跑完整矩阵或 Spectre。

后续历史候选 `9c5d6c5` 修复优化后丢失 `select` 的验收漏洞并收紧两端谓词范围，
306 Python / 64 Rust 与 Clippy、格式检查通过。原 31×2 全矩阵沿用冻结输入和判据新执行，
两档各 25/31；原达标 48 份 CSV 哈希与 PR26 收据一致，剩余 6 条明确拒绝。
详情见[验收修复结果](../../experiments/archive/pr14-pr15-validation/RESULTS.md#analog-conditions-acceptance-review)与
[新收据](https://github.com/BucketSran/vaEVAS/blob/a07f401466189324a7e6df0493c6d853f3841102/experiments/pr14-pr15-validation/results/analog-conditions-acceptance-review.json)。
该轮执行时尚未合入 main，未新执行 Spectre，正式资格仍 I。
当前联合矩阵与精度链见[最新验证](README.md#latest-evas-checkpoint)，不改写这些历史身份。

后续[缺口与对照](../../experiments/archive/pr14-pr15-validation/RESULTS.md#analog-gap-spectre-comparison)
复用该原矩阵 EVAS 执行、新跑 Spectre 31×2，后者两档各 31/31；另对六个独立有理数
边界案例执行两档对照。源结点等号双方一致；大数消去的点输入谓词体现精确判符号与
分别舍入表达式的差别；PWL 临界阈值和大增益的过严预算 EVAS 明确拒绝。
这些是开发数值诊断，不改变原矩阵或资格结论，也不证明整体精度排名。

## 剩余边界

尚未支持隐式分支反馈、输出/内部节点 predicate、普通 analog `if` 内贡献、事件与普通
条件组合、条件选择的多项式/动态算子叶子、循环、连续时间观察误差界和未见确认集。
当前另有标准常量数组、受限 `sin` 和无条件局部算子别名，范围由各算子契约定义。
这些缺口需要各自的数学契约与独立答案，不能由本切片的 `select` 表达式外推。

## 六路整合的局部算子别名

当前允许无条件局部赋值接收受限算子结果；赋值和贡献使用同一份顺序环境。
先贡献、再覆盖局部变量，不会追溯修改前一条贡献。两个算子调用赋给同一局部名仍有两个调用点，
不共享历史。算子回调读取调用处的环境；后续算子参数仍必须符合各自的直接 PWL 或状态输入契约。
局部别名里的零系数和相消表达式保留结构依赖，不能隐藏反馈条件或算子输入。

条件体中的新动态调用、带 `Select` 的历史/事件方程仍明确拒绝；单个普通条件和单个积分分别支持，
不表示二者已能联立。验证见 [test_gap_integration.py](../tests/test_gap_integration.py)。

## 纯函数的分支候选

依据 [Verilog-AMS LRM 2.4 §4.7](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
的 analog function 作用域及函数返回规则。此分支仅开放 real 返回值和 real input 参数、
顺序局部赋值、模块参数读取与受限嵌套调用。输出/inout 参数、数组、条件函数和递归
仍未开放。函数内部禁止电压访问、贡献、事件和历史算子；实参中的历史调用也明确拒绝，
避免内联复制调用点。函数可接收已经在外部求得的电压表达式。

`elaboration.py::inline_functions` 在实例绑定前以实参替换形参。局部赋值按顺序建立
表达式环境，返回函数名最后一次赋值：例如 `tmp=gain*x; f=tmp+1` 展开为 `gain*x+1`。
模块参数仍留给每个实例独立绑定。展开结果进入既有 `lowering.py` 和同一电压方程组，
`V(y)<+f(V(u))-2*V(y)` 不按语句顺序写节点，而是求 `3y=gain*u+1`。

只允许读取已赋值的局部变量，未知函数、递归和缺少返回值均给出源码诊断。
表达式深度、调用深度和实际展开大小受前端预算约束；共享实参不能逃过 JSON 树大小
计数，失败不得变成 Python 的 `RecursionError` 或无限展开。

[pure_function](cases/pure_function/dut.va)及 [test_user_functions.py](../tests/test_user_functions.py)
用手算电压、多项式 guard 的两根、局部顺序写与实例参数隔离验证。该切片不新增 IR
字段、动态状态或历史执行器，也不改变原 31 条件；该切片没有新 Spectre 运行。

## 静态 genvar 循环的分支候选

语言依据是 [Verilog-AMS LRM 2.4 §3.5](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
的 genvar 与 analog for。该分支只展开标量 genvar、整数实例常量控制的有限循环，
支持递增、递减、嵌套和零次迭代。更新仅允许写循环头的同一个 genvar；
重复值、动态电压边界、非整数/超出 32 位控制值、嵌套同名变量和预算超限明确拒绝。
总迭代数与实际叶子语句各限 4096，空的嵌套循环也不能逃过总工作预算。

`elaboration.py::unroll_loops` 在每个实例参数绑定后替换索引并输出普通语句。
贡献仍加入同一方程组，局部赋值保留展开后的顺序。对 count=3，
`sum=Σ(i+1)u=6u`，`y=sum−2y` 应解得 `y=2u`。这不是新增运行时执行器。
模块参数覆盖必须独立于实例顺序；纯函数先内联，再替换循环索引。

[static_loop](cases/static_loop/dut.va)和 [test_static_loops.py](../tests/test_static_loops.py)
验证手算求和、非收缩反馈、实例隔离、嵌套/空循环、函数组合及预算拒绝。
每个展开的历史调用在 lowering 时生成独立 OperatorRef 槽，并携带 `Origin.expansion`
中的 genvar 名称/值路径。实例、原源码位置和展开路径组成调用点身份；重复身份
仍拒绝，接收变量不参与历史所有权。IR17 的普通调用使用空路径。LRM 允许合规的 genvar
analog 循环中使用历史算子。[test_loop_histories.py](../tests/test_loop_histories.py)
检查两个不同 IC/增益的积分、嵌套的四个积分及数组接收者；改变输出网格仍保持解析答案。
通用数组、运行时循环和层次不由这一切片获得支持。该切片的支持范围如上。


<a id="variable-arrays"></a>

## 变量数组的分支候选

语言依据为 [LRM 2.4 §3.2](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)：
real/integer 变量可以有常量整数范围，范围可以递增、递减并包含负下标。
本候选先绑定实例参数，再展开 genvar 循环，最后把一维数组元素改名为独立标量。
总数组元素限 4096；声明范围和下标必须为有符号 32 位实例常量整数。
动态索引、多维、参数数组、整数组赋值和函数数组参数仍未开放。

`a[0]=u; a[1]=2*a[0]; y=a[0]+a[1]-2y` 仍求 `3y=3u`，不是顺序写电压。
事件状态 `a[0]` 与 `a[1]` 分别进入 State 表；事件中先执行 `a[0]=a[0]+1`，
后执行 `a[1]=a[0]+a[1]`，四次事件后从 `[0,1]` 得到 `[4,11]`。
每个状态需按既有契约显式初始化；没有赋值的局部元素不能借用其他元素的值。

[variable_array](cases/variable_array/dut.va) 和
[test_variable_arrays.py](../tests/test_variable_arrays.py) 检查手算求和、参数范围、
负/降序索引、实例隔离、事件顺序、越界和预算拒绝。数组在进入 Rust 前消失，
不增加 IR 或运行时数组执行器；历史仍属于算子槽。该切片无新 Spectre 运行。


<a id="hierarchy"></a>

## 静态层次的分支候选

依据 [LRM 2.4 §6.2.2–6.3](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
的模块实例、端口连接和参数覆盖规则。候选接受多模块源文件、嵌套的静态实例、
命名/位置端口与参数覆盖，以及一个声明中的多个实例。端口须完整连接到已声明的
electrical 网络；未连接端口、实例数组、generate、层次变量访问和递归模块仍未开放。

`hierarchy.py` 在创建全局电压索引前绑定实例树，参数使用与平面入口相同的
`parameters.py`。子实例身份如 `dut/a/b`，内部网络如 `dut/a:z`；
电压贡献、事件状态和算子 Origin 都使用该身份。顶层名字与生成路径碰撞时拒绝，
不能静默覆盖实例。实例总数限 4096，层次深度限 64。

层次不是依次运行多个仿真：若子块 `z=g*u`，父块 `y=z+1`，联合求 `y=g*u+1`。
两个子块输出积分 `z₁=2+∫u dt`、`z₂=4+∫3u dt`，父块求和；
当 u=t 时 `y=6+2t²`。所有历史与事件仍经过同一候选提交机制。
[hierarchy](cases/hierarchy/dut.va) 与 [test_hierarchy.py](../tests/test_hierarchy.py)
检查上述手算答案、参数传播、同刻事件、实例身份、连接错误与预算边界。
此展开不增加 IR 或第二个运行时；该切片无新 Spectre 对照。


<a id="preprocessing"></a>

## 预处理的分支候选

依据 [LRM 2.4 §10.4–10.5](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)
及它引用的 Verilog 文本宏规则。候选支持对象/函数宏、define/undef、续行、
ifdef/ifndef/elsif/else/endif 和 include。`__VAMS_ENABLE__` 始终定义且不能重定义；
undef 对它无效。`__LINE__` 和 `__FILE__` 保留调用位置；字符串仍不在电压表达式范围内。

`preprocessor.py` 在语法解析前展开 Token；不加入表达式执行器。sources 是文件库存，
include 用相对当前文件的规范化路径查找。库存中被 include 引用的文件不再次作为根
编译；其余根按给定顺序共享宏环境。只处理已提供的文件，无隐式磁盘/网络读取。
include guard 不受库存顺序影响；条件块须在各文件内配对。

`SCALE(x) = G*(x)`、G=3 应给 `y=3u+1`。复制积分宏
`TWICE(x) = idt(x,1)+idt(2x,2)` 在 u=t 时应给 `y=3+1.5t²`。
宏参数先展开，再替换；`F(F(1))` 是有限嵌套，不是递归定义。复制的每个调用
保留原调用位置和 `_macro_NAME`/Token 序号路径；与 genvar 路径组合，防止历史合并。
每个 include 边也加入 `_include`/Token 序号路径；重复或嵌套包含同一历史算子时，
保留不同的调用点身份，源文件及行列仍指向被包含文件。两个 `idt(t,1)` 的贡献
应共同给出 `y=2+t²`，不能因包含位置相同而共用历史或被当作重复 IR 拒绝。

活动 Token 总展开数限 100000，展开/包含/条件嵌套及完整身份路径限 64。
递归、缺失文件/宏、参数错配、未知指令、预算超限均给出诊断；不活动分支
不展开宏或读取 include。宏拼接、字符串化、动态 include 名称、跨文件未配对条件
及其余编译指令仍未支持。标准内建 include 仍只提供原有有限数学常量。

[preprocessor](cases/preprocessor/dut.va) 和 [test_preprocessor.py](../tests/test_preprocessor.py)
检查手算电压/积分、宏嵌套、复制历史、循环组合、条件/续行、包含位置、预算和失败。
宏与 include 的失败不能静默变成默认值。该切片无新 Spectre 对照。
