# Alexander BBPD 三采样学习说明

2026-10-10。本页用于先理解判相，再讨论 v4-001 的迁移。只查主源与旧题代码，没有编译、仿真、评分或修改正式题目。

## 主源及阅读位置

1. Behzad Razavi, *Challenges in the Design of High-Speed Clock and Data Recovery Circuits*, IEEE Communications Magazine, August 2002, pp.94–101。[作者 UCLA 原文 PDF](https://www.seas.ucla.edu/brweb/papers/Journals/BRAug02.pdf#page=3)。重点是印刷 p.96 的 Fig.3、p.97 的 “The Alexander Phase Detector”。核对了 PDF 图像与正文。它直接给出采样电路和 XOR 判定，但早晚标签存在内部不一致，见下文。
2. Ken Kundert, *Verification of Bit-Error Rate in Bang-Bang Clock and Data Recovery Circuits*。[作者网站 PDF](https://designers-guide.org/analysis/bang-bang.pdf#page=6)。重点是 §4，PDF p.6 的早晚与调速说明；§5，PDF p.7 的电压域/相位域区别；§6.2，PDF pp.9–11 的抖动与亚稳态。首页标有 Version 1c, 4 May 2010，版权/更新说明延续至 2022。本页不从该文示例借用 BER、抖动或带宽数值。

## 固定本页的采样约定

以下是用于推导的约定，不表示时钟已经锁定。以全速、约 50% 占空比的恢复时钟为例，上升沿用于比特中心采样，下降沿用于边界采样。

```text
时间向右
        tA                 tB                 tC
时钟    上升沿             下降沿             下一上升沿
用途    前比特中心         预期位边界         后比特中心
样本    A                  B                  C
        |----约半个 UI-----|----约半个 UI-----|
```

UI 是一个比特周期。A、B、C 都是采样得到的数据位，不是三个端口的瞬时电平。A 和 C 是相邻的中心样本；B 是夹在中间的边界样本。每次在取得 C 后，将同一组三个样本对齐，再比较它们。所谓“中心”“边界”是时钟的目标位置，实际相位误差正是要通过数据判断的量。

主源事实：Razavi Fig.3b/c 用寄存器延迟把三个历史样本对齐，使比较时的三个值属于同一组。按时间顺序，本页 A/B/C 对应其中 S1/S2/S3。该原文的采样器及对齐说明在 p.97。

## 从时间顺序推导早晚

下面推导假设 A 与 C 之间只有一次有效数据跳变，而且 A、C 正确读出跳变两侧的位。这是讨论近锁定理想 NRZ 行为的前提。

定义 `x = A xor B`，`y = B xor C`，并将“时钟早/晚”专指边界采样时刻 tB 相对这次数据跳变的早晚。

| A B C | x y | 时间关系 | 本页判定 |
| --- | --- | --- | --- |
| 0 0 1 或 1 1 0 | 0 1 | B 仍是旧位，数据在 B 之后才跳变 | 时钟早，数据晚 |
| 0 1 1 或 1 0 0 | 1 0 | B 已是新位，数据在 B 之前已跳变 | 时钟晚，数据早 |
| 0 0 0 或 1 1 1 | 0 0 | 三点没有观察到变化 | 不给方向修正 |
| 0 1 0 或 1 0 1 | 1 1 | B 与两侧相反 | 不属于上述单跳变前提 |

这个表是从本页定义直接推导的。它不依赖数据跳变是上升还是下降。例如数据 0→1 在 B 之前发生，得到 011；把电平全部反相成为 1→0，就得到 100，方向相同。

可用两个时间例子自检。令 A/B/C 时刻为 0/0.5/1 UI：跳变在 0.4 UI 时，B 已经读到新位，时钟边界晚；跳变在 0.6 UI 时，B 仍读到旧位，时钟边界早。这些数值只是解释时间顺序的示例，没有给出可捕获相位范围或测量结果。

原文核对限制：Razavi p.97 的项目条目给出 `10 = clock late`、`01 = clock early`，与上表一致。但条目前的叙述反向命名；Fig.3a 的 “Clock early” 实际画出 011，“Clock late” 画出 110。不能把图标签和条目都当成一致证据。本页明确固定“B 相对同一次单跳变”的定义后推导，不推断原文冲突的成因，也不把图中邻近另一跳变混入本页定义。[核对页](https://www.seas.ucla.edu/brweb/papers/Journals/BRAug02.pdf#page=4)

`010/101` 指的是这三个相隔半 UI 的样本，不是三比特序列 010/101。三比特交替数据本身是正常 NRZ。若本页的样本三元组为 010，A 到 B、B 到 C 都有变化；它可能来自窄脉冲、严重失锁、采样错误等，具体原因需要波形。仅有该三元组不能辨认唯一早晚方向。原始 XOR 两路都会为 1；若相减则净值为 0。若新题要求 UP/DOWN 永不同时为高，就必须另写无效样本处理规则，例如要求 A != C 后才允许方向输出。该门控是拟定的模型合同，不应声称所有 Alexander 实现都这样做。

## 判相方向与 UP/DOWN 名字分开

主源事实：Kundert §4 将时钟晚与加速、时钟早与减速联系起来；未观察到数据边沿时没有新的方向信息。[§4](https://designers-guide.org/analysis/bang-bang.pdf#page=6)

工程推断：若 UP 表示正电荷泵电流，滤波器输出增大又令正增益 VCO 加速，那么 `UP = clock_late`，`DOWN = clock_early`。上述采样表可写为 `UP = x && !y`，`DOWN = !x && y`。若后级控制极性不同，映射也要改变。早晚是时间事实，UP/DOWN 是接口及环路符号约定，不能靠名字确定。

三采样给的是方向，不直接给误差大小。不能由某次 011 判出“晚了多少 ps”。输出维持一个判定周期、固定宽度脉冲、或只发一次事件，也属于模型需要明确的输出合同。Kundert 的相位域模型用于平均行为，本页没有用它替代逐边沿电压域采样，也没有对亚稳态、抖动、锁定时间、BER 或环路稳定性作量化结论。

## 旧 v4-001 代码实际做什么

本地证据是 [公开题面](../../reference/v4/release/benchmarkv4-r53/tasks/001-bang-bang-phase-detector/public/instruction.md) 与 [参考代码](../../reference/v4/release/benchmarkv4-r53/tasks/001-bang-bang-phase-detector/evaluator/solution/bbpd_ref.va)。

事实：题面要求在 data 的每次上升/下降跳变时，如果 clk 高且 retimed_data 低就置 UP；如果 clk 低且 retimed_data 高就置 DOWN；其他情况不置位。下一个 clk 跳变清除。参考代码第27–38行照此读取瞬时电平，第41–44行清除；状态只有两路输出，没有存储 A/B/C，也没有由 clk 采样 data 的过程。

| 对比项 | 旧题已写出的行为 | 完整三采样 Alexander 至少要明确 |
| --- | --- | --- |
| 数据获得方式 | data 跳变触发，读 clk 与 retimed_data 当前电平 | clk 在三个有序时刻采样 data |
| retiming | 外部 retimed_data 是输入 | 哪个中心样本、哪个周期、延迟多少、何时有效 |
| 判定依据 | 两个电平条件 | 同一组 A/B/C 的两个 XOR 与有效性 |
| 输出时刻 | 从 data 跳变到下一 clk 跳变 | 完成 C 后何时发布，持续多久，方向如何映射 |

判断：旧题可被称为按既定规则输出修正脉冲的行为模块，但现有公开合同不足以证明它是完整 Alexander 判相器。外部 retimed_data 即使来自某个 retimer，也不能自动补出 B/C 的定义、历史对齐和时序。参考忠实执行旧规则，与“旧规则已具备真实早晚含义”是两个问题。

旧代码两种 data 跳变执行同一条件，而条件没有使用跳变方向。作为对称性检查，将 data 与 retimed_data 的位全部反相、保留跳变时刻和 clk，物理相位误差不变，旧条件却可能由 UP 变成不输出。因此，在没有额外且具体的信号编码/retimer 合同前，不能将这两条条件解释成对数据极性对称的标准 Alexander 早晚逻辑。这是代码逻辑推导，没有运行波形证明。

## 从原理到 r2 题目合同

2026-10-10，用户确认采用完整 Alexander 单模块，采样与历史对齐均在模块内部完成。新方案移除外部 retimed_data，并用相邻上升沿及中间下降沿建立三点历史。它会改变旧任务合同，不是只换两条 if。

[r2 公开规格](../cases/spec-modeling/pll/case-0012-bbpd/instruction.md)提出启动历史无效、完成三点才发布、同方向跨拍保持等规则；[checker 方案](../cases/spec-modeling/pll/case-0012-bbpd/checker-design.md)说明如何从输入独立构造答案，并在采样重合时检查跨周期历史的一致性。方向已认可，新增规则和数值仍待 review。

重合窗口是我们为理想行为题提出的验收约定，不是论文规定的算法或实测 setup/hold 数值。Kundert §6.2 说明小相位差下实际 PD 的亚稳态会影响输出幅度，进一步支持将理想逐拍规则与真实模拟效应分开建模；该文没有证明本题拟定的10 ps窗口。[原文 §6.2](https://designers-guide.org/analysis/bang-bang.pdf#page=10)

本页完成的核对是两份主源阅读、Razavi Fig.3 图像核对、旧题面与参考源码对照，以及逐样本逻辑推导。没有运行模拟器，不能据此宣称新题已实现或验收通过。
