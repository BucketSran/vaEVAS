# 四后端支持对比

按语言、算子、简单组合、完整信号链、复杂交互排列。每行对应[累计清单](../validation/paper/COVERAGE.md#layer-directory)中的固定能力 ID。
结果累积自不同版本，**不代表当前 main 的完整支持范围**。新 44 组 EVAS 为 [#162 候选](https://github.com/BucketSran/vaEVAS/pull/162) `519d5e28`，
本次仅合入文档，候选实现未随之合入。旧精度集为 `826fefb1`，其他版本见[来源表](../validation/paper/COVERAGE.md#先找到各批的原始成绩)。

<a id="table-design"></a>

**部分 · Q3**：已有固定子范围完整通过 Q3，整行仍有未通过或未完成的必测范围。Q2、旧电压预算同理。
**✓** 留给整行必测范围完成验收；本次仅整理已有证据，没有新增整行通过。
**未通过**：已测配置存在失败，尚无可列的合格子范围。**待核**：已有资料不足以完整判定。
**未测**：没有对应执行。**规则待定**：须先确认探针的验收答案。具体用例、失败与缺证均在行名链接中。

精度是验收上限，不是实测最大误差。1 V 刻度下 Q1、Q2、Q3 分别为 **10.1 µV、1.01 µV、101 nV**；
1 mV 小信号 Q3 为 **1.1 nV**。时间、状态和关键边界另须达标。配置与预算见[评测标准](COMPARISON-METHODOLOGY.md)。

<a id="支持矩阵"></a><a id="precision-binding-results"></a><a id="新精度测试"></a><a id="precision-breadth-results"></a>

## 1. 语言与静态电压关系

| 能力 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |
| --- | --- | --- | --- | --- |
| [宏与 include](../validation/paper/COVERAGE.md#l1-01) | 部分 · Q3 | 部分 · 1 mV | 未通过 | 部分 · Q3 |
| [参数](../validation/paper/COVERAGE.md#l1-02) | 部分 · Q3 | 部分 · 1 mV | 部分 · 1 mV | 部分 · Q3 |
| [条件与逻辑表达式](../validation/paper/COVERAGE.md#l1-03) | 部分 · Q3 | 待核 | 待核 | 部分 · Q3 |
| [case 分支](../validation/paper/COVERAGE.md#l1-04) | 待核 | 待核 | 待核 | 待核 |
| [顺序赋值](../validation/paper/COVERAGE.md#l1-05) | 部分 · Q3 | 待核 | 待核 | 部分 · Q3 |
| [用户函数](../validation/paper/COVERAGE.md#l1-06) | 部分 · Q3 | 待核 | 待核 | 部分 · Q3 |
| [静态循环](../validation/paper/COVERAGE.md#l1-07) | 部分 · Q3 | 待核 | 未通过 | 部分 · Q3 |
| [变量数组](../validation/paper/COVERAGE.md#l1-08) | 部分 · Q3 | 待核 | 未通过 | 部分 · Q3 |
| [电气向量](../validation/paper/COVERAGE.md#l1-09) | 部分 · Q3 | 部分 · 1 mV | 未通过 | 部分 · Q3 |
| [模块层次](../validation/paper/COVERAGE.md#l1-10) | 部分 · Q3 | 未通过 | 部分 · 1 mV | 部分 · Q3 |
| [sin](../validation/paper/COVERAGE.md#l1-11) | 未测 | 未测 | 未测 | 未测 |
| [cos](../validation/paper/COVERAGE.md#l1-12) | 未测 | 未测 | 未测 | 未测 |
| [exp](../validation/paper/COVERAGE.md#l1-13) | 未测 | 未测 | 未测 | 未测 |
| [ln](../validation/paper/COVERAGE.md#l1-14) | 未测 | 未测 | 未测 | 未测 |
| [sqrt](../validation/paper/COVERAGE.md#l1-15) | 未测 | 未测 | 未测 | 未测 |
| [pow](../validation/paper/COVERAGE.md#l1-16) | 未测 | 未测 | 未测 | 未测 |
| [电压访问与贡献](../validation/paper/COVERAGE.md#l1-17) | 部分 · Q3 | 部分 · 1 mV | 部分 · 1 mV | 部分 · Q3 |
| [静态电压反馈](../validation/paper/COVERAGE.md#l1-18) | 部分 · Q3 | 部分 · 1 mV | 部分 · 1 mV | 部分 · Q3 |

## 2. 单个动态算子与基本事件

| 能力 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |
| --- | --- | --- | --- | --- |
| [initial_step](../validation/paper/COVERAGE.md#l2-01) | 待核 | 未通过 | 未通过 | 待核 |
| [输入驱动的 cross](../validation/paper/COVERAGE.md#l2-02) | 部分 · Q3 | 未通过 | 未通过 | 部分 · 2.01 µV、12 nV |
| [固定 timer](../validation/paper/COVERAGE.md#l2-03) | 部分 · Q3 | 未通过 | 部分 · Q3 | 部分 · Q3 |
| [动态 timer](../validation/paper/COVERAGE.md#l2-04) | 规则待定 | 规则待定 | 规则待定 | 规则待定 |
| [事件 OR](../validation/paper/COVERAGE.md#l2-05) | 待核 | 未通过 | 待核 | 待核 |
| [transition](../validation/paper/COVERAGE.md#l2-06) | 待核 | 未通过 | 未通过 | 部分 · Q3 |
| [固定 absdelay](../validation/paper/COVERAGE.md#l2-07) | 部分 · Q3 | 未通过 | 部分 · 1 mV | 部分 · Q3 |
| [固定 slew](../validation/paper/COVERAGE.md#l2-08) | 部分 · Q3 | 未通过 | 部分 · 1 mV | 部分 · Q3 |
| [idt](../validation/paper/COVERAGE.md#l2-09) | 部分 · Q3 | 未通过 | 未通过 | 部分 · Q3 |
| [idtmod](../validation/paper/COVERAGE.md#l2-10) | 待核 | 未通过 | 未通过 | 待核 |
| [ddt](../validation/paper/COVERAGE.md#l2-11) | 待核 | 待核 | 待核 | 待核 |
| [一阶 laplace_nd](../validation/paper/COVERAGE.md#l2-12) | 部分 · Q3 | 部分 · Q3 | 部分 · Q3 | 部分 · Q3 |
| [一阶 laplace_np](../validation/paper/COVERAGE.md#l2-13) | 部分 · 1 mV | 未通过 | 未通过 | 部分 · Q3 |
| [高阶连续滤波](../validation/paper/COVERAGE.md#l2-14) | 待核 | 未通过 | 未通过 | 部分 · Q3 |

## 3. 简单组合

| 能力 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |
| --- | --- | --- | --- | --- |
| [采样保持](../validation/paper/COVERAGE.md#l3-01) | 部分 · Q3 | 未通过 | 部分 · Q3 | 部分 · Q3 |
| [采样、复位与输出边沿](../validation/paper/COVERAGE.md#l3-02) | 待核 | 未通过 | 待核 | 待核 |
| [迟滞比较器与边沿](../validation/paper/COVERAGE.md#l3-03) | 待核 | 未通过 | 未通过 | 待核 |
| [采样保持后积分](../validation/paper/COVERAGE.md#l3-04) | 未通过 | 未通过 | 未通过 | 部分 · 100 µV |
| [积分级联与复位](../validation/paper/COVERAGE.md#l3-05) | 待核 | 未通过 | 未通过 | 未通过 |
| [非线性输入与滤波直通项](../validation/paper/COVERAGE.md#l3-06) | 部分 · 1 µV | 未通过 | 未通过 | 部分 · Q2 |
| [滤波与微分组合](../validation/paper/COVERAGE.md#l3-07) | 待核 | 未通过 | 未通过 | 部分 · Q3 |
| [延迟级联](../validation/paper/COVERAGE.md#l3-08) | 待核 | 未通过 | 待核 | 部分 · Q3 |
| [限速及延迟限速级联](../validation/paper/COVERAGE.md#l3-09) | 部分 · 1 µV | 未通过 | 待核 | 部分 · Q3 |
| [中断边沿后积分](../validation/paper/COVERAGE.md#l3-10) | 规则待定 | 规则待定 | 规则待定 | 规则待定 |
| [数组的事件状态更新](../validation/paper/COVERAGE.md#l3-11) | 待核 | 未通过 | 未通过 | 待核 |

## 4. 完整工程信号链

| 能力 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |
| --- | --- | --- | --- | --- |
| [采样→保持→边沿→滤波](../validation/paper/COVERAGE.md#l4-01) | 部分 · 100 µV | 未测 | 未测 | 部分 · 100 µV |
| [滤波→采样保持](../validation/paper/COVERAGE.md#l4-02) | 待核 | 待核 | 待核 | 待核 |
| [电压求解→延迟→采样](../validation/paper/COVERAGE.md#l4-03) | 待核 | 未通过 | 待核 | 部分 · Q3 |
| [VCO 与相位消费者](../validation/paper/COVERAGE.md#l4-04) | 待核 | 未通过 | 未通过 | 待核 |
| [量化器与 ADC 码流](../validation/paper/COVERAGE.md#l4-05) | 未测 | 未测 | 未测 | 未测 |

## 5. 复杂交互

| 能力 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |
| --- | --- | --- | --- | --- |
| [多通道与实例隔离](../validation/paper/COVERAGE.md#l5-01) | 部分 · 100 µV | 未通过 | 未通过 | 部分 · Q3 |
| [连续动态联合反馈](../validation/paper/COVERAGE.md#l5-02) | 部分 · Q3 | 部分 · Q3 | 部分 · Q3 | 部分 · Q3 |
| [事件改变连续动态](../validation/paper/COVERAGE.md#l5-03) | 部分 · 0.1 µV／1 mV | 未通过 | 未通过 | 部分 · Q2 |
| [近邻事件与下游历史](../validation/paper/COVERAGE.md#l5-04) | 部分 · 1 µV | 未通过 | 待核 | 部分 · 1 µV |
| [同刻事件](../validation/paper/COVERAGE.md#l5-05) | 规则待定 | 规则待定 | 规则待定 | 规则待定 |
| [内部状态触发反馈事件](../validation/paper/COVERAGE.md#l5-06) | 规则待定 | 规则待定 | 规则待定 | 规则待定 |
| [隐式连续关系与复位](../validation/paper/COVERAGE.md#l5-07) | 规则待定 | 规则待定 | 规则待定 | 规则待定 |

<a id="historical-results"></a><a id="strobe-与连续历史组合"></a><a id="两级固定-slew-组合"></a><a id="非线性输入的滤波直接通路"></a>
<a id="accuracy-controls"></a><a id="acceptance-budgets"></a><a id="measured-settings"></a>
<a id="current-failure-causes"></a><a id="evas-precision-recovery"></a><a id="precision-v2-results"></a>

[全部历史条件与新增 44 组](../validation/paper/COVERAGE.md#legacy-31) ·
[待补测试和证据](../validation/paper/COVERAGE.md#remaining-coverage) ·
[逐档原成绩](../../experiments/backends/support/README.md#breadth-tier-results)

原八条件的[配置与成绩](https://github.com/BucketSran/vaEVAS/blob/814da00daf2f0bea1555fffe923f5b6abd78b6bf/evas/docs/COMPARISON.md#原八条件的配置身份)保留在固定历史版本；
当前[精度控制与配置规则](COMPARISON-METHODOLOGY.md#backend-controls)在评测标准中维护。
