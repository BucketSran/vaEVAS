# 能力比较表

由 `evas/capabilities/catalog.py` 生成。已比较的成绩转录自
[四后端支持表前五节](../../docs/COMPARISON.md#支持矩阵)，不改写该文的历史说明。
没有四后端成绩的节点标为等待跑，不填通过或失败。

成绩沿用[原支持矩阵](../../docs/COMPARISON.md#支持矩阵)的固定模型和配置，
只适用于各行的容差、停止时间及来源版本，不覆盖所有合法写法。
结果来自不同历史版本，不代表当前 main 或 IR33 的一次全量验收。
逐行范围见[验证覆盖](../../validation/paper/COVERAGE.md)，
执行版本与收据见[来源和补充证据](../../docs/development/COMPARISON.md#table-evidence)。

| 能力 | 章节 | 状态 | Spectre | ngspice + OpenVAF-R | Gnucap + modelgen-verilog | EVAS |
| --- | --- | --- | --- | --- | --- | --- |
| [宏与 include](../macro-include/README.md) | 语言 | 已比较 | ✓ Q3 | 层次语法编译失败 | ✓ Q3 | ✓ Q3 |
| [参数](../parameters/README.md) | 语言 | 已比较 | ✓ Q3 | 层次语法编译失败 | ✓ Q3 | ✓ Q3 |
| [条件与逻辑表达式](../conditions/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [case 分支](../case/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [顺序赋值](../sequential-assign/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [用户函数](../user-function/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [静态循环](../static-loop/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | 编译失败 | ✓ Q3 |
| [变量数组：静态下标](../array-static-index/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | 编译失败 | ✓ Q3 |
| [电气向量](../electrical-vector/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | 编译失败 | ✓ Q3 |
| [模块层次](../hierarchy/README.md) | 语言 | 已比较 | ✓ Q3 | 编译失败 | ✓ Q3 | ✓ Q3 |
| [sin](../sin/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [cos](../cos/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [exp](../exp/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [ln](../ln/README.md) | 语言 | 已比较 | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [sqrt](../sqrt/README.md) | 语言 | 已比较 | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [pow：三次幂](../pow-cube/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [pow：半次幂](../pow-half/README.md) | 语言 | 已比较 | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [电压访问与贡献](../voltage-contribution/README.md) | 静态电压传递 | 已比较 | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [静态电压反馈](../static-voltage-feedback/README.md) | 静态电压传递 | 已比较 | ✓ Q3 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [initial_step](../initial-step/README.md) | 阈值、迟滞、启动 | 已比较 | ✓ Q3 | 编译或初始化失败 | 编译失败 | ✓ Q3 |
| [cross：斜坡穿越](../cross/README.md) | 阈值、迟滞、启动 | 已比较 | ✓ Q3 | 初始化失败 | 漏事件 | ✓ Q3 |
| [固定 timer](../timer/README.md) | 延迟、边沿、周期 | 已比较 | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [事件 OR：采样与复位](../event-or/README.md) | 采样、保持、复位 | 已比较 | ✓ Q3 | 编译失败 | 漏事件 | ✓ Q3 |
| [transition：定时非对称沿](../transition/README.md) | 延迟、边沿、周期 | 已比较 | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [固定 absdelay](../absdelay/README.md) | 延迟、边沿、周期 | 已比较 | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [固定 slew](../slew/README.md) | 延迟、边沿、周期 | 已比较 | ✓ Q3 | 编译失败 | ✓ Q3 | ✓ Q3 |
| [idt：非零初值与正负面积](../idt/README.md) | 连续动态与相位 | 已比较 | ✓ Q2 | ✓ Q3 | ✓ Q3 | ✓ Q3 |
| [idtmod：原始相位与环回](../idtmod/README.md) | 连续动态与相位 | 已比较 | 环回边界未验收 | 环回边界未验收 | 编译失败 | ✓ Q3 |
| [ddt：二次时间表达式](../ddt-time/README.md) | 连续动态与相位 | 已比较 | Q1 误差超限 | 误差超限 | ✓ Q2 | ✓ Q3 |
| [ddt：电压斜坡平方](../ddt-input/README.md) | 连续动态与相位 | 已比较 | ✓ Q2 | 误差超限 | ✓ Q2 | ✓ Q3 |
| [一阶 laplace_nd](../laplace-nd/README.md) | 连续动态与相位 | 已比较 | ✓ Q3 | ✓ Q3 | 非零初态错误 | ✓ Q3 |
| [一阶 laplace_np](../laplace-np/README.md) | 连续动态与相位 | 已比较 | ✓ Q3 | 编译失败 | 误差超限 | ✓ Q3 |
| [二阶滤波（内部微分）](../filter-second-order/README.md) | 连续动态与相位 | 已比较 | ✓ Q3 | Q1 误差超限 | 误差超限 | ✓ Q3 |
| [采样保持：定时](../sample-hold-timer/README.md) | 采样、保持、复位 | 已比较 | ✓ Q3 | 初始化失败 | ✓ Q3 | ✓ Q3 |
| [采样保持：阈值](../sample-hold-cross/README.md) | 采样、保持、复位 | 已比较 | ✓ Q3 | 初始化失败 | 漏事件 | ✓ Q3 |
| [采样、复位与输出边沿](../sample-reset-edge/README.md) | 采样、保持、复位 | 已比较 | ✓ Q3 | 编译失败 | 漏事件 | ✓ Q3 |
| [迟滞比较器与边沿](../hysteresis-edge/README.md) | 阈值、迟滞、启动 | 已比较 | ✓ Q3 | 初始化失败 | 误差超限 | ✓ Q3 |
| [定时采样→积分：原模型](../sample-integrate-timer/README.md) | 组合、反馈、实例 | 已比较 | ✓ Q3 | 初始化失败 | 漏定时事件 | ✓ Q3 |
| [采样→积分：停止边界与非线性](../sample-integrate-ordered/README.md) | 组合、反馈、实例 | 已比较 | ✓ Q3 | 初始化失败 | 停止边界未达标 | ✓ Q3 |
| [积分级联与复位](../integrator-cascade-reset/README.md) | 组合、反馈、实例 | 已比较 | 复位误差超限 | 初始化失败 | 误差超限 | ✓ Q3 |
| [非线性输入与滤波直通项](../nonlinear-filter-feedthrough/README.md) | 连续动态与相位 | 已比较 | Q2 误差超限 | Q1/Q2 误差超限 | 误差超限 | ✓ Q3 |
| [滤波与微分：DC 直通项](../filter-ddt-dc/README.md) | 连续动态与相位 | 已比较 | Q3 启动误差超限 | ✓ Q3 | 误差超限 | ✓ Q3 |
| [两个固定延迟的历史](../two-absdelay/README.md) | 延迟、边沿、周期 | 已比较 | ✓ Q3 | 编译失败 | ✓ Q3 | ✓ Q3 |
| [两级 slew 与反向追赶](../two-slew/README.md) | 延迟、边沿、周期 | 已比较 | ✓ Q3 | 编译失败 | ✓ Q3 | ✓ Q3 |
| [中断边沿→积分](../interrupted-edge-integrate/README.md) | 组合、反馈、实例 | 已比较 | ✓ Q3 | 新版验收未跑 | 新版验收未跑 | ✓ Q3 |
| [数组的事件状态更新](../array-event-update/README.md) | 语言 | 已比较 | ✓ Q3 | 初始化失败 | 编译失败 | ✓ Q3 |
| [采样→保持→边沿→滤波](../chain-sample-hold-edge-filter/README.md) | 组合、反馈、实例 | 已比较 | ✓ Q3 | 编译失败 | 事件与输出错误 | ✓ Q3 |
| [滤波→采样保持](../filter-then-sample/README.md) | 组合、反馈、实例 | 已比较 | ✓ Q3 | 编译失败 | 采样历史错误 | ✓ Q3 |
| [电压求解→延迟→采样](../solve-delay-sample/README.md) | 组合、反馈、实例 | 已比较 | ✓ Q3 | 编译失败 | ✓ Q3 | ✓ Q3 |
| [VCO：扫频与原始相位](../vco/README.md) | 连续动态与相位 | 已比较 | 环回边界未验收 | 扫频误差超限 | 编译失败 | ✓ Q3 |
| [实例隔离：双积分器复位](../instance-integrator-reset/README.md) | 组合、反馈、实例 | 已比较 | 复位误差超限 | 编译失败 | 误差超限 | ✓ Q3 |
| [实例隔离：双相位历史](../instance-phase/README.md) | 组合、反馈、实例 | 已比较 | 环回边界未验收 | 编译失败 | 编译失败 | ✓ Q3 |
| [非线性积分与滤波联合反馈](../nonlinear-integral-filter-feedback/README.md) | 组合、反馈、实例 | 已比较 | ✓ Q3 | 误差超限 | ✓ Q3 | ✓ Q3 |
| [事件改变动态：线性反馈](../event-dynamics-linear/README.md) | 组合、反馈、实例 | 已比较 | ✓ Q3 | 初始化失败 | Q1 误差超限 | ✓ Q3 |
| [事件改变动态：Riccati 滤波](../event-dynamics-riccati/README.md) | 组合、反馈、实例 | 已比较 | ✓ Q3 | 初始化失败 | 误差超限 | ✓ Q3 |
| [近邻定时事件：原整链](../near-timer-chain/README.md) | 组合、反馈、实例 | 已比较 | ✓ 1 µV | 初始化失败 | ✓ 1µV | ✓ Q3 |
| [近邻定时事件：相邻浮点采样积分](../near-timer-adjacent/README.md) | 组合、反馈、实例 | 已比较 | 回调同刻 | 初始化失败 | 回调同刻 | ✓ Q3 |
| [include 保护](../include-guard/README.md) | 语言 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [参数范围端点](../parameter-range/README.md) | 语言 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [零次、一次与参数化循环](../loop-bounds/README.md) | 语言 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [数组声明方向](../array-declaration-order/README.md) | 语言 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [供电与参考的统一精度](../supply-reference-precision/README.md) | 参考与供电 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [初始阈值](../initial-threshold/README.md) | 阈值、迟滞、启动 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [above](../above/README.md) | 阈值、迟滞、启动 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [last_crossing](../last-crossing/README.md) | 阈值、迟滞、启动 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [周期修改](../period-update/README.md) | 延迟、边沿、周期 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [旧日程取消](../schedule-cancel/README.md) | 延迟、边沿、周期 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [同刻规则](../same-time-rules/README.md) | 阈值、迟滞、启动 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [VCO 门控](../vco-gated/README.md) | 连续动态与相位 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [VCO 长期相位](../vco-long-phase/README.md) | 连续动态与相位 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [读取相位的 cross](../phase-cross/README.md) | 阈值、迟滞、启动 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [正弦幅相](../sine-response/README.md) | 连续动态与相位 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [共轭极点](../conjugate-poles/README.md) | 连续动态与相位 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [光滑曲线导数](../smooth-derivative/README.md) | 连续动态与相位 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [延迟后限速](../delay-then-slew/README.md) | 延迟、边沿、周期 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [短脉冲](../short-pulse/README.md) | 延迟、边沿、周期 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [更深 slew 级联](../deeper-slew-cascade/README.md) | 延迟、边沿、周期 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
| [ADC 端码、阈值、饱和与读取时序](../adc-codes/README.md) | 采样、保持、复位 | 等待跑 | 等待跑 | 等待跑 | 等待跑 | 等待跑 |
