# 旧 EVAS → 新 vaEVAS：源码迁移候选审查

审查日期：2026-09-29。范围：只读源码审查、独立本地探针和迁移设计；没有实施迁移。

**建议先提取独立回归素材，再实现受限 `idt` → 修正后的 `idtmod` → 一阶 `laplace_nd`。旧版最有价值的是语法案例、局部变换和简单数值更新；不宜复制其模型执行器、算子状态布局或事件提交路径。** 本次发现的缺陷包括同一赋值目标的积分历史串用、缺省模数语义错误、额外极点丢弃，以及宏替换破坏字符串。这些会抵消整包复用节约的开发工作。

## 1. 确认了哪一份“旧源码”

| 对象 | 实际身份 | 本报告如何使用 |
| --- | --- | --- |
| 原始旧仓库 | 公开仓库 [Arcadia-1/EVAS](https://github.com/Arcadia-1/EVAS) | 真实独立 Git 仓库，不是新仓库里的 `evas/` |
| 当前旧工作树 | HEAD `17914d62b92dd6a15c8fa9792f09feed963c7597`；Python 0.8.4 / Rust 0.2.1；`parser.py`、`linter.py`、`test_linter.py` 有未提交修改 | 保留原状，不把它冒充固定镜像 0.8.7 |
| 本次主审源码 | 本地标签 `v0.8.7` → commit `6cb6fa7a7dac70fc0d4120126d8cf74258e6637b`，2026-07-28；Python 0.8.7 / Rust 0.2.4 | 通过 `git archive` 导出；公开链接固定到 [该提交源码](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/pyproject.toml)，所有源码定位均针对该导出 |
| 历史镜像提取源码 | 历史诊断的 `evas-source.tar.gz`（仅本地保留） | 归档 SHA-256 `420a1e17403ac03eb3de8bdd6bbce88169f33185ed824e9b64469329ac845bdc`；66/66 个文件与上述标签文件逐字节相同 |
| 历史部署二进制 | 历史收据 SHA-256 `e2a6a54b470578e9451e48427efede3f91b501ba8da20d368087ccad083928a4`，build revision 未知 | 本次没有运行该历史二进制；源码相同不构成其可复现构建证明 |
| 本次本地二进制 | 从导出源码执行 `cargo build --locked --offline`，Rust 0.2.4，macOS 本地 debug 构建 | 与部署镜像是不同执行身份；SHA-256、Python/Rust 工具版本见收据；二进制仅本地保留 |

许可证文件为 [MIT，Copyright (c) 2024 Zhishuai Zhang](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/LICENSE)。包元数据也声明 MIT；本次未完成第三方依赖的全量许可审计。真正导入代码或实质性测试素材时，应连同该版权和许可声明、来源 commit、原路径及修改说明保存；不能用新仓库名称抹掉来源。

[身份收据](evidence/provenance.json)记录标签 tree、导出文件哈希、66 文件对照和新仓库引用文件的提交/哈希。本次取到的是**真实 Git 标签源码**，并以**历史镜像提取字节**交叉绑定；历史诊断仅负责导航。

新实现只读参考固定如下。发布前将正文引用的 11 个文件与各自 Git 提交逐字节核对，全部相同；正文链接固定到这些提交及行号。未将并发工作树的其他未提交内容发布为提交源码。

| 参考检查点 | 捕获时 HEAD | `pyproject.toml` 版本 | 主要参照 |
| --- | --- | --- | --- |
| `vaEVAS-transition` / PR13 | `9850450505e7c43a5d62ce6dab6d74dcf65e7cf4` | 0.6.1 | `OperatorSpec`、调用点身份、带界历史与候选 Frame；README 此时仍写 0.6.0，以文件哈希为准 |
| `vaEVAS-absdelay` / PR14 | `a4b4fbe628c798c616ccdbcd82e04f36fcd41bb0` | 0.5.1 | 不可变语义 PWL、局部时间减法、移动断点 |
| `vaEVAS-slew` / PR15 | `5f0aba6a4312fbcddd261cc3e9de7f63736bef9a` | 0.5.1 | `direct_points` 的直接驱动依赖限制、解析分段输入 |

审查时采用逐文件捕获，不宣称三个工作树的全部内容处于同一基线或构成原子提交。文档 PR 以 main `e026cda71d4c8a6a5dde45d99b8c51ba3c182b94` 为基线，此时 PR13 已合入；这不构成 PR14/15 最新版本的验证。本次没有改动三个实现工作区。

## 2. 新执行证据与历史证据分开

共做 **47 个定向探针记录**：35 个主探针、8 个前端/波形探针、4 个 Rust 内核探针。其中 16 次要求生产 Rust 全模型路径的本地调用，12 次完成、4 次明确拒绝；完成的调用中包含错误行为。**47 不是通过数，也不是独立验证集条件数。** 其余是 parser/lowering、Python 辅助方法或 Rust 内核直接调用。

- [主探针输入与运行器](probes/probe_legacy.py)、[结果与本地二进制身份](evidence/python-probes.json)。
- [前端/波形运行器](probes/probe_frontend_waveforms.py)、[8 条结果](evidence/frontend-waveform-probes.json)。
- [Rust 内核探针](probes/probe_kernels.rs)、[4 条结果](evidence/rust-probes.jsonl)。
- [按解析答案计算的误差与完整性检查](evidence/summary.json)、[构建身份与资产可用性](evidence/provenance.json)。

积分参考由常数/线性函数的解析积分给出；滤波参考为 `τ=1, gain=1, x(t)=t, y(0)=0` 的 `y(t)=t−1+exp(−t)`；贡献参考直接使用原方程。不是把 Python 旧实现当 Rust 的 oracle。本次没有运行旧 pytest 全集、没有测试新实现、没有运行 Spectre、没有启动远程矩阵或付费资源。现有 Python 环境无 pytest，因此独立运行器使用原有 numpy 环境和标准库，不安装依赖。

| 新观测 ID | 实际结果 | 可支持的结论 |
| --- | --- | --- |
| D07 / D08 / D09 | 显式初值常量积分、线性积分、显式模数相位，各 9 点最大误差为 0 | 简单算术切片可利用；不证明任意反馈、复位或事件组合 |
| D10 | `idtmod(1.5,0)` 在 `t=1` 为 0.5，解析无界积分为 1.5 | 缺省模数被错误填成 1 |
| D11 | `q=idt(1,0); q=idt(2,0);` 在 `t=1` 得 1，第二调用应为 2 | 状态按赋值目标分配，两个调用历史串用 |
| D12 / F02 | 三参数 idt lowering 拒绝；三参数 timer parser 拒绝 | 接口缺口确认，不能通过函数名声称支持 |
| L01 / L02 | `t=1` 误差 0.0757262 / 0.0386847，步长分别 0.25 / 0.125 | 旧低通使用右端采样更新，PWL 输入不精确，误差随网格变化 |
| L03 / L04 | 双节点直接贡献拒绝；同一表达式先赋 real 再贡献能运行 | differential 输入限制属于具体 lowering 路径，并非所有滤波求值都不认识 `V(a,b)` |
| L06 / L07 | 两极点 NP/ZP 均被编码，但第二极点未进入 IR | 不能把“编译成功”当多阶滤波支持 |
| L08 | `den={1,-1}` 得与稳定 `{1,1}` 相同响应 | `abs(d1/d0)` 改变模型符号 |
| C01 / C02 | `1+2` 的两条贡献输出分别为 2 / 1，依语句顺序改变 | 确认最后写覆盖路径；不是所有旧 body-IR 路径都如此 |
| C03 | `y=1+0.5y` 初值 1.5，正确值 2 | 有限旧值代入，未解到每时刻原关系残差要求 |
| E01 | x 尚为 −0.15 时登记候选与历史；到 0、+0.15、+0.3 均无新候选 | 检测器历史先变更；完整候选方向拒绝路径另由源码核对，不能把本探针冒充全电路插桩 |
| K01 / K02 | 同刻改输入仍返回先前积分值；后查历史时刻返回未来积分值 | 内核更新函数没有独立 trial/recompute/history 查询契约 |
| K03 / N01 | `dt/τ=1e−20` 滤波增量为 0；NaN 误差比返回 0 | 需要稳定指数差与非有限数拒绝；N01 是辅助函数反例，不代表已测试所有生产误差入口 |
| F03 / F04 / F06 | 宏 `AB` 被 `A` 的前缀替换破坏；字符串内宏被替换；缺少实参生成空表达式 | 预处理不能原样复用 |
| F07 / F08 | 纯函数 `2x`、固定三次循环 `3x` 在 3 组输入上正确 | 局部函数展开/循环展开有可提取价值 |
| H01 / H02 | Python delay 辅助方法把 ramp 变为阶梯；生产 Rust 拒绝 absdelay | 存在辅助方法不等于生产支持；不应迁入该历史队列 |

已知历史“31 条件 basic 18/31、refined 8/31”及 D2 两场景通过仍是**旧固定镜像的历史结论**，本次没有重新计算、认证或覆盖它们。这里新增的 D09 也不是原两个 D2 条件的重跑。

## 3. 排序与工作节省类别

P0 是下一项动态能力的前置工作；P1 是在该基础上按需求提取；P2 是有相应用户场景后再做。优先级不是授权实施或时间承诺。

| 顺序 / 候选 | 判断 | 新架构目标层 | 可节省的工作类别 |
| --- | --- | --- | --- |
| 1 / R1 独立测试素材与反例，P0 | 筛选后直接复用输入；修正断言/夹具 | `evas/tests` 与独立 validation | 用例设计、失败缩减、接口边界发现 |
| 2 / R2 显式初值 `idt`，P0 | 修正后复用局部算术；重写状态接入 | Python OperatorSpec lowering → Rust operators/history | 数学原型、状态量识别、输入案例 |
| 3 / R3 `idtmod`，P0，依赖 R2 | 修正后复用 wrap 思路及测试 | 同上，增加模数/偏移契约 | 相位案例、边界枚举、重复评估反例 |
| 4 / R4 一阶 `laplace_nd`，P1 | 修正后复用系数归一化和受限更新 | Python 系数验证 → Rust 分段滤波 | 一阶模型映射、初始化与输出绑定 |
| 5 / R5 语法小片段，P1 | 修正后复用；不替换整套 parser | `syntax.py`、`frontend.py` | 词法/语法案例、AST 构造、错误位置 |
| 6 / R6 纯函数/固定循环 lowering，P1 | 修正后复用局部变换 | Python lowering，保留新贡献方程语义 | 参数代换、作用域展开、静态展开算法 |
| 7 / R7 波形源规范化，P1 | 修正后复用描述与受限构造 | Python 输入适配 → Rust `pwl/Trajectory` | pulse/SCS 输入约定、断点案例 |
| 8 / R8 宏预处理和诊断，P2 | 仅借鉴整体；修正后择取小函数 | Python source preprocessing / diagnostics | include/条件宏案例、报错语料 |
| 9 / R9 数值辅助与验证工具，P2 | 仅借鉴；一般内存拷贝可直接复用但收益小 | Rust 数值验证 / 测试工具 | 缓冲区检查、尺度化误差案例 |
| 10 / R10 历史与事件基础设施，架构前置约束 | 旧执行逻辑弃用；反例直接保留 | 延续新 `Frame/Operators` | 避免重新踩提交/去重/历史插值缺陷 |

没有估算节省天数；旧库面积大不等于可省的实现面积大。数值状态、贡献方程和已接受历史是架构边界，不能用适配层把旧副作用执行器藏进新求解器。

## 4. 候选逐项展开

### R1：优先迁入测试输入及独立 oracle（P0）

**具体来源。** [test_compiler.py](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/tests/test_compiler.py#L96) 的预处理/词法/声明/表达式案例；[test_audit_094f_body_ir_encoder.py](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/tests/test_audit_094f_body_ir_encoder.py#L279) 的纯函数展开；[test_engine.py](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/tests/test_engine.py#L1734) 的 VCO、积分、滤波模型；[test_audit_300_idtmod_fourth_arg.py](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/tests/test_audit_300_idtmod_fourth_arg.py#L62) 的第四参数及插值时间回归；[test_netlist.py](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/tests/test_netlist.py#L1557) 的 pulse 平台宽度。

**实际价值与证据。** F07/F08、D07–D11、L01–L04 给出独立可计算的接收和拒绝案例。最小切片直接采用本次 47 探针中的 VA 输入、解析答案和回归目的；新测试接口应重写，不搬旧构建器。D07/D08 每个输出点必须满足解析积分；L01/L02 应逐点满足解析 ODE；C01/C02 应对语句交换不变。

**依赖与缺陷。** 旧测试常用 `cargo build --release`、兄弟仓库 fixture、私有性能统计字段、`pytest.approx`，甚至自动 skip。[旧低通 parity 测试](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/tests/test_engine.py#L10023) 比较 Python 与 Rust，因此共同错误也可能通过。`test_audit_300` 把 offset 叫 reset，非零 offset 的拒绝测试只能作为旧缺口记录，不得转成新支持规范。Python `_idtmod` 的固定 `1e−9` wrap snapping 测试也不宜变成通用期望。

**目标与验收。** `evas/tests/test_dynamics.py` 等是建议新文件名，尚不存在；独立合同放在现有 validation 体系，保留原 31 条件身份。逐条记录来源、期望公式、容差、覆盖能力和反例；故意破坏 reset/phase/contribution 后对应断言必须失败；本地没有 Spectre 的测试不得因名字含 spectre 就获得后端认证。直接复用素材可省案例挖掘和反例缩减，不能省独立 oracle 编写。

### R2：显式初值 `idt` 小切片（P0）

**源码链。** [stmt_ir._append_idt_assignment_stmt_ops](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/stmt_ir.py#L1298) → [rust_program._extend_bindings_with_stateful_function_slots](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/rust_program.py#L882) → [expr.rs / BODY_STMT_IDT](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/expr.rs#L744)。另有 [program.rs / rust_sim_step_branch_idt_ops](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/program.rs#L366) 的支路电流路径，不能与 real 赋值路径混称一个实现。

**实际支持。** body 路径面向 real 标量赋值，接受至多两个实参，并会把缺参补零；用梯形更新 `z+=0.5*(x+x_prev)*dt`，同刻抑制重复积分。D07/D08 证实独立常量/PWL 线性输入及显式 IC 的算术成立；D02/D12 证实复位实参不通。没有证据证明无 IC 的 DC/反馈求解语义。

**必须修正。** 隐藏槽跟随 target 而非调用点，D11 出错；K01 同时刻更正输入不重算，K02 返回未来历史；支路路径在负 dt 时重置 IC，body 路径则保留已有积分，二者不一致。没有内核局部截断误差/残差认证，不能把外部步长控制视为动态方程求解器。

**最小迁移切片。** 先支持 `idt(direct_affine_input, constant_ic)`，限定直接驱动、连续 PWL 输入，参数有限，禁止内部节点反馈、嵌套和算子输出驱动事件。Python 为每个语法调用点生成独立算子 ID；Rust 在每个语义分段使用 `z(t0+h)=z0+x0*h+0.5*m*h²`。梯形公式可作为分段端点实现/对照，不搬旧状态槽和执行队列。源断点拆段，输出采样不得成为历史推进的定义。

**验收门槛。** 常量/正负斜率/非零 IC/两实例/同目标两调用分别对解析值核对；本报告量级的无反馈 dyadic 样例建议绝对误差 ≤`1e−12`。同一历史随机查询顺序、细粗输出网格、候选放弃再试结果一致；未支持的 reset、feedback、nonfinite 明确拒绝。后续再加入复位保持/释放，并单独通过该合同，首片不得声称 idt 全支持。

**目标层与收益。** 在 [新 Python lowering](https://github.com/BucketSran/vaEVAS/blob/9850450505e7c43a5d62ce6dab6d74dcf65e7cf4/evas/src/evas/lowering.py#L20) 与 [Rust OperatorSpec](https://github.com/BucketSran/vaEVAS/blob/9850450505e7c43a5d62ce6dab6d74dcf65e7cf4/evas/rust_core/src/ir.rs#L104) 扩展；历史进入新 Operators/Frame。可省数值原型与状态需求分析；不省动态状态契约和组合验证。

### R3：`idtmod` 相位切片（P0，依赖 R2）

**源码链。** [stmt_ir._append_idtmod_assignment_stmt_ops](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/stmt_ir.py#L1344)、[expr.rs / BODY_STMT_IDTMOD](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/expr.rs#L1049)、[Python CompiledModel._idtmod](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/backend.py#L5778)。

**实际支持与证据。** real 目标的积分+Euclidean remainder；三参数及字面量第四参数 0 可降低到三参数内核。D09 在明确模数 1 时通过手算相位；D04 拒绝非零 offset；D05/D10 证明省略模数被补 1；D06/K04 证明负模数仍被接受并取绝对值。Python 路径另有 `1e−9` 近边界归零，Rust 路径无同样处理，不能互当 oracle。

**规范核对。** LRM 2.4 §4.5.5 的第四参数是 **offset**；指定 modulus 应为正，省略 modulus 时是不回绕积分。旧变量 `reset_value` 和测试注释属于误命名，不能延续。[Accellera LRM 2.4](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf)

**最小迁移与目标。** 在 R2 的独立调用点历史上增加经过验证的 `modulus` 与 `offset`；可先明确只支持常量模数/偏移、直接输入。使用 `offset+rem_euclid(z−offset,modulus)`；省略模数委托无界积分。保留相位/周期信息应由精度设计决定，不直接维护无限增长的 binary64 总积分，也不靠固定 snapping 掩盖边界误差。

**验收门槛。** 正负频率、跨一个/多个周期、非零 offset、缺省 modulus、不合法 0/负 modulus、两实例/两调用；边界前后用可控 dyadic 时间以及 `nextafter` 邻点查侧别，离开边界的合法小相位不得清零。同一源粗细输出网格不改周期数。wrap 导致输出不连续，第一片禁止其输出进入 cross/反馈，直到相应事件断点/侧值合同落实。收益是相位模型和回归素材，不能以原 D2 两例通过省掉这些门槛。

### R4：一阶 `laplace_nd`（P1）

**源码链。** [backend._collect_evaluate_ir_laplace_nd_ops_from_stmt](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/backend.py#L8289) → [rust_program._convert_laplace_nd_ops](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/rust_program.py#L2646) → [program.rust_sim_step_laplace_nd_ops](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/program.rs#L529)。另一条为 [stmt_ir._encode_transfer_assignment_args](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/stmt_ir.py#L1122) → [expr.body_first_order_update](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/expr.rs#L447)。

**真实范围。** ND 只支持长度 1 的分子、长度 2 的分母及非零 d0/d1。直接贡献输入限制为单节点电压访问；body 赋值路径能处理双节点表达式。初始化输出为 DC 增益乘初始输入；每步使用 `alpha=1−exp(−dt/τ)` 和当前输入。不是通用有理传递函数引擎。直接滤波 op 与事件 ABI 的组合有显式拒绝；本次 L09 在更早的路径选择阶段被拒绝，未跑到那一行 ABI 检查。

**独立证据。** L01/L02 的 ramp 误差约减半，但细化后仍为 0.0386847；L03/L04 在等价双节点形式间行为不同；L05 拒绝二阶 ND；L08 把负时间常数稳定化；K03 在极小比值下 `1−exp()` 消减为零。

**最小迁移。** Python 把 `n0/(d0+d1*s)` 规范为 gain 与 τ，明确首片只支持 τ>0、有限系数、直接仿射连续 PWL 输入；不对负 τ 取绝对值。对单段 `x=x0+m*h`，以

`y(h)=e^(−h/τ)*y0 + gain*x0*(1−e^(−h/τ)) + gain*m*(h−τ*(1−e^(−h/τ)))`

更新，指数差使用 `expm1`，最后括号在小 h/τ 时还需稳定级数或等价的稳定函数。这是建议替换公式，本轮未实现。允许 `V(a,b)` 的统一输入 lowering，初态先限定可直接确定的 DC 稳态。

**验收。** step、ramp、常量、时间常数/幅度缩放、极小/大 h/τ、双节点等价、零增益、非法分母、同刻试算/放弃候选；对独立高精度解析解核对，精度阈值随量级明确声明，不以 Python/Rust parity 代替。高阶 ND、复杂极点和额外 NP/ZP 项必须明确拒绝。Rust 延用新 operator history，在尚无指数事件根求解时拒绝算子输出驱动 cross。收益为一阶系数映射、初始化和案例，不是整套 filter 内核。

### R5：语法、字面量与源位置（P1）

**来源。** [compiler/lexer.py](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/compiler/lexer.py#L1)、[parser._parse_primary / _parse_function_decl / _parse_single_event](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/compiler/parser.py#L2443)、[ast_nodes.py](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/compiler/ast_nodes.py#L1)。旧 AST 包含条件、case、for、数组、函数、参数、支路及组合事件；parser 的接收不等于生产 lowering 的接收。

**验证及问题。** L01–L07 经过真实 parser 的标准带撇号系数数组；F01/F02 区分 timer 两/三参数；F07/F08 穿过函数/循环 parser 和 Rust body 编码。F09 把非法 `8'hGG` 读为 0，F10 把含 X 的 `4'b10x1` 化为普通 9。旧 token 虽保留 raw 文本，但数值层已丢失未知位；该行为不能移到严格前端。

**最小切片。** 先为 R4 添加匿名系数数组、调用参数个数/源位置；再按实际模型需要增加声明/纯表达式，不一次性开启旧 lexer 的全部数字语言。维持新 parser 的完全消费、行列位置、严格拒绝以及实例绑定。目标为 [syntax.py](https://github.com/BucketSran/vaEVAS/blob/9850450505e7c43a5d62ce6dab6d74dcf65e7cf4/evas/src/evas/syntax.py#L1)、frontend 和 IR 源信息，不是旧 `compile_module`。

**验收。** 正反语法成对测试；同一语法等价写法生成相同语义但保留不同调用点身份；非法字面量/多余 token/未支持语法明确报错。未知位先拒绝，未来若支持则建模位宽/符号/四态语义。可省语法案例与 AST 构造设计；不省语言语义和新 IR 版本契约。

### R6：纯函数内联、静态循环与条件表达式（P1）

**来源。** [expr_ir._inline_user_function_call / _inline_user_function_stmt](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/expr_ir.py#L545)、[stmt_ir._unroll_static_for_statement / _static_for_loop_values](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/stmt_ir.py#L2776)。前者按形参建环境、局部变量代换、防止递归；后者要求静态初值/条件/更新、循环体不改控制变量，最多尝试 4096 次，再做替换。

**范围与证据。** F07 的纯 `2x` 函数、F08 的三次求和经原 Rust body 执行满足解析答案；不是对所有数组、局部作用域或 dynamic loop 的验证。旧函数默认返回 0、局部默认 0 的策略需要重新核对目标语言合同；旧 4096 上限和动态 while guard 属实现限制，不宜伪装成语言规定。

**最小切片。** 首先内联仅表达式/分支的无副作用 real 函数，禁止函数内动态算子、I/O、递归；使用新源身份与作用域绑定。随后只支持编译期有限循环，并检测爆炸式 IR 膨胀。贡献必须展开为新 `Contribution` 方程项，程序赋值则保持离散语句顺序，不能共用旧“写节点”代码。

**验收。** 形参实参同名、嵌套函数、参数覆盖、局部变量遮蔽、错误 arity、递归拒绝；循环 0/1/多次、负步进、无进展、上下界错误；多贡献求和、语句交换、两实例隔离。F07/F08 的三组输入是第一组独立回归，仍要扩展上述边界。收益是代换/静态展开框架；状态算子的条件执行另立合同，不能顺便放开。

### R7：波形源和网表适配（P1）

**来源。** [engine.pulse / dc / sine / pwl](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/engine.py#L7542)、[program.rust_sim_write_sources](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/program.rs#L1)、[spectre_parser._parse_pwl_wave_values / _build_source / parse_spectre](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/netlist/spectre_parser.py#L807)。Python waveform 闭包附带 `_evas_waveform` 描述，供 Rust 编码；pulse 区分 rise、plateau width 和 fall，这比只看函数签名更有价值。

**独立证据。** H03 平台宽度与斜边的 7 点手算通过；H04 PWL 的 5 点及端点保持通过。H05 极大异号端点的中点溢出为 inf，H06 接受 NaN 时间。因此旧插值和边界检查不能原封搬入；sine 的连续采样不提供新事件引擎所需的解析 PWL 契约，本轮未单独验证其事件行为。

**最小切片。** 先做 DC/有限 pulse → 有限时域 PWL 描述适配，延续新 `Trajectory` 的有限数、严格递增时间和受控断点；只提取 SCS source/parameter/instance 子集时要对未支持器件/命令报错。不要让旧网表“跳过行”的容错入口引入未执行模型。新库已有 PWL，收益主要在输入格式和 pulse 语义，不是再写一套 PWL 内核。

**验收。** rise/fall/plateau 边界、one-shot、起始 delay、周期端点；负时间参数/NaN/Inf/重复时间/大时间分辨率明确处理；有限窗口产生的每段与解析源相符；将输出采样网格改变不得改变源定义。目标为 Python adapter → [Rust pwl.rs](https://github.com/BucketSran/vaEVAS/blob/9850450505e7c43a5d62ce6dab6d74dcf65e7cf4/evas/rust_core/src/pwl.rs#L1)。

### R8：预处理和诊断（P2）

**来源。** [preprocessor.preprocess / _find_unexpanded_macro / _split_macro_args / _resolve_include](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/compiler/preprocessor.py#L15)、[linter.py](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/compiler/linter.py#L1)。条件宏/include 搜索和错误案例有价值；预处理返回展开字符串，缺少跨文件源映射，included_files 一次性抑制所有重复 include，不能直接代表完整预处理标准。

**独立证据。** F05 正确保留嵌套括号中的逗号；F03/F04/F06 显示 token 前缀、字符串及 arity 缺陷。旧 `test_backticks_in_comments_and_strings_are_not_macros` 只覆盖未定义宏，不能发现已定义宏在字符串内被替换。本轮没有把整个 linter 的规则正确性或 Spectre 兼容性认证一遍。

**最小切片与验收。** 复用嵌套实参分割思路和条件宏测试；token 化替换、词法状态、include 源映射和循环诊断重做/修正。测试定义宏出现在字符串/注释、宏名称前缀冲突、错误参数个数、条件分支中的不存在 include、嵌套目录相对 include、重复 include 的声明语义。诊断码应区分不支持与非法；linter 的能力清单不能授权执行器运行。目标是前端输入诊断；收益是案例和诊断语料，优先级低于动态算子首片。

### R9：数值辅助与工具（P2）

**来源。** [util.max_err_ratio_for_nodes / adaptive_step_floor / adaptive_shrink_step / interpolate_event_values_for_arrays](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/util.rs#L504)、[to_veriloga_integer](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/util.rs#L5)，以及普通 `copy_f64_values` 长度检查。

**独立证据及边界。** N02 与 `100/21` 的手算归一化差一致；N01 对 NaN 返回 0，不能作为认证 gate。K03 的指数差消减示例同时表明不能只看“使用 f64”。旧整数转换把非有限输入化为 0，溢出转换也没有新状态范围检查的合同。`max_err_ratio` 是相邻值变化比，不是 ODE 局部截断误差，更不是隐式方程残差或解误差上界。

**迁移判断。** 可直接复用一般 buffer 长度检查的代码形状，但价值很小；误差指标/步长控制仅借鉴接口和反例。新 [interval.rs](https://github.com/BucketSran/vaEVAS/blob/9850450505e7c43a5d62ce6dab6d74dcf65e7cf4/evas/rust_core/src/interval.rs#L1)、[solver.rs](https://github.com/BucketSran/vaEVAS/blob/9850450505e7c43a5d62ce6dab6d74dcf65e7cf4/evas/rust_core/src/solver.rs#L1)、settlement 的认证基础优先保留，不新增旧 adaptive 控制器。

**最小切片与门槛。** 把 N01/N02/K03 变为新数值层负/正控制，加入有限数检查、溢出拒绝、次正规数/大时间偏移、缩放和独立 Fraction/高精度参考。确需动态误差估计后另设计有方法阶数与误差意义的控制器；不把旧步长下限规则当准确性保证。收益是边界测试与接口经验。

### R10：旧历史、cross 提交、节点写入执行器（弃用代码，保留反例）

**具体位置。** [event.cross_detector_step_for_arrays](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/event.rs#L157) 在候选阶段更新历史；[program.rs 方向过滤](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/program.rs#L1420) 可 `continue` 而不回滚。旧 [backend._specify_path_delay / _absdelay](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/backend.py#L2699) 按采样保留变化值并作保持，夹带固定 epsilon 与裁剪。旧 [expr.evaluate_static_linear_ops](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/expr.rs#L22) 直接写 node；[stmt_ir 的 ContributionIR 路径](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/stmt_ir.py#L1668) 和 [write-spec 路径](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/simulator/stmt_ir.py#L2664) 的累加处理不同。

**证据与判断。** E01、H01/H02、C01–C03、K01/K02 联合支持弃用这些执行逻辑。旧 snapshot/restore、隐式有限刷新、特殊 runtime 选择器不能满足新候选原子提交和方程残差目标；代码能 snapshot 不等于所有拒绝路径都回滚。

**目标层。** 保留 [PR13 Frame / prepare_event](https://github.com/BucketSran/vaEVAS/blob/9850450505e7c43a5d62ce6dab6d74dcf65e7cf4/evas/rust_core/src/transient.rs#L12) 与 [Operators](https://github.com/BucketSran/vaEVAS/blob/9850450505e7c43a5d62ce6dab6d74dcf65e7cf4/evas/rust_core/src/operators.rs#L1) 的候选克隆；延续 [PR14 AbsDelay](https://github.com/BucketSran/vaEVAS/blob/a4b4fbe628c798c616ccdbcd82e04f36fcd41bb0/evas/rust_core/src/absdelay.rs#L1) 的不可变输入历史和带低位余量时间查询；参考 [PR15 direct_points](https://github.com/BucketSran/vaEVAS/blob/5f0aba6a4312fbcddd261cc3e9de7f63736bef9a/evas/rust_core/src/operators.rs#L15) 对原始依赖的检查。三者对应各自固定检查点，不能直接混拼其类型定义。

**最小切片与验收。** 仅把 E01、C01–C03、H01、K01/K02 作为新回归输入/设计反例；确认候选失败后状态、历史、事件去重、输出、算子断点一起不变；重试与从原始 accepted frame 首次执行完全一致；贡献语句交换不改解，原关系残差满足目标。收益是省去重复定位与错误架构返工，不是复制旧队列。

## 5. 明确不进入首轮迁移的模块

- **通用 `laplace_np/zp/zd`**：L06/L07 已证实额外极点丢弃；ND/NP 用绝对值改变时间常数/极点符号，ZD/ZP body 只接收原点零点等特定形状。Python helper 不支持的系数还可能直接返回 x（`backend.py:5459`）。没有可直接认证的通用传递函数实现；将来应从完整系数/状态空间合同设计。
- **`zi_*`、支路电流 idt/ddt、间接 ODE**：源码确有 [program.rs:196 起的滤波历史及 :366 起动态分支](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/evas/rust_core/src/program.rs#L196)，不能因旧 skill 声称“不支持 idt”就忽略它们。支路 idt 依赖 Python 生成的伪 current node 与独立 ABI；新架构当前是电压方程域，不能据此宣称获得 KCL/MNA。此组未做新的独立数值验证，不列为已认证候选；仅记录后续入口。
- **随机数/噪声/文件 I/O/专门高速内核**：不在本次优先目标；旧 thread-local RNG、文件副作用与 rollback 的兼容性未审。`specialized.rs`、whole-segment profile 不能作为新 solver 的实现捷径。
- **整个旧测试/示例库**：有过时能力文档、Python/Rust 自比、兄弟目录依赖与实现内部断言。可检索、按场景提取，不作为“一次跑绿即可迁移”的总认证。

## 6. 与新求解架构衔接时的真实门槛

1. **统一调用点和贡献语义。** `Origin(instance, source, line, column)`/显式 operator ID 是历史所有者，不能用赋值变量名。Python 构造版本化语义 IR，Rust 同时求贡献方程；节点值不是 `V(...) <+` 的赋值槽。[新 assembly](https://github.com/BucketSran/vaEVAS/blob/9850450505e7c43a5d62ce6dab6d74dcf65e7cf4/evas/rust_core/src/assembly.rs#L1) 已按实例局部支路组装方程。
2. **动态积分不能伪装成纯表达式。** 首片只做外生输入；若后续允许内部节点反馈，需要把积分状态放进方程，例如梯形离散残差 `R=z−z_n−h/2*(f(v,z,t)+f_n)=0`，与节点方程同刻求解，并有初始化、误差估计和不收敛错误。旧 `+=` 不提供这些。
3. **输出轨迹类别会变化。** PWL 的积分是分段二次，低通响应含指数，wrap 会跳变。新事件/guard 支持目前受限定，不能只在 OperatorSpec 增一个枚举就让它们进入所有 cross 路径。第一片保持算子输出驱动 cross/反馈/嵌套的明确拒绝；随后按轨迹类别补事件求根、界与侧值。
4. **reset 不是普通 transition 更新。** PR13 `prepare_event` 假定同刻算子值冻结，advance 后变化即报错；这适合正持续时间的连续 transition。idt 复位可使输出跳变，需要新的同刻 reset/重求解/原子提交规则，不能直接套用当前不变检查。持续 assert 时保持 IC，释放时从该时刻重新积分，需独立验证。
5. **旧失败不能靠默认值隐藏。** 非有限系数、负/零指定模数、不支持的高阶滤波、畸形 IR、未知算子参数均应清楚拒绝。新 IR 扩展同时更新 Python/Rust 解码、版本拒绝、文档及能力证据；旧 ABI opcode 225/238/244 和 ctypes 扁平数组不是新的公共接口。

建议实施顺序仅为设计产物：R1 → R2 限定无复位切片 → R3 正确模数/offset → reset 与事件组合 → R4 一阶滤波。R5/R6 按首片实际所需穿插；R7 仅在需要 SCS/pulse 入口时做。每一片先固定模型、解析答案与拒绝范围，再运行对应新实现回归；不要求先扩展整套语法。

## 7. 复核和交付边界

详细复现命令见 [REPRODUCE.md](REPRODUCE.md)。本 PR 复用 2026-09-29 审查运行的结果，仅整理公开材料，没有新增仿真运行。

原审查的完整性检查确认导出源码和参考快照的已捕获文件哈希未变；原工作树修改保留。发布材料通过资产哈希、47 个唯一探针 ID、解析误差重算和链接检查；机器绝对路径已移除，原始运行器内容保持不变。并发实现的后续变化仍由各自 PR 负责。

| 资产 | 可用性 |
| --- | --- |
| 本报告、原探针运行器、精简结果、来源及哈希清单 | 仓库内可取得，见 [evidence](evidence/provenance.json) 和 [probes](probes/probe_legacy.py) |
| 固定旧源码及被引用的新源码 | 公开 Git 提交可取得；正文使用永久链接 |
| 历史源码提取包、历史部署二进制、本地 debug 库、完整日志和工作树快照 | 仅本地保留；哈希不代表公开下载入口或可复现构建证明 |

成果是**可执行证据支撑的迁移建议**，不是迁移完成、正式 DVS 资格、最新三 PR 验收或历史部署二进制重建认证。发现负例是本次审查的有效结论；没有把失败转换成支持声明。
