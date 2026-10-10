# 电路测试与表征任务

候选实现可读 Verilog-A 仪表或测试台。固定电路产生实际响应，独立 checker 从保存的波形重算结果。正确测出坏电路也能通过，例如比较器延迟变大、DCO 分频比错误或放大器在公开窗口内没有建立；输出目标常量不能替代观测。

九个仪表任务已冻结供实际校准与独立审查。POR 完整测试台已有草稿；原晶体管电路在 ngspice 完成上电、欠压和恢复，数字边界也已实际通过 Spectre 校准。完整混合环境仍在排查 SPICE 方言兼容，闭环候选尚未完成实跑验收。目录及本地测试不代表发布资格。

| 任务 | 来源 | 实际测量 |
| --- | --- | --- |
| v2-test-hysteresis | v4 111 | 双向输出边沿处的输入、带符号宽度、每轮有效性 |
| v2-test-comparator-delay | v4 170 | 过驱动 mV、首个决策延迟 ps、极性、缺决策 |
| v2-test-duty-cycle | v4 060 | 完整上升—下降—上升周期及八位占空比 |
| v2-test-sampled-rms | v4 074 | 有符号差分样本的四点 RMS、复位与禁用 |
| v2-test-online-gain | v4 093、038 | 真实放大器的输入输出跨度比、重新开窗 |
| v2-test-clock-frequency | v4 362 | 实际 DCO 与分频周期，不读取目标频率码 |
| v2-test-offset-search | v4 109 | 比较器 ready 响应推进搜索、缺响应超时 |
| v2-test-time-protocol | v4 346 | 边沿计数、重武装、锁存、复位、溢出 |
| v2-test-gain-settling | case0018、v4 038、370 | 同输入的静态增益与动态输出最后超差后的有限建立 |
| v2-test-por-sequence，待校准 | case0001、sky130-ajc-por | 实际供电闭环、两轮振荡器起点响应、周期、脉宽及故障判断 |

build_tasks.py 生成 Harbor 任务、正确参考、另一种实现和三种行为突变；calibration.json 是调用清单，不含已运行声明。每题公开输入、端口、单位、窗口和容差。060 仅在公开 1fs 边沿不确定度使区间跨过半 LSB 时接受相邻两个完整码，八个位必须同时匹配其中一个码。其余周期严格匹配单码。

本地独立 checker 测试：

    python3 -B -m unittest discover -s experiments/benchmark_v2/testing_characterization -p test_checker.py -v

统一执行依赖父分支的 v2_runtime.py 和 PSF 读取器，不另行实现评分路径。工具链失败应记录为环境错误，不据此给候选零分。实际校准、Harbor reference、模型试跑和审查通过后，才能完成发布资格与证据记录。

POR 使用真实模拟晶体管源和可读数字边界，候选通过观察 POR 完成与 power 欠压事件推进供电。报告 response_us 从各轮首次 osc 上升到 POR 上升计时。周期保留原脚本的第3至第9个振荡器上升平均值。性质判断只观察实际端口，第6/第13个时钟对应断言与释放；不读取内部计数结束标志。正常、慢振荡器、漏恢复脉冲和过早释放都属于公开条件。

prepare_por_source.py 固定原电路与 PDK 版本，build_por_task.py 生成完整任务。两电平转换单元采用同版本官方 CDL 源视图，原抽取 SPICE 的独立单元测试存在悬空连接。prepare_por_spectre.py 只适配数学等值的表达式分隔符和数值后缀，未调整器件阈值。原源17位导出实跑指标见 por_source_ngspice.json，数字实际 Spectre 边界见 por_digital_spectre_r2.json，全量语法等值核验见 por_spectre_translation_r3.json；r3 解析时发现12个电阻公式使用重复引号，r4只删除冗余引号，等值核验见 por_spectre_translation_r4.json。这些证据不替代尚待执行的完整候选校准。

POR 归属 Spectre 扩展。整个 POR 的纯 VA 开源替代仍未校准，不作为本轮真实闭环的替代验收。原模型公开材料约6.9MB，Agentic 能完整读取文件；one-shot 只有能原样提供同一完整材料时才是等价对照，否则记录不适用，不删减真实电路来适配上下文。

POR checker 的独立行为测试：

    python3 -B experiments/benchmark_v2/testing_characterization/test_por_checker.py

POR 超时分支按公开半开窗口处理。test_por_timeout.py 对实际发货源码的 timer 条件执行有限控制流回归，覆盖截止前50us、截止时刻、截止之后及缺事件；test_por_checker.py 使用独立端口波形拒绝提前欠压。该源条件回归不等同VA仿真，完整Spectre校准仍待运行。
