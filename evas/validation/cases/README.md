# DVS-2 起步卡的共同 DUT

八个 `dut.va` 对应 [CASE_CARDS.md](../CASE_CARDS.md) 中的八张契约，
由本项目按关系重新编写，未复制第三方示例源码，也未从既有 400 家族挑选。
各文件中的归一化参数已恢复电压和时间单位；四个后端运行相同的 DUT 字节。

**已发现的编码问题：** 冻结的 `d2_v6_01/dut.va` 系数数组缺少 LRM 2.4 要求的前导撇号，不可作为该规范下的有效能力计分项。此处保留原字节以复核历史试点；[标准语法诊断修订](../../../experiments/dvs2-starter-pilot/diagnostics/v6-lrm24.va)和[归因报告](../../../experiments/dvs2-starter-pilot/DIAGNOSIS.md)单独保存，下一次正式冻结必须采用修订并重新绑定结果。

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

刺激、参数、网表外壳和独立参考在
[suite.py](../../../experiments/dvs2-starter-pilot/suite.py) 中生成。
运行协议和实际结果分别见
[README](../../../experiments/dvs2-starter-pilot/README.md) 与
[RESULTS](../../../experiments/dvs2-starter-pilot/RESULTS.md)。

每个 DUT 在 Spectre 的两档配置中均成功执行；这不等于全语言合法性认证，
也不保证其他前端接受同一编码。原始拒绝与错误已保留，不以改写后的模型覆盖失败。
15 个条件只覆盖起步卡，正式 DVS-2 分母仍未冻结。

## 2026-09-28 Spectre 扩展验证

新一批输入由 [run_suite.py](../../../experiments/dvs2-spectre-validation/run_suite.py)
固定为 31 个当前条件、两档设置。源码与历史 v1 分开保存：

| 源码 | 对应条件 | 说明 |
| --- | --- | --- |
| [d2_v6_01_standard](d2_v6_01_standard/dut.va) | v6-standard、C2 滤波级 | 标准数组修订；不改冻结 v1 |
| [n_v3_02](n_v3_02/dut.va) | E1 的 3 条件 | 分别观察上穿、下穿计数 |
| [n_v4_02](n_v4_02/dut.va) | E2 的 3 条件、C1 的 3 条件、C2 采样级 | 显式初始化、复位优先的参数化采样器；状态属于各实例 |
| [n_v6_02](n_v6_02/dut.va) | D1 的 2 条件 | 非零初值积分、持续复位与释放 |
| [n_v6_03](n_v6_03/dut.va) | D2 的 2 条件 | 累积相位、包裹相位及正弦输出 |
| [n_v1_02](n_v1_02/dut.va) | S1 的 2 条件 | 两个输入与三个贡献相加 |

C1 由两个采样器实例构成，C2 由低通与采样器两个模块构成；构建器按
`source_cards` 打包源文件并保存完整网表。卡数、源文件数和条件数不是同一计数。
执行证据和判定边界见 [本轮实验](../../../experiments/dvs2-spectre-validation/README.md)。

随后已用相同 DUT 字节完成 [四后端补测](../../../experiments/dvs2-four-backend-validation/README.md)，
形成 [31 条件完整对照表](../../../experiments/dvs2-four-backend-validation/results/MATRIX.md)。
Gnucap 的外壳采用预先固定的具名零伏参考与 `short=1e-9`，全部 31 条件按此设置重跑；
编译和执行失败仍计入对应条件，完整观察资格未因此取得。

## S1 审阅补充

[n_v1_02_reordered/dut.va](n_v1_02_reordered/dut.va)仅反转 S1 三条贡献的顺序。
它对应单独登记的 `s1-default-reordered`；其他输入与默认条件一致。
[审阅卡](../NEXT_CASE_CARDS.md#s1-review)给出独立答案、错误对照与运行入口。
本地检查器校准不等于后端通过；此条件尚未仿真，不进入原 31 条矩阵。
