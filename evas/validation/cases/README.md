# 共同 Verilog-A 测试模型

本目录保存独立验证使用的 DUT。模型从明确的电压关系与状态转移构造，
同一条件的各后端使用相同源码；参数、刺激、实例连接和观察要求在案例卡及输入构建器中固定。
**一个源文件可以参与多个条件，一个条件也可以包含多个模块。**

当前结果与判定边界见[验证集入口](../README.md)。只运行 `dut.va` 本身不能复现一个条件，
还需要对应的刺激、参数、连接和检查器。

## 原 31 条件的模型

原矩阵由 14 个未改动的 v1 条件、1 个标准低通修订和 16 个补充条件组成。
[起步案例卡](../CASE_CARDS.md)与[补充案例卡](../NEXT_CASE_CARDS.md)定义独立答案；
[run_suite.py](../../../experiments/dvs2-spectre-validation/run_suite.py)生成冻结输入与网表外壳。

以下源码补充或修订了历史起步模型：

| 源码 | 对应条件 | 说明 |
| --- | --- | --- |
| [d2_v6_01_standard](d2_v6_01_standard/dut.va) | v6-standard、C2 滤波级 | 标准数组修订；不改冻结 v1 |
| [n_v3_02](n_v3_02/dut.va) | E1 的 3 条件 | 分别观察上穿、下穿计数 |
| [n_v4_02](n_v4_02/dut.va) | E2 的 3 条件、C1 的 3 条件、C2 采样级 | 显式初始化、复位优先的参数化采样器；状态属于各实例 |
| [n_v6_02](n_v6_02/dut.va) | D1 的 2 条件 | 非零初值积分、持续复位与释放 |
| [n_v6_03](n_v6_03/dut.va) | D2 的 2 条件 | 累积相位、包裹相位及正弦输出 |
| [n_v1_02](n_v1_02/dut.va) | S1 的 2 条件 | 两个输入与三个贡献相加 |

C1 使用两个采样器实例，C2 使用低通与采样器两个模块；构建器按 `source_cards` 打包完整源码。
新版 EVAS 的验证与历史四后端对照分开记录，分别由[当前证据](../README.md#latest-evas-checkpoint)
和[历史矩阵](../../../experiments/dvs2-four-backend-validation/results/MATRIX.md)进入。

## 历史起步模型

八个原始 `dut.va` 对应 v1 的八张案例卡、15 个条件；各文件的参数已恢复电压和时间单位。
刺激与参数展开由 [suite.py](../../../experiments/dvs2-starter-pilot/suite.py)生成。

| 目录 | 行为 | 试点条件数 |
| --- | --- | ---: |
| [d2_v1_01](d2_v1_01/dut.va) | 仿射增益、失调、上下限幅 | 1 |
| [d2_v2_01](d2_v2_01/dut.va) | 变化参考、差分输入、供电相关共模 | 4 |
| [d2_v3_01](d2_v3_01/dut.va) | 初始化、双阈值迟滞、连续电压贡献 | 1 |
| [d2_v4_01](d2_v4_01/dut.va) | 上升沿采样、保持、异步复位与复位优先 | 2 |
| [d2_v5_01](d2_v5_01/dut.va) | 周期 timer、输出延迟及不对称边沿 | 1 |
| [d2_v6_01](d2_v6_01/dut.va) | 一阶低通的 laplace_nd 编码 | 1 |
| [d2_v7_01](d2_v7_01/dut.va) | 两实例的唯一线性隐式关系 | 3 |
| [d2_v7_02](d2_v7_02/dut.va) | 单调三次隐式关系，两组参数 | 2 |

**低通的历史编码问题：** `d2_v6_01/dut.va` 的数组缺少 LRM 2.4 要求的前导撇号。
该文件保留原字节以核对 v1 历史；[语法诊断修订](../../../experiments/dvs2-starter-pilot/diagnostics/v6-lrm24.va)
和[归因报告](../../../experiments/dvs2-starter-pilot/DIAGNOSIS.md)单独保存。
原 31 条件采用 `d2_v6_01_standard`，没有覆盖旧输入。

历史试点的协议与结果见[试点入口](../../../experiments/dvs2-starter-pilot/README.md)。
后端成功执行不等于语言合法性认证，改写后的模型也不能替代旧失败记录。

## 贡献顺序变体

[n_v1_02_reordered/dut.va](n_v1_02_reordered/dut.va) 只反转 S1 三条贡献的顺序，
用于检查贡献相加是否与独立语句的顺序无关。它单独登记为 `s1-default-reordered`；
输入与默认条件相同，数学答案和错误对照见 [S1 审阅卡](../NEXT_CASE_CARDS.md#s1-review)。

该条件尚未执行后端，不进入原 31 条矩阵。增加源码或检查器校准，也不能直接继承原条件的通过结果。
