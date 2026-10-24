# EVAS：电压域 Verilog-A 仿真器

模型支持范围及已有对照证据见[四后端支持范围](docs/COMPARISON.md)。

EVAS 面向 Verilog-A 行为模型的开发与验证。首要目标是提供开源、可审查的电压域仿真环境，
让使用者不依赖商业仿真器也能运行和验证目标模型，为 benchmark 提供开源复现路径。
EVAS 有独立的使用者、验收标准和交付成果；速度优化须保持模型语义和误差要求。

用户可以先用 EVAS 迭代模型，再用同一份 VA 验证 Spectre 兼容性，最后与实际器件网表共同仿真。
开源复现是建设目标，覆盖程度以具名版本和具体模型的对照证据为准。
benchmark 遇到 EVAS 能力缺口时，可以继续使用已校准的 Spectre 验收；
EVAS 按受影响的任务类别、工程使用频率与实现成本选择扩展，不要求题目等待全部能力补齐。

EVAS 把限定范围内的 Verilog-A 电压关系编译为方程，联立求解节点电压。
它适合描述理想电压域行为，例如增益、限幅、采样、事件计数和连续时间算子。
它不包含晶体管器件模型、电流/电荷方程或完整 SPICE 网表求解。

限定求解范围，为专门的算法和实现优化提供了空间；实际速度仍受模型规模、
稀疏性、事件密度和精度要求影响。性能结论需要绑定具体模型、误差标准与测量环境。
优化不能通过改变模型语义、跳过真实事件或放宽验收要求来获得速度收益。

前端使用 Python 解析、绑定并生成 IR，Rust 内核完成求解与时间推进。
同一支路的多条贡献会相加；程序赋值则保留顺序语义。
瞬态试算从已接受历史出发，电压、状态和误差检查通过后一起提交。

