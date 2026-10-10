# Tiny Tapeout ADPLL：数字架构与 fine TDC 方法来源

固定来源：[SriKondapaturi/tt-um-govardhana-adpll](https://github.com/SriKondapaturi/tt-um-govardhana-adpll/tree/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2)。
版本：`c0a03ef603bd9d40ce61e34262d22d7f7e5676e2`。
作者：Govardhana (Sai) Kondapaturi。核查日期：2026-10-10。
许可：[Apache-2.0 LICENSE](https://github.com/SriKondapaturi/tt-um-govardhana-adpll/blob/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2/LICENSE)。

此来源提供 Verilog 数字闭环、行为 DCO 和 SKY130 标准单元环振结构。它不是现成 VA 电压域系统。下面为候选设计保留来源事实、静态风险和拟改编要求，没有建立正式评分任务或运行仿真。

## 实读范围与许可

本轮读取固定版本 `src/project.v`、`src/dco.v`、`test/test.py`、README 和 LICENSE 全文。通过 GitHub API 核对完整递归文件树，返回 `truncated=false`；`src/` 只有 config.json、dco.v、project.v，许可类路径只有 LICENSE，未发现 NOTICE。没有读取版图/波形图片、全部 CI 日志、PDK 文件或网表，也没有复现作者结果。[固定文件树](https://api.github.com/repos/SriKondapaturi/tt-um-govardhana-adpll/git/trees/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2?recursive=1)

Apache-2.0 §4 要求随分发提供许可证、标明修改并保留相关版权及归属声明；如果所用资产另带 NOTICE，须按该条保留。仓库许可不自动证明外部 PDK、工具或其他第三方资产具有相同许可。此页只链接原材料，没有复制第三方源码。

README 将项目描述为 SKY26c，并写硅片预计 2027 年 5 月返回；频率与锁定时间来自作者报告，不能写成已测硅片结果。README 称未做门级仿真，但同版本测试文件包含门级 smoke 分支。是否运行过该分支未核查，应分别记录文档描述、测试能力和实际执行证据。[README](https://github.com/SriKondapaturi/tt-um-govardhana-adpll/blob/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2/README.md)

## 原闭环与 DCO 码频规则

[project.v](https://github.com/SriKondapaturi/tt-um-govardhana-adpll/blob/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2/src/project.v#L63) 中真实反馈来自 `dco_clk`。DCO 域的 12 位 Gray 计数经两级同步进入参考域，每 16 个参考周期求一次模 4096 计数差，再与 `N*16` 比较，PI 输出饱和到 0..1023。配置支持 N=1..63，零表示 N=4。外露时钟是 DCO/2，不能直接以它和 N 比较。

[dco.v 仿真分支](https://github.com/SriKondapaturi/tt-um-govardhana-adpll/blob/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2/src/dco.v#L68) 的规则是：

```text
k = tune[9:6], k ∈ {0,...,15}
tune_q = 64*k
T_ns = 60 - 0.04*tune_q = 60 - 2.56*k
f_MHz = 1000/T_ns
```

由代码计算，恒码频率约 16.667..46.296 MHz。周期随码线性变化，频率并不随码线性变化；低 6 位没有细调作用。10 MHz 参考下，接口允许的全部 N 不能都在该仿真频率范围内达到。`en` 为低时清输出；高时按当前半周期延迟翻转。已经启动的延迟不会因换码或关使能自动取消，所以这一数字过程也不能直接当“连续相位 VA”合同。

[结构分支](https://github.com/SriKondapaturi/tt-um-govardhana-adpll/blob/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2/src/dco.v#L90) 使用 NAND、32 个 inverter、16 tap mux、反馈 inverter 和输出 buffer；tap k 接 `chain[2*k+1]`。源码的历史修复注释记载旧 16 级链造成高 tap 越界，现在链长度由 tap 数决定。固定版本不能继续描述为仍有该越界错误。

静态推断：高码选择更长结构环路，通常使频率下降，而 SIM 高码缩短周期使频率上升。确切结构码频曲线仍依赖 cell delay、PVT、负载和 mux，当前没有测量证明两分支的单调方向或数值对齐。出题应独立规定控制极性，不把 SIM 公式视为器件表征数据。

## 原验收与不能省略的问题

[test.py](https://github.com/SriKondapaturi/tt-um-govardhana-adpll/blob/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2/test/test.py) 的 RTL 路径使用 10 MHz 参考，验 N=4 后 N=3；从 DCO/2 的上升沿还原 DCO 频率，容差为 2 MHz。门级路径仅检查输出翻转，没有验闭环频率或相位。此次只是读测试，没有运行。

[lock detector](https://github.com/SriKondapaturi/tt-um-govardhana-adpll/blob/c0a03ef603bd9d40ce61e34262d22d7f7e5676e2/src/project.v#L198) 实际检查四窗口有符号误差之和的绝对值是否不大于 8，连续八组后置 lock；正负误差能抵消。这不是四个绝对误差的均值，也不是绝对相位锁定证明。配置改变没有立即清 lock，旧资格可能保留到后续组判定。原 retune 测试不要求先看到 lock 撤销，不能借此证明新目标已重新获得资格。

此前研究的另一来源 [anlit75/ADPLL 的固定顶层](https://github.com/anlit75/ADPLL/blob/57376b014d06dd0832eb8f17906d681f09c9a097/05_ADPLL/ADPLL.v#L70) 把 divider 的 `.clk` 接 `REF_CLK`，PFD 的 FB 却接该 divider 输出，未由 `OUT_CLK` 闭合反馈。本轮全文重读该顶层确认连接，未重读其全部部件或执行测试。它是另一个 Verilog/HSPICE 工程，不能与 Tiny Tapeout 混称同一故障。健康旧闭环必须在出题前另行建立；修该错线是基线准备，不能冒充 fine TDC 扩展，也不派生本轮未授权的优化任务。

## fine TDC 的方法来源

来源为 DVCon 官方 [An Effective Design and Verification Methodology for Digital PLL](https://dvcon-proceedings.org/wp-content/uploads/an-effective-design-and-verification-methodology-for-digital-pll.pdf)，Biju Viswanathan 等。本轮阅读网页提取文本全文，工具报告 8 页，但文本页码只覆盖 1..7；未渲染图像核对图中细节，未下载并固定 PDF 哈希，也未确认出版年份。重点读取 §III A–E、图 1–5 周围说明及参考文献；没有查到公开完整源码或独立宽松许可。

§III B 用两条延迟链分别处理 lead/lag，再将温度计码转成二进制。§III C 区分 coarse、fine、fractional 搜索和 phase tracking；这里的 fine code search 与随后 TDC 相位跟踪不是同一个阶段。§III E 说初期使用 oscillator Verilog/Verilog-A 模型、后期以 SPICE netlist 做 co-simulation。论文只提供方法与结构，不能据此声称已获得作者 VA 系统或可复验环境。文中 DCO 码增大使频率下降，与 Tiny Tapeout SIM 极性不同。

## 两个候选的拟改编边界

“固定架构中补 DCO”属于按规格构建模型。应由出题者先提供健康闭环和固定的计数、PI、端口职责，求解者补空壳 VA DCO。题面另定电压阈值、码频函数、使能/复位、输出边沿与换码时的相位协议。原 16 档公式可以成为明示行为规格，不能伪称硅片拟合数据；若要求全 10 位连续细调，就须标成新的规格。独立验收建议对恒码测周期，对换码积分频率测相位，并从外部输出验闭环目标与重锁。

“健康旧闭环接入 fine TDC”属于扩展与集成。Tiny Tapeout 的窗口频率计数不能直接提供参考与 N 分频反馈的细相差。候选仍需补以下合同及配套环境：

- 从 DCO 建立明确定义初相位的 N 分频反馈，确定相位边沿配对和 PFD/lead-lag 极性。
- 定义 TDC 分辨率、量程、符号、饱和、同刻边沿、缺边沿及更新延迟；延迟链方法仅供来源参考。
- 定义 coarse 到 tracking 的资格条件、模式切换、retune/reset 撤销资格，并明示允许修改的 controller/filter 范围。
- 提供能实际执行 fine 校正的 DCO 或受控 dithering 路径。原低 6 位是保留位，仅新增更细的测量器不能保证相位指标改善；是否引入 DSM 仍待选题决定。
- 定义关闭 fine 模式时保留的旧行为，并用独立的输出/反馈边沿检查频率、相差和扰动响应，同时核对内部 TDC 码与控制码，避免仅凭 lock 判分。

这些是任务设计建议，不是原作者接口。健康 VA 基线、可达条件、数值容差、正式验收后端和 checker 校准均尚缺。后端按逐题合同与实际支持/校准证据决定，来源论文采用 co-simulation 不替本题指定后端。已有研究的背景见 [规格建模](../../research/spec-modeling.md) 与 [扩展集成](../../research/extension-integration.md)。