EVAS 的价值需要由电压域工程行为证明：在正确时刻采样，保持已读状态，并让边沿、滤波和积分
使用一致的历史。[OpenVAF-R 事件诊断](../experiments/backends/support/README.md#ngspice-events)
说明，模型编译成功甚至仿真完成，都可能没有实现这些行为。现有对照支持 EVAS 在已测范围内的
可用性；尚不能据此宣称全面优于 Gnucap、精度总是更高，或速度更快。

后续优先完善采样保持、迟滞比较器、定时与复位、VCO、边沿与滤波这些模型的组合验收。
每类都检查初始化、事件前后读值、历史延续、多个实例和误差控制，再扩展反馈及更复杂组合。
支持结论仍只维护在总表中。晶体管、电流与电荷方程不属于当前范围；性能优化排在行为与精度之后。

最近一次正式验收（同源400收据、完整CI与安装）的检查点为 **EVAS 0.24.1 / IR32**，生产源码 `0a8dc512`、身份测试修正 `159c0512`，本地release核 `3551db2dcdc6`。当时同源原始400为318通过、19失败、63拒绝；材料r3修订轨为321通过、15失败、64拒绝，剩79项。两轨仅新增019，旧317／320个通过全部保留。旧317份原响应仅engine版本标识变化，去掉该字段后完整JSON相同；19份旧失败checker字典不变。修订轨由当次396份原执行和4份新修订执行组成，未用此前部分运行补行。202份运行及构建输入与481份冻结打包源码分别计数，见[混合冷目标收据](../experiments/backends/support/low-cost-closure/mixed-cold-transition.json)。400全部PASS目标未完成。该检查点和下面两段2026-10-21候选的源码已随PR208于2026-10-21合入main（`deb5cf28`），版本仍为0.24.1、IR仍为32；未发布公共索引或tag。

2026-10-22，`main@6f3a6b54`（含PR208和PR220）的原始400开发重放为 **343通过、5失败、52拒绝，剩57项**，相对下面的 `19cf340f` 本地检查点零回退。这是用同一冻结checker和公共CLI得到的开发观察，不是验收收据：没有经过安装包与harness门禁，修订轨未重跑。剩余57项的分组和待决事项见[Issue214评论](https://github.com/BucketSran/vaEVAS/issues/214#issuecomment-6335640576)，汇总见[功能进度总览](docs/COMPARISON.md#progress-board)。

2026-10-21 的四路候选（当时未提交，后由 `cfbdeb00` 提交并随PR208合入main）实现了受限 native SCS 零相位入口、历史谓词的原电压接口、
普通 held timer 的有理偏移，以及物理 DC 供电乘保持历元斜坡。
最终 debug 核 `fc2c6c22b425` 对应46项不同 Python 方法、39项不同 Rust 测试及3类早期集成检查通过；
源代码、原红例和边界见[最小合同收据](../experiments/backends/support/low-cost-closure/minimum-contracts-four-lanes.json)。
该收据保留最小切片时点的局部结果；后续完整验证使用下面的新执行身份。

同日六原件后续候选基于 `19cf340f` 的当时未提交源码（同样由 `cfbdeb00` 提交并随PR208合入main），release核 `1132e1cac008`。
完整 Rust 为730通过、0失败、1项原有忽略；单次完整 Python 的2691个不同方法全部通过，无遗漏、失败、错误或跳过。
全新原始400为 **320通过、20失败、60拒绝**；材料r3修订轨为 **323通过、16失败、61拒绝，剩77项**。
两轨新增362、391，旧318／321个通过全部保留；前后均完成的原337份、修订336份完整响应逐字节相同。
修订轨使用本次396份原执行及4份新修订执行，012／075／077的独立后验通过，107仍拒绝且后验不可评估。
391原checker六性质通过；079完成仿真但原checker仍FAIL，074／093／364／390仍拒绝。
具体实现、独立正反例、阻塞和执行身份见[六原件收据](../experiments/backends/support/low-cost-closure/original-six.json)。
源码及必要POSIX临时目录在Mac，完整实验与归档在T7；1132份冻结源码中的257份实际构建输入已核对。
这份本地候选当时未运行新CI、安装或Spectre，没有新增共同Q资格；原失败、全额命令计费和旧检查点均保留。
合入后，PR208精确head `aabc769c` 的完整CI（含双平台安装）通过；该CI不重跑400，320/20/60仍是本地执行结果。

0.24.1为混合real与integer冷Transition保留独立认证，原019在最终release完整通过原checker，61项定向检查通过。前两次全量分别在0例、362例后被进程门禁拦住，失败记录与各1805.05秒计费保留；新全量经单调进程组生命周期门禁完整执行。首次CI三处旧版本断言已修正；完整交付CI `39394363248` 的15项检查通过，2644个不同Python方法实际通过，Rust655通过及1项忽略，双平台安装、重装和负控通过。工程验收未新增Spectre或共同Q资格。

此前IR31检查点增加事件体标量integer赋值根的直接物理输入电压转换，最近整数且半整数远离零，完整原值盒须证明同一signed32 bin；[合同及边界](docs/math/events.md#ir31-候选事件中的直接电压到-integer-转换)单独维护。IR30受限source Forcing与独立held Transition、IR29右移与按位与等原有边界保留。IR31保存请求须从原VA重编译为IR32。数学合同见[算子说明](docs/math/operators.md#independent-source-forcing-beside-held-histories)，历史版本见[更新记录](docs/UPDATE.md)。

IR32增加受限普通历史消费者、同支路二次源项与保持历史的组合、保持整数目标的紧凑表示，以及显式参数的解析正弦输入值。原请求Work、全部准入审计和精度预算保留。早期局部候选的199个唯一Python方法、110个不同Rust单元测试及6个原生测试保留其开发身份；最终验收使用上述wave27同源双轨和CI。原369、371仍被原1e9预算拒绝，原346仍有展开及derived clock组合缺口。数学合同见[算子手册](docs/math/operators.md#同支路二次源直接项的本地候选)与[解析源值合同](docs/math/events.md#ir32-private-candidate-explicit-analytic-source-values)。
此前IR32迭代曾使旧PASS027触及原100000审计上限；wave26恢复旧通过，原始314、修订317。该历史失败及恢复身份保留；本次wave27再次完整验证旧通过不回退。

本次接纳普通integer当前值与单点保持来源证明，原037、114、234在最终release核上完整通过原checker，响应与开发核074f28fd的对应结果逐字相同。完整误差盒、原Frame和共享Work保留。合同见[事件手册](docs/math/events.md#ordinary-current-integer-alias)，最终成绩与CI见[共同收据](../experiments/backends/support/low-cost-closure/ordinary-common-three.json)。

本次还接纳[回调位置的普通纯输入前缀](docs/math/events.md#ordinary-event-prefix)与[事件读取的integer Floor前缀](docs/math/events.md#ordinary-integer-event-prefix)。早期135个不同Python方法跨运行通过，公开编译IR上的2项Rust控制覆盖同Controller完整Frame与共享Work。k225旧费用保持、k226仍按原100000上限拒绝，signed32及Floor bin边界不放宽。局部身份见[前缀收据](../experiments/backends/support/low-cost-closure/ordinary-prefix.json)，不与最终全量方法数相加。

历史wave22生产快照 `ab928317` 绑定177份源码／构建输入、IR31、0.24.0和release核 `69c46e155808`，测试辅助提交为 `6d3c8a93`。原始400保持314通过、19失败、67拒绝，333完成；材料r3修订另轨400为317通过、15失败、68拒绝，332完成，两轨均清理400/400、零超时。原件新增027、142；修订轨先由075、再由077新增通过，旧316通过零回退，旧19份原失败checker字典不变。修订轨由同wave22的396份原执行、既有修订012／107／075及新正式执行的077组成。全部PASS仍差83项，350只是节点。
075原相邻样本平滑判据会误拒正确斜坡并放过瞬时跳变，独立Fraction参考与14项正负控制已证。修订仅增加250ps直接观察和必要的有限边沿检查，仍要求完整原checker及其0.40阈值；原VA、物理输入、时长、maxstep、精度和全部预算保持。正式725行保留原365点，32个直接边沿通过，两轴独审闭合；原075仍为FAIL。
077的说明把整个输出保持与实时输入加保持扰动混写。用户审阅具体提案后明确选择后者；修订保留原deck、参数和全部预算，只保持扰动、实时相加输入，完整checker核五性质。正式405直接行、独立Fraction校核、真实registry42项校准及完整400两轴独审通过；原077仍FAIL，未据此推断唯一原意。
[材料r3收据](../experiments/backends/support/low-cost-closure/continuation-wave22-materials-r3.json)绑定修订依据、正式执行与完整400映射。
单次完整delivery CI `39193253152` 在精确head `6d3c8a93` 实际15 jobs全部成功，2424个唯一Python方法通过，四分片705/514/634/571，无遗漏、重复、方法或setup跳过；两平台0.24/IR31安装、重装及负控通过。177份运行源码／构建输入与生产快照相同，本地、远端及wheel核各保留实际SHA。两轨输入、源核、预算、checker、覆盖与安装均已独审。
此前CI `39192407319` 的2423PASS及1个旧错误文案断言FAIL保留，coverage因失败分片跳过；同一非法内部电压仍拒绝，一行测试预期修正后18项相关方法通过并双轴复核，再用上述单次完整CI重验，未跨run拼绿。原041仍默认1e9预算拒绝，048仍8192根材料预算拒绝；371、346及369未验收改动不混入本轮。400全部PASS目标未完成，原生Goal已由用户恢复并核实active；既有原生Stop检查在317/400且83项有事可做时的精确命令重放仍阻止结束；用户已信任本地定义，真实原生Stop触发仍未观察到。PR208当时保持草稿、未合并（已于2026-10-21合入main），未发布公共索引/tag，未新增Spectre或正式共同资格。
[wave22紧凑收据](../experiments/backends/support/low-cost-closure/continuation-wave22.json)保留完整执行和独审身份；后续实现继续使用既有scope与400队列。

历史wave21生产提交 `a201378e` 绑定176份源码／构建输入、IR30、0.23.0和release核 `7e7ae92ae2de`。原件400份已完整执行：312通过、19失败、69拒绝，331完成，清理400/400；这不表示400份全部PASS。13+387件同源，旧312、303和基线198通过保留，旧19份失败checker字典相同，相对wave20新增PASS为0。原041在默认1e9证明预算下 `step_budget` 拒绝，checker未运行；R6作者独立PASS不替代统一结果。
修订材料另轨400为313通过、17失败、70拒绝，清理400/400；398份同材料复用本轮原件结果，另两份为修订012通过、107因 `condition_precision` 拒绝。它不替换原件计数。距离全部PASS，原件还差88份，修订轨还差87份；350只是进展节点。
单次完整delivery CI `39169679908` 在辅助修复提交 `8e507c51` 实际15 jobs全部成功，2390个唯一方法通过，四分片621/605/638/526，无遗漏、重复、方法或setup跳过。Ubuntu x86_64/Python3.10与macOS arm64/Python3.12的0.23/IR30安装、重装及负控通过；176份源码／构建输入不变，远端回归和wheel核各保留实际SHA，不声称与本地release字节相同。CI执行身份、完整方法覆盖和两平台安装证据已独立复核。
本轮先前CI `39168731444` 因inventory stale在完整Python前失败（0完整Python、0安装）；`39169086325` 完整失败，2375条为2372PASS及main/point/shaped三个loader ERROR，18个真实方法遗漏，15 jobs为10成功、4失败、1个上游失败导致coverage skip。两份原红记录保留，不跨run拼接全绿。PR208当时仍为草稿未合并（已于2026-10-21合入main），0.23是开发版本，未发布公共索引或tag；未新增Spectre共同资格，完整EVAS与400全部PASS目标未完成。

IR28新增事件体 typed 二元Subtract与运行期Remainder除数；IR27的Add与常量Remainder继续保留；IR26的受限原生事件`floor`和IR25的原生`tanh`继续保留；IR24的物理PWL、有限采样算术与transition组合继续保留。
范围与失败规则见[事件循环](docs/reference/frontend-admission.md#runtime-event-loops)和[事件数学](docs/math/events.md#event-math)；版本升级不代表支持表新增通过。

<a id="model-handoff"></a>

## 与电路仿真配合

模型移交以 `.va` 源码、实例参数、端口定义、初始条件和验证用例为基础。
模型在 EVAS 中通过后，先在 Spectre 中运行相同源码与等价刺激，再接入器件级网表。
具体负载、驱动和反馈连接由集成测试台声明，交给 Spectre 共同求解。

这三个层次分别验收：

| 层次 | 检查内容 |
| --- | --- |
| 数学正确性 | 根据规格和语言语义建立独立答案，检查电压关系、状态演化与事件 |
| 后端兼容性 | 同一模型在 EVAS 与 Spectre 中，事件次数、顺序、时刻和波形满足共同判据 |
| 网表集成 | 接入实际电路后，初始化、负载、反馈和接口假设仍符合模型规格 |

两个后端可以采用不同算法和内部时间步；比较使用事先约定的输出误差与事件要求。
相同名称的容差参数不保证相同的输出误差。发现差异时，分别检查模型写法、
语言语义、数值设置和求解器实现；不能仅以任一后端的结果作为正确答案。
EVAS 通过独立测试，也不能直接标记为已通过 Spectre 兼容性验证。

电压域模型还需要说明接口假设。例如，理想电压输出没有自动包含真实的输出阻抗、
限流和负载效应；这些行为需在模型或外围电路中显式表达，并在集成阶段验证。
预先计算的波形适合单向激励。存在电路反馈时，需要使用能响应输入变化的行为模型。

当前的[测试台读取](#spectre-testbench)和[后端对照](../experiments/backends/dvs2-spectre-validation/README.md)
是这条工作流的已有基础。兼容性证据限于已测模型、配置和仿真器版本；
通用的自动移交与 EVAS/Spectre 运行时同步接口尚未实现。

## 查询实际包与内核身份

`PYTHONPATH=evas/src python3 -m evas version --json --kernel /path/to/evas-kernel`
查询所选二进制的身份、SHA-256 与 IR 版本；省略 `--kernel` 时只查询 Python 包。
内核可直接运行 `evas-kernel --version --json`，无需 manifest 或标准输入。
缺少构建来源和独立请求协议元数据时明确返回 null；IR 匹配不等于全部运行兼容。
字段及失败行为见[身份接口](docs/reference/identity.md)。

## 仅编译预检

```sh
PYTHONPATH=evas/src python3 -m evas lint evas/examples/01-static-gain/sim.json
```

`lint` 检查 manifest 编译字段、源文件读取、参数绑定、受支持源码编译及 IR 资源预算，
输出 JSON，不查找或启动内核，并明确拒绝 `--kernel` / `--timeout` 执行选项。`lint_passed` 不检查数值请求内容、动态组合支持、
数值精度或外部仿真器兼容性。例如可编译的 timer/多项式 DAE 组合仍可能在瞬态执行时拒绝。
诊断只为已登记的 manifest/source I/O、参数依赖/覆盖和资源来源补充分类；
未登记的 code/kind 保留原消息、位置与额外字段，类别为 `unknown`，不按前缀或消息猜测。
接口与来源盘点边界见[诊断说明](docs/reference/diagnostics.md)。

## 安装配套发行包

平台 wheel 可携带独立 Rust 内核，安装后 `evas-rebuild solve MANIFEST` 无需 PYTHONPATH 或显式内核。
默认选择校验包内核身份；显式 `--kernel` 保持可用，失败不回退。
构建、安装、平台证据边界和源码方式见[安装合同](docs/reference/install.md)。尚未发布到公共索引或打 tag。

有限标量 `case/default` 的支持范围、资源预算与拒绝边界见 [case 契约](validation/CASE_STATEMENTS_CONTRACT.md)。

## 构建与运行

需要 Python 3.10+ 和 Rust/Cargo。以下命令从仓库根目录运行。
先构建内核，再求解一个静态示例：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas solve evas/examples/01-static-gain/sim.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

结果以 JSON 输出，包含节点顺序和各样本电压。
[第 1 课](examples/01-static-gain/README.md)的三个样本中，`out` 约为
`0.225 V`、`1.825 V`、`-0.325 V`；`ref` 的变化也参与支路电压方程。

只查看编译后的 IR，或运行带积分历史的瞬态示例：

```sh
PYTHONPATH=evas/src python3 -m evas compile evas/examples/01-static-gain/sim.json
PYTHONPATH=evas/src python3 -m evas transient evas/validation/smoke/idt.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

积分示例的五个观察点输出约为 `0.25`、`0.40`、`0.45`、`0.40`、`0.25 V`。
输入从正值线性降至负值，输出先增加、再减少，停止时回到初值。

manifest 声明源文件、实例参数和端口到全局网络的映射。
静态入口提供驱动节点与样本；瞬态入口提供 PWL 源、观察时间和停止时间。
`solve` 不推进历史；含状态、事件或历史算子的模型使用 `transient`。
[examples/](examples/) 从静态求解、瞬态历史讲到事件；第 4 课展示当前分支的事件与积分组合候选，
每课提供模型、运行清单与期望输出；覆盖各条仿真能力路径的最小冒烟集
（静态非线性、连续积分、延迟历史、定时/过阈事件、有限边沿）见
[validation/smoke/](validation/smoke/)：

| 冒烟输入 | 说明 |
| --- | --- |
| [static_nonlinear.json](validation/smoke/static_nonlinear.json) | 多项式电压关系的工作点 |
| [cross_counter.json](validation/smoke/cross_counter.json) | 输入过阈值后更新计数状态 |
| [timer_counter.json](validation/smoke/timer_counter.json) | 固定定时事件 |
| [transition_pulse.json](validation/smoke/transition_pulse.json) | 有限上升/下降沿 |
| [absdelay.json](validation/smoke/absdelay.json) | 延迟历史查询 |
| [idt.json](validation/smoke/idt.json) | 连续输入积分 |

当前准入下，冻结的 `absdelay`、`timer_counter` 原 VA 缺少 discipline 声明，
`cross_counter` 原 VA 含非法小数拼写，直接按这些 manifest 重编译会拒绝。
原文件与历史结果保留；可运行的显式版本见
[smoke-admission-v1 successors](tests/fixtures/smoke-admission-v1/README.md)。
`idt`、`transition_pulse` 和 `static_nonlinear` 的原 manifest 仍可编译。
CLI 的 `solve`/`transient` 会读取 manifest 的 VA 并重新编译；
API 运行已有 `Program` 不重复源码准入，但仍须满足当前 IR/内核版本契约。

## 精度与结果解释

支持独立于输出网格的 `strobetimes` 和周期 strobe 控制，见[强制求解时刻](docs/reference/strobe.md)。
`solve`、`transient` 和 manifest 的 `tolerances` 接受 `vabstol`（默认 `1e-12 V`）
与 `reltol`（默认 `1e-10`，无量纲）。这两个数字是求解/验收设置，
不能直接解释为所有输出都具有同样的全时域精度。
静态 Newton 检查原方程残差；瞬态还要考虑输入、历史、采样及事件时刻的误差和网络放大。
各控制项和失败处理见[精度控制](docs/math/solving.md#当前精度控制怎么用)，具体数值方法见同章。
瞬态响应可选保存实际控制值、逐行来源和已有节点认证区间，见[观察证据接口](docs/reference/observation-evidence.md)。缺失区间保持未知，这些字段不自动授予外部观察资格。

<a id="spectre-testbench"></a>

### Spectre 风格电压测试台

`simulate` 将受限 `.scs` 输入转换为已有的实例、PWL 和瞬态请求，再交给同一 Rust 内核：

```sh
PYTHONPATH=evas/src python3 -m evas simulate evas/examples/01-static-gain/tb.scs --kernel evas/rust_core/target/debug/evas-kernel
```

[示例测试台](examples/01-static-gain/tb.scs)的独立答案是 `out = 2*u - 0.125 V`。
API 为 `evas.scs.load_scs(path)`（检查测试台并返回 manifest 和模型文本），
以及 `simulate_scs(path, kernel=...)`（编译并运行）。`load_scs` 成功只说明已完成输入适配，
不代表 IR 编译、动态组合或数值验收成功。

| 输入 | 当前接受范围 |
| --- | --- |
| 模型与连接 | `ahdl_include "file.va"`；按 VA 声明顺序展开静态向量后逐位连接的标量节点列表；常量参数覆盖；`global 0` |
| 数字 | 有限十进制、科学计数和单字母 SI 后缀 `T G M k K m u n p f a`；可引用先前 `parameters` 语句的常量 |
| `vsource` | 一端接地；`dc`；从零开始、时间严格递增的 `wave=[time value ...]`；显式 `rise/width/fall/period/val0/val1` 的线性 pulse，`delay` 缺省为 0 |
| `bsource` 电压式 | 一端接地；`v=V(node)`，可加减一个有限常量或先前 `parameters` 常量；偏移可用一层括号包住，例如 `v=V(vin)+(-0.04)` |
| 瞬态 | 一条 `tran tran stop=... maxstep=...`，两项必须显式指定且为正；观察点取 `0`、转换为浮点数后仍小于 stop 的 `k*maxstep`、一次 stop，以及 `[0, stop]` 内全部源折点的并集；可另给 [strobe 五项控制](docs/reference/strobe.md)，不改变常规观察网格 |
| 保存策略 | 显式 `tran strobeoutput=all/strobeonly` 选择常规与强制行的并集，或强制行加终止行；周期窗口外保留常规行，详见 [strobe 保存合同](docs/reference/strobe.md#显式保存策略) |
| 精度 | `options reltol=... vabstol=...`，映射到现有 EVAS 设置；未指定项使用 EVAS 默认值，不采用 Spectre 默认值 |
| 电流容差兼容 | `options iabstol=...` 接受有限、非负标量，但发出 warning；EVAS 没有电流未知量，该值不参与求解 |
| 精度预设兼容 | `tran` 的 `errpreset=liberal/moderate/conservative` 接受但发出 warning，不应用 Spectre 的预设调整；使用显式容差和步长，未指定容差使用 EVAS 默认值 |
| 输出 | `save` 选择标量节点；无同名电气节点时接受 `time`，时间轴单独保存在 `saved.times`；原 `solutions` 保留完整求解响应 |

`save time y u` 将时间保存在 `saved.times`，电压列按 `y`、`u` 排列；重复选择不增加列。
若 `time` 是实际连接或驱动的电气节点，`save time` 仍保存其电压。
只有非节点 `time` 时，沿用未指定节点保存的 EVAS 默认列，包括地节点；这不等于 Spectre 的完整默认保存集合。
名称区分大小写，`Time` 仍须是已知节点。非节点 `time` 只作时间轴兼容选择，
EVAS 不导出 Spectre 可能同时产生的 `param_real` 同名记录。
未知节点和 `V(node)` 等范围外选择语法继续拒绝。
[保存回归](tests/test_scs_save.py)覆盖 API、CLI、strobe 行对齐及 manifest 的完整 CSV 导出；
后者保留全部节点，不按 SCS 的 `save` 选择裁列。

所有外部 `vsource` 驱动都保留在请求中，包括未连接到 VA 端口、仅被行为源引用的节点；
不能把它们变成待解的内部节点。独立回归见 [SCS 驱动保留](tests/test_scs_driven_nodes.py)。

输入允许 `//` 注释、反斜杠续行和跨行括号。所有字段必须被消费。
未知 options、未知 `errpreset` 值、sine、理想跳变、浮动源、R/C/I 器件、
子电路指令、电流探针、总线名/范围/拼接/切片等连接语法均明确拒绝；不把它们当作可忽略的文本。
VA 的自定义 include 仍使用显式 source 清单；适配器只加载 `ahdl_include` 列出的文件。
重复源、重复设置、非法源时刻和未知 save 节点在运行前拒绝。

例如 `options reltol=1e-6 vabstol=1e-9 iabstol=1e-15` 保留两项电压求解设置，
并警告 `iabstol` 被忽略、实际不生效。API 发出 `ScsIgnoredOptionWarning`，
成功结果的 `testbench.warnings` 记录请求值、原因和网表位置；`load_scs` 的对应字段为 `metadata.warnings`。
CLI 在 stderr 输出包含 `warnings` 的 JSON，成功结果仍在 stdout。
若后续检查或求解失败，已发出的 warnings 附在同一个错误 JSON 中，保留原错误及退出码。
`iabstol` 的非法数值和重复声明仍拒绝；接受该选项不增加电流网络支持。

`errpreset` 的 warning 在网表语句扫描和基本数值检查完成后发出，
包含最终 `effective_controls`，即 `reltol`、`vabstol` 和 `max_step`。
例如请求 `reltol=1e-6` 和 `errpreset=conservative` 时，EVAS 仍采用 `reltol=1e-6`，
不会套用 Spectre 的预设缩放。这种输入兼容不保证两者具有相同实际误差。

`B (us 0) bsource v=V(vin)+(0.04)` 表示 `V(us)=V(vin)+0.04 V`。
适配器将它转换成普通 VA 电压关系，交给同一 Rust 内核联立求解；引用内部节点时也不会预计算波形。
反向接地端口保留电压方向，串联源可按任意声明顺序连接。
未知参考节点、同一节点的重复 `bsource`/`vsource` 驱动、电流表达式、乘除和一般函数表达式均拒绝。
测试台仍须包含 `ahdl_include` 和 VA 实例；这不是完整的 Spectre 行为源实现。
独立三角波、正负偏移、反向连接和反馈答案见 [bsource 回归](tests/test_scs_bsource.py)。

含 `bsource` 时，`load_scs` 返回的 `sources` 包含一个只存在于内存的辅助 VA 模型，
`manifest` 必须与这些源码一起使用；直接将 manifest 保存后交给文件入口会缺少该生成文件。
`model_sha256` 保留原文件哈希，`generated_model_sha256` 单独记录生成源码的哈希。
辅助模型名和源码键避开用户已声明的模型及文件，不写入或覆盖磁盘文件。

静态向量端口按每个实例的有效参数展开，索引按声明方向依次连接。
例如 `input [1:0] u; output [0:1] y;` 的 `DUT (a b c d) bus`
对应 `u[1]=a,u[0]=b,y[0]=c,y[1]=d`；列表长度必须与展开后的端口数相同。
参数宽度、负/非零索引和单元素范围复用已有 VA 绑定规则。
见[输入契约与 Spectre 准入证据](validation/SCS_VECTOR_CONTRACT.md)及
[公共入口回归](tests/test_scs_vectors.py)。

DC 和 PWL 保留输入数值与所有拐点。PWL 末点之后保持最后的值。
线性 pulse 的 `delay` 缺省为 0 s，依据安装版 Spectre 21.1 的源参数帮助及
[两个实际静态对照](../experiments/backends/support/pulse-delay/README.md)。
`val0/val1/rise/fall/width/period` 仍须显式提供，不采用其他 Spectre 默认值。
缺省 delay 与显式零进入相同的源构造和误差检查；显式非零 delay 的意义保持。
pulse 的第 k 次起点为 `d+kP`，四个拐点为 `d+kP`、`d+kP+r`、
`d+kP+r+w`、`d+kP+r+w+f`；要求 `r,f,P>0`、`d,w>=0`、`r+w+f<=P`。
拐点由已解析的 binary64 参数用有理数计算，再舍入为保存的 binary64 时刻。
不能精确表示的拐点仍保留源电压误差界。有限原始角点同时进入 IR24 的物理曲线描述，
内核验证它在名义 PWL 的原误差带内，再按真实曲线求值、导数和 cross 根。
每次有理数转 binary64 的误差仍随电压及采样状态传播，超出 `vabstol/reltol` 时拒绝。
`testbench.pulse_corner_proofs` 保留角点、舍入时刻和原非零电压界；
`pulse_corner_rounding_seconds` 保留最大时刻偏差。
Python `transient` 及 manifest 以 `source_errors={"node": upper_bound_V}` 提供有限非负幅度界，
另以 `source_shapes` 提供有限原始曲线。仅有幅度界的 cross、保持状态 timer 与算子请求仍拒绝。
物理曲线最多 512 点，当前动态消费者限已支持的 cross、timer 与 transition；
具体字段、证明和拒绝边界见[源曲线契约](docs/math/events.md#physical-source-shape)。
此选项不属于静态 `solve` API，时刻分辨率不能区分边沿时仍拒绝。
这不是通过输出网格采样近似 pulse；改变 maxstep 不改变源拐点。
保存网格包含源折点，避免后续对保存的驱动电压做线性插值时漏掉窄脉冲。
例如源在 `.25 s` 为零、`.375 s` 为 `1 V`、`.4375 s` 回零，即使 `maxstep=.5 s`，
这三个时刻仍被保存。驱动电压可按原线段插值；模型输出若含非线性或事件，仍须按各自观察合同验收。
网表 token、输出点和每个 pulse 点均有 100000 的资源上限。

`testbench` 同时记录测试台/模型 SHA256、生效容差及观察网格约定。
格式适配不等于完整 Spectre 兼容或对照实验；独立答案与 manifest 等价性由
[test_scs.py](tests/test_scs.py)检查。网表解析与源构造分别位于
[scs.py](src/evas/scs.py)和[scs_sources.py](src/evas/scs_sources.py)。

旧 IR 1–21 必须从原始 VA/manifest 重新编译；前端与内核需要配套。
批量工具和兼容性规则见[IR 版本与迁移](#ir-v8-migration)。

## 验证与开发

[独立验证集](validation/README.md)维护模型契约、数学答案和判据。
[当前执行证据](../experiments/runs/capability-completion/README.md)记录原 31 条件
两档回放及实际被测源码/内核身份。有限观测达标不等于完整 Verilog-A 合规、
连续时间资格或性能领先；详细结果与历史失败分别保留。

从仓库根目录运行开发检查：

```sh
PYTHONPATH=evas/src python3 -m unittest discover -s evas/tests -v
cargo test --locked --manifest-path evas/rust_core/Cargo.toml
```

[CI 工作流](../.github/workflows/numerical-assurance.yml)区分草稿迭代和完整交付，具体规则见
[CI 阶段与检查范围](../scripts/README.md#ci-按改动选择检查)。本地先执行最小复现和受影响模块；
草稿 CI 先检查格式、Clippy、Python 基本错误和生成清单，再执行已映射的相关回归。
稳定候选执行完整 Python/Rust 回归、相关静态校准、ngspice 共同子集、有界 fuzz 和两平台安装。
完整 Python 回归按模块分为四组，汇总核对所有测试恰好覆盖一次。CI 只复用完整身份匹配的成功证据；
普通 Cargo 缓存仍只加速构建。普通说明文档走快速检查，能力表与评测标准保留最终校准要求。
回归使用 Python 3.12、Rust stable，fuzz 使用 nightly。CI 不自动执行 Spectre 或原 31×2 矩阵，
各次矩阵执行与正式资格边界仍以具名收据为准。

静态回放工具 [run_static_regression.py](tests/run_static_regression.py) 检查符合静态入口的
原矩阵模型；两档的采样点与残差检查不能替代瞬态事件验证。
新增能力需要同时说明数学含义、状态生命周期、组合边界和独立答案，要求见
[技术手册](docs/README.md#feature-documentation-contract)。

<a id="实现范围"></a>

语法和参数的详细约束见[模型编译](docs/reference/frontend-admission.md#模型编译)。
逐端口方向的 ANSI 头部、正文补 discipline 及拒绝边界见 [ANSI 端口声明](docs/reference/frontend-admission.md#ansi-端口声明)。

<a id="frontend-boundaries"></a>

## 前端输入与执行边界

CLI 与迁移工具共用 manifest 校验。`models` 和 `instances` 必须是非空数组；
实例的 `connections`、`parameters` 必须是对象。重复 JSON 字段和非有限数字会被拒绝，
避免后一个参数悄悄覆盖前一个。迁移中已识别的输入错误按单项记录，后续模型继续处理。

编译器有明确的资源预算。这些是实现限制，不是 Verilog-A 语言规则：

| 对象 | 当前上限 |
| --- | ---: |
| 语法递归嵌套 | 64 层 |
| 源表达式树深度 | 80 层 |
| 覆盖后有效参数依赖链 | 64 层 |
| Program 序列化容器深度 | 96 层，为 Rust 请求外层保留空间 |
| 展开后的 IR 值与容器总数 | 100,000 |

参数按有效依赖图迭代求值，声明顺序不改变依赖链限制。IR 大小检查计入每次引用的展开成本，
同时缓存子图的计算结果；不会为了估算大小而先复制整个表达式树。原生事件审核还在同一请求的单一 NativeAudit 中，
复用传递不可变 IR 子图已证明的深度和展开大小；缓存强引用对象，不能跨请求复用或缓存可变后代。
每个父引用仍累计完整展开尺寸，序列化仍复制和计入全部 wire 项；新增查找、元数据扫描和缓存存储先扣原100000累计预算。
见[独立缓存边界控制](tests/test_ir_cache.py)。纯函数的编译期
校验义务按同一展开中的 AST 身份合并；义务不加入计算值替换或序列化的展开成本，
函数赋值 RHS 和返回值仍检查原深度/大小上限。源 token 总数限 100,000，函数调用嵌套
限 64；函数调用、表达式下降与条件体嵌套共同累计到 80 层展开深度预算，
避免分别合规的嵌套相乘使编译器递归溢出；不另设累计校验图上限。
超限时返回带源码位置的 `CompileError`。合法但过大的模型也可能被拒绝，
包括旧版本偶尔能处理的长表达式。使用 IR28，不通过重关联算式或消去依赖绕过预算；
更大的模型需要后续共享表达式 IR 或其他有独立验证的方案。

`solve` / `transient` 的 `timeout` 默认 **300 秒**，只限制内核进程执行时间，
不包含 Python 编译与序列化。API 可传正的有限秒数，或用 `timeout=None` 关闭上限。
CLI 使用 `--timeout 600` 调整；时间超限会终止并回收内核子进程，报告 `kernel_timeout`。
仿真时间 `stop` 与这个墙钟时间上限是两个不同设置。

CLI 的内核失败在 stderr 输出 JSON，保留 `kind`、`message` 和存在时的 `sample`；
成功结果仍输出到 stdout。输入/编译错误也输出带 code/阶段的 JSON，错误退出码均为 2。
适配器验证返回结果的身份、行数、电压/状态维度及有限数值；坏响应为 `invalid_response`，
无法启动进程或不合格式的进程错误为 `kernel_process`。
这些检查保护调用边界，不代替内核的电压精度验收。

## 模块与接口

仅编译预检接口为 `evas.lint.lint_manifest(path) -> dict`。
Python 的编译与求解接口：`compile_sources(sources, instances) -> Program`，
`solve(program, driven, samples, kernel=...) -> result`，以及
`transient(program, sources, output_times, stop=..., max_step=..., kernel=...) -> result`。
支持独立于输出网格的 `strobetimes` 和周期 strobe 控制，见[强制求解时刻](docs/reference/strobe.md)。
`solve`、`transient` 和 manifest 的 `tolerances` 接受 `vabstol`（伏特，默认 `1e-12`）与
`reltol`（无量纲，默认 `1e-10`），例如 `solve(..., vabstol=1e-9, reltol=1e-6)`。
保留 `absolute` / `relative` 作为对应旧名称；同一容差不能同时提供新旧名称。
本分支的非线性 Taylor/DAE 路径将节点容差用于候选细化，并保留最终前向电压误差验收。
`max_step` 同时限制其内部试步；线性/PWL 解析路径保持解析传播。观察网格不定义积分历史。
模型还可用 [`$bound_step`](docs/math/events.md#bound-step) 限制下一次推进；它与 `max_step` 取最小值。
已支持的非线性积分路径也应用动态请求来限制内部接受段；隐式 DAE 仍只接受正的无条件常数请求。
极小步长或无法认证的累计包围会明确失败，资源上限与数学说明见
[非线性精度控制](docs/math/continuous.md#多项式非线性积分与误差证明)。
Python 前端与 Rust 内核使用相同的 IR 版本；当前版本及迁移规则见[下文](#ir-v8-migration)。

Rust 库接口：`Circuit::new(...)` 和无状态的 `Circuit::solve(inputs)`。
独立 Rust 进程也校验 IR，不能依赖 Python 已验证输入。

静态批量求解默认串行。设置 `EVAS_STATIC_THREADS=4` 可让内核并行处理独立样本，
合法线程数为 1–64；结果顺序和首个失败的样本下标不变。Rust 调用方可用
`run_with_threads(request, 4)`。瞬态仍按时间顺序推进；线程启动有开销，小批量未必更快。

语法解析不依赖 IR；绑定层只依赖语法树与 IR。Rust 求解层依赖内部组装模块，
组装模块依赖 IR 和表达式校验，不反向调用求解层。`Circuit::new` 保留为公开构造入口，
内部组装结果不成为新的公共 API。结构化支路身份沿用 v2；表达式、事件与算子的当前 IR 版本及序列化迁移规则见[下文](#ir-v8-migration)。

当前用 JSON 进程接口使 IR 易于检查，避免先复制旧的复杂 FFI。
性能基准覆盖 Rust 库内静态求解、批量并行和五类瞬态路径。
这些计时不含 Python/JSON 进程接口，不能直接代表端到端吞吐量或跨后端速度。

<a id="review-map"></a>

## 按功能审查

源码按下面六组责任阅读。表中列出入口，具体辅助模块由对应章节说明。
这些是阅读分组，当前文件路径保持原布局。

| 功能与数学入口 | 源码入口及责任 | 独立契约 | 回归入口 |
| --- | --- | --- | --- |
| 模型编译与贡献：[参数](#参数绑定契约)、[IR 与贡献](#ir-与贡献契约) | [syntax.py](src/evas/syntax.py) 解析；[frontend.py](src/evas/frontend.py) 编排；[instance_compiler.py](src/evas/instance_compiler.py) 绑定实例、参数、状态和调用点；[lowering.py](src/evas/lowering.py) 转换表达式；[Python IR](src/evas/ir.py) / [Rust IR](rust_core/src/ir.rs) 定义传输；[assembly.rs](rust_core/src/assembly.rs) 累加贡献 | 本页接口契约；[起步案例卡](validation/CASE_CARDS.md)的静态关系 | [test_contracts.py](tests/test_contracts.py)、[test_affine.py](tests/test_affine.py) |
| 电压求解与精度：[NUMERICS](docs/math/solving.md) | [solver.rs](rust_core/src/solver.rs) 工作点；[nonlinear.rs](rust_core/src/nonlinear.rs) Newton；[linear.rs](rust_core/src/linear.rs) 稠密/稀疏分流；[analog.rs](rust_core/src/analog.rs) 无状态瞬态与普通条件；[expression.rs](rust_core/src/expression.rs)、[interval.rs](rust_core/src/interval.rs)、[affine_bounds.rs](rust_core/src/affine_bounds.rs) 提供共用运算与认证 | [非线性瞬态](validation/NONLINEAR_TRANSIENT_CONTRACT.md)、[普通条件](validation/ANALOG_CONDITIONS_CONTRACT.md) | [精度](tests/test_accuracy.py)、[稀疏](tests/test_sparse.py)、[普通条件](tests/test_analog_conditions.py)、[非线性瞬态](tests/test_nonlinear_transient.py)、[精度链](tests/test_precision_chain.py) |
| 事件与同刻关系：[EVENTS](docs/math/events.md) | [events.rs](rust_core/src/events.rs) 赋值语义；[event_conditions.rs](rust_core/src/event_conditions.rs) 选支；[pwl.rs](rust_core/src/pwl.rs) 输入与仿射根；[schedule.rs](rust_core/src/schedule.rs) 日程；[event_accuracy.rs](rust_core/src/event_accuracy.rs) 定位认证；[settlement.rs](rust_core/src/settlement.rs) / [settlement_bounds.rs](rust_core/src/settlement_bounds.rs) 联立求解与误差 | [事件条件](validation/EVENT_CONDITIONS_CONTRACT.md)、[定时契约](validation/TIMED_OPERATOR_CONTRACTS.md) | [cross](tests/test_events.py)、[timer](tests/test_timer.py)、[同刻](tests/test_settlement.py)、[条件](tests/test_event_conditions.py)、[OR](tests/test_event_or.py)、[写者冲突](tests/test_event_writers.py) |
| 独立波形算子：[OPERATORS](docs/math/operators.md) | [operators.rs](rust_core/src/operators.rs) 管理调用点、值/区间查询及候选历史；各算子的文件与测试见[算子对应表](docs/math/operators.md#operator-map) | [定时算子](validation/TIMED_OPERATOR_CONTRACTS.md)、[积分](validation/DYNAMICS_CONTRACTS.md)、[低通](validation/LAPLACE_CONTRACTS.md) | 各算子回归；[定时组合](tests/test_timed_composition.py)、[语义不变性](tests/test_semantic_invariants.py) |
| 联合连续动态：[CONTINUOUS](docs/math/continuous.md) | [continuous.rs](rust_core/src/continuous.rs) 关系与 DC；[continuous_derivatives.rs](rust_core/src/continuous_derivatives.rs) 导数；[state_space.rs](rust_core/src/state_space.rs) 线性传播；[nonlinear_dynamics.rs](rust_core/src/nonlinear_dynamics.rs) 多项式传播；[implicit_dynamics.rs](rust_core/src/implicit_dynamics.rs) DAE；[continuous_initialization.rs](rust_core/src/continuous_initialization.rs) 联合冷启动；[guard_trajectory.rs](rust_core/src/guard_trajectory.rs) / [dynamic_roots.rs](rust_core/src/dynamic_roots.rs) 动态根 | [动态与生命周期](validation/DYNAMICS_CONTRACTS.md) | [连续关系](tests/test_continuous_dynamics.py)、[动态 cross](tests/test_dynamic_cross.py)、[动态组合](tests/test_dynamic_closure.py)、[混合算子](tests/test_mixed_dynamics.py)、[DAE](tests/test_implicit_dynamics.py) |
| 请求与接受帧：[共同生命周期](docs/math/continuous.md#shared-lifecycle-closure) | [__main__.py](src/evas/__main__.py) / [manifest.py](src/evas/manifest.py) 校验输入；[runtime.py](src/evas/runtime.py) / [protocol.py](src/evas/protocol.py) 处理进程与响应；[main.rs](rust_core/src/main.rs) 处理请求；[transient.rs](rust_core/src/transient.rs) 试算与整批提交；[continuous_runtime.rs](rust_core/src/continuous_runtime.rs) / [continuous_history.rs](rust_core/src/continuous_history.rs) 区分观察与未来历史；[reset_dependencies.rs](rust_core/src/reset_dependencies.rs) 检查复位及瞬时反馈依赖 | [共同生命周期契约](validation/DYNAMICS_CONTRACTS.md#shared-lifecycle-contract) | [观察闭包](tests/test_lifecycle_closure.py)、[事件时间盒](tests/test_event_window_sampling.py)、[已知事件截止点](tests/test_event_horizons.py)；[真实控制器回退](rust_core/src/transient_lifecycle_tests.rs) |

`tests/` 与 `validation/` 的分工：**[tests/](tests/) 是"改代码时别改坏"的护栏**——
开发回归套件，随时全量运行，期望值独立于实现但准入跟随开发节奏；
**[validation/](validation/) 是"证明它本来是对的"的证据**——固定的条件矩阵与协议，
预期结果来自模型声明的方程与状态转移，可对外引用为验证资格。
tests 通过的数目不折算为验证条件数；分组与运行方式见
[tests/README.md](tests/README.md)，两级验证目录见 [validation/README.md](validation/README.md)。

`tests/test_*.py` 从公开编译/运行入口检查行为。Rust 模块中的私有测试检查区间、缓存和候选回退；
`transient_*_tests.rs` 由 `transient.rs` 加载，部分测试直接检查接受帧，
`transient_lifecycle_tests.rs` 还检查生产控制器的游标和事件记录。
[run_static_regression.py](tests/run_static_regression.py) 与 [benchmark_events.py](tests/benchmark_events.py)
分别用于静态矩阵回放和局部事件计时，不能代替独立答案或完整瞬态验证。
迁移工具 [migrate.py](src/evas/migrate.py) 与[批量入口](../scripts/recompile_evas_manifests.py)
的规则见[IR 版本与迁移](#ir-v8-migration)，回归见 [test_migrate.py](tests/test_migrate.py)。

审查一个算子时，先确认输入依赖，再选择路径。例如，直接 PWL 的 `idt` 从
[解析公式](docs/math/operators.md#idt)和 `idt.rs` 开始；带反馈的 `idt` 从
[联合方程](docs/math/continuous.md#电压关系与积分反馈)和 `continuous.rs` 开始。
如果改动涉及事件或复位，还需检查共同生命周期与对应的失败后回退测试。
单项测试通过，不能替代这些组合义务。

<details>
<summary>参数、贡献与 IR 的详细接口契约</summary>

## 参数绑定契约

这是当前切片的明确行为约定，不是完整 Verilog-A LRM 合规认证。

1. 所有默认表达式必须通过限定语法检查，数值字面量必须有限，名字必须已声明，
   不能引用节点电压。即使参数被覆盖或没有用于贡献，这些结构检查仍执行。
2. 对每个实例先应用覆盖值，再求其有效依赖图。覆盖值替代对应默认表达式，
   该默认表达式的算术和依赖边不再求值；其他参数读取覆盖后的值。
3. 所有参数（包括未用于贡献的参数）的有效依赖必须无环、可求值且结果有限。
   覆盖值只接受可表示为有限浮点数的 Python int/float，不接受 bool 或字符串。
4. 每个实例独立求值与缓存；源码中的声明先后顺序不影响依赖绑定。

| 默认声明 | 实例覆盖 | 当前契约 |
| --- | --- | --- |
| `a=0; b=1/a` | `a=2` | 接受，`b=0.5`；无覆盖则拒绝除零 |
| `a=1/0` 或 `a=1e308*10` | `a=2` | 接受，未执行被替换的算术；无覆盖则拒绝 |
| `a=b+1; b=a+1` | `a=2` | 接受，`b=3`；无覆盖则拒绝循环 |
| `a=missing`、`a=V(u)`、`a=1e999` | `a=2` | 仍拒绝，覆盖不能隐藏结构错误或非有限字面量 |

## IR 与贡献契约

本地 0.25.0 候选正在集成 IR33（`schema_version` 为33，见[IR 版本与迁移](#ir-v8-migration)）。IR33 保留程序 real 运算、绑定与过程顺序，合同见[ADR-006](docs/development/DECISIONS.md#adr-006)。运行时和完整交付验证尚未完成，最近正式验收仍为本页开头的0.24.1／IR32。模型步长请求 `step_bounds`、连续纯数学函数及原动态契约继续保留。
本地的[历史输入适配](docs/math/operators.md#ir33-源码位置的历史输入候选)保留 Plan 的调用点输入图，
并为受限来源 RN 积分保存独立误差界；一般反馈、源误差管及不可隔离近根仍明确拒绝。
IR23 新增 loop、array_read/array_write 和 checked_integer/checked_index；[执行合同](docs/reference/frontend-admission.md#runtime-event-loops)限定其范围。IR22 引入的 `event_math` 继续保留。每条贡献的 RHS 是带 `op` 标签的表达式，不含“直接写节点”指令。
`affine` 叶子保存有限常数和不重复的节点系数；`add` / `multiply` 含 `left` / `right`；
`power` 含 `base` 和整数 `exponent`；半次幂编译为 `sqrt` 调用点。
`math` 调用点含函数名和输入表达式；认证范围见[纯数学函数](docs/math/operators.md#elementary-functions)。
`event_math` 含 `function`、`args` 和 `origin`，只接受 `sqrt`、`abs`、`min`、`max`。
它在事件执行时计算值及区间，不创建连续历史调用点。`sqrt`、`abs` 各有一个参数，
`min`、`max` 各有两个参数；Rust 校验参数数目、源码位置、实例身份及所有子表达式。
新增节点的执行范围见[事件数学](docs/math/events.md#event-math)。
`select` 含比较关系、两侧表达式、两臂值与源码位置。
Rust 递归检查所有节点、指数和字段，不能绕过前端注入非法表达式。
每条贡献有源码文件、行列、实例以及本地支路身份。

`branch` 保留结构化身份，例如：

```json
{"instance": "dut", "local_positive": "r", "local_negative": "y", "kind": "voltage"}
```

本地端点为非空名称，按字典序排列（允许相等），`0` 表示地。贡献外层的
`positive` / `negative` 是这两个本地端点绑定后的全局节点索引，顺序对应，
RHS 已按规范方向调整符号。`kind` 目前只允许 `voltage`。
归并键是整个支路身份；`origin.instance` 仅保留诊断来源，必须与身份中的实例一致。

Rust 独立检查同一实例内本地端点的绑定一致性、地绑定和规范方向。
同一身份不能绑定不同端点；不同本地贡献支路不能因连接成为同一全局节点对。
这些检查不扩展端口别名、命名支路、电流贡献或更广层次结构的支持范围。

1. 前端按本地节点名固定支路方向；反向贡献同时翻转 RHS 的符号。
2. Rust 按结构化支路身份汇总所有贡献，得到一条支路电压方程。
3. 不同实例即使接到相同外部节点，也保留各自的电压约束。
4. 每次计算由完整方程求解，无旧节点值代入路径，也无自动退回旧 EVAS 的分支。

例如 `V(y,r)<+V(u,r); V(y,r)<+0.125;` 形成
`V(y)-V(r) = V(u)-V(r)+0.125`。
`V(y,r)<+V(u,r)+k*V(y,r);` 形成
`(1-k)*(V(y)-V(r)) = V(u)-V(r)`。
这两种写法使用同一组装与求解入口。

<a id="ir-v8-migration"></a>

### IR 版本与迁移

本地 0.25.0／IR33 候选的 Program 和成功 Response 使用 `schema_version=33`。前端与内核须在完整候选中同步，不能混用当前仍在开发的快照。该版本号不表示已经完成验收；已审 main 和最近正式验收仍为0.24.1／IR32。
旧版本或未知整数版本先于载荷解码返回 `unsupported_ir_version`；版本缺失/错误类型及当前格式错误返回
`invalid_request`。Rust 库构造入口也检查版本。迁移到 IR33 时，旧 IR 1–32 的 JSON 须从原始 VA 与 manifest 重新编译，不能只改版本号。
前端与内核须配套使用。IR24 的源误差项兼容原数值形式，另接受严格的物理曲线对象；
与 IR33 配套的 JSON Program/Response 版本必须为33。以下保留旧版本的语义边界和验收身份。IR32新增显式typed analytic physical source值，合同见[事件手册](docs/math/events.md#ir32-private-candidate-explicit-analytic-source-values)；0.24.1／IR32已完成正式验收，见本页开头。IR31新增直接物理输入的事件整数转换，IR30新增受限source Forcing与独立held Transition。IR29新增受限右移、按位与及纯保持目标，旧载荷须从原VA重编译。IR27新增事件体 typed Add 与常量非零 Remainder。IR26新增实际驱动仿射输入的原生事件 `floor`，IR25及更旧载荷须重新编译。IR25新增原生 `tanh` 数学算子。IR24 扩展源误差描述，IR23 新增有界事件循环和紧凑数组读写；IR22 引入 `event_math`，仅扩展完整 IR 证明隔离的观察事件；
物理联立、初始化和固定 start=0 timer 的数学边界保持。IR21 保留 `step_bounds`，新增变量分母的 `divide` 表达式、顺序初始化和事件输出记录。
`step_bounds` 保存每次 `$bound_step` 的值、激活条件和源码身份。
IR19 引入的纯数学函数格式继续保留；不能只给旧 JSON 改版本号。
IR18 将 `State.initial` 扩为有限常数或明确的 0/1 `select` 比较；
IR21 将初始化扩展到 real/integer 的顺序赋值、默认零值及受限条件；输入仍限 ground/实际 driven 输入。
初始化先于算子历史、守卫日程、首次电压求解和 t=0 事件；详见[初始化契约](docs/math/events.md#input-initialization)。
IR1–25 必须从原始 VA/manifest 重新编译，不原地改写历史 IR 或收据。

仓库冒烟 manifest 的默认范围为 `evas/validation/smoke/`。批量工具读取原 VA 和实例参数，按所用前端的当前schema写入新IR，
保留每项 manifest/source SHA256 及失败诊断；原 IR、历史波形和收据不改写：

```sh
python3 scripts/recompile_evas_manifests.py --output runs/recompile-ir22
python3 scripts/recompile_evas_manifests.py --output runs/recompile-selected evas/validation/smoke/idt.json
```

默认六项当前会有上述三项准入拒绝，命令返回非零并保留另三项成功输出。
需要演示修正后的三条路径时，显式选择版本化 successor：

```sh
python3 scripts/recompile_evas_manifests.py --output runs/recompile-smoke-admission-v1 evas/tests/fixtures/smoke-admission-v1
```

输出目录必须不存在；部分失败返回非零，成功项仍保留。没有原始 VA/manifest 的旧 IR 无法凭改版本号迁移。

更严格的瞬态认证会改变部分接受范围：多项式非方阵在点输入也拒绝；仿射冗余关系必须
在误差映射的参数域上成立，不能只在某个状态点碰巧一致。通用 `real` 状态保留误差区间，交给电压、事件和历史消费者验收；
近零状态不再单独受纯相对预算限制，但后续放大仍可能使请求无法认证。静态 `solve` 仍是局部 Newton 验收，没有同等根前向误差证书。
这些是明确实现边界，详见[精度链与兼容性](../experiments/runs/parallel-gap-integration/REVIEW.md#precision-chain)。
旧归档使用对应提交的前端和内核复现；[历史 v9 迁移说明](https://github.com/BucketSran/vaEVAS/blob/8f9c9ee84593778b1fcb52e264af6d3546466a8b/evas/README.md#ir-v8-migration)保留原身份。

`Program.states/events/operators` 为空时保持静态语义；省略这些字段也只表示空列表，不推断事件。
`state` 表达式保存状态索引，状态含实例身份、名称、类型及初始化常数或上述输入比较；事件为 `trigger/body/origin`。
body 的 `kind=assign` 含 `state/rhs`；`kind=if` 含 `relation/left/right/then_body/else_body/origin`，
relation 为 `lt/le/gt/ge`。无 else 序列化为空 body；未知字段、关系或缺失 body 均拒绝。
trigger 支持 cross、固定及保持状态控制的 timer，以及 cross/timer 混合 OR；格式、身份与事件记录见[事件手册](docs/math/events.md#event-or)。
源码 `timer(start)` 为单次事件，`timer(start,period)` 为周期事件；省略的时间容差采用 EVAS 的
`1e-12 s` 默认值。该值不是与 Spectre 共享的默认设置；规则和拒绝边界见[固定 timer](docs/math/events.md#固定-timer)。
算子按实例/调用点引用，idt 的可空 reset 字段见[算子手册](docs/math/operators.md#idt)。
静态入口拒绝含状态、事件或算子的程序；完整字段定义见[Python IR](src/evas/ir.py)与[Rust IR](rust_core/src/ir.rs)。

</details>

<details>
<summary>Rust 库内性能检查</summary>

## 本地求解性能检查

[static_solver.rs](rust_core/benches/static_solver.rs) 提供 Rust 库内构造解核对和局部计时：

```sh
cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
EVAS_BENCH_CASE=chain-64 EVAS_BENCH_SAMPLES=1024 cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
EVAS_BENCH_CASE=random-1024 cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
EVAS_BENCH_CASE=batch EVAS_BENCH_SAMPLES=4096 cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench static_solver
cargo bench --locked --offline --manifest-path evas/rust_core/Cargo.toml --bench transient_solver
```

基准的准备/首次/重复求解边界、稠密/稀疏分流及局限统一见[数值手册](docs/math/solving.md#稀疏分支与性能边界)。
旧 0.3.1/0.3.2 的重复求解比较保留在[固定历史记录](https://github.com/BucketSran/vaEVAS/blob/8f9c9ee84593778b1fcb52e264af6d3546466a8b/evas/README.md#本地求解性能检查)，
不代表当前版本、首次求解、瞬态或跨后端速度。

</details>

## 保存完整运行结果

使用 `python3 -m evas.results run MANIFEST --kernel PATH --out NEW_DIR` 保存带身份的完整 JSON、CSV 和源码快照。只有最后写入的 `manifest.json` 标记为 `complete` 才表示完整产物；失败保留诊断与部分文件。单位、精度、失败处理和使用示例见[运行产物契约](docs/reference/results.md)。
