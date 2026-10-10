# 电路测试与表征任务

候选实现可读 Verilog-A 仪表或测试台。固定电路产生实际响应，独立 checker 从保存的波形重算结果。正确测出坏电路也能通过，例如比较器延迟变大、DCO 分频比错误或放大器在公开窗口内没有建立；输出目标常量不能替代观测。

九题公开各3例保留原材料，终评已改成独立实例，待重新校准。POR 原晶体管电路在 ngspice 完成上电、欠压和恢复，数字边界与真实 mixed 源也已实际通过 Spectre 来源校准。完整闭环候选尚未完成实跑验收。目录及本地测试不代表发布资格。

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

POR 使用真实模拟晶体管源和可读数字边界，候选通过观察 POR 完成与 power 欠压事件推进供电。报告 response_us 从各轮首次 osc 上升到 POR 上升计时。周期保留原脚本的第3至第9个振荡器上升平均值。性质判断只观察实际端口，第6/第13个时钟对应断言与释放；不读取内部计数结束标志。健康、慢振荡器、漏恢复脉冲、过早释放和缺首轮下降沿的性质与计量合同公开，具体终评实例隐藏。公开自测仅含原RC健康实例。

prepare_por_source.py 固定原电路与 PDK 版本，build_por_task.py 生成完整任务。两电平转换单元采用同版本官方 CDL 源视图，原抽取 SPICE 的独立单元测试存在悬空连接。prepare_por_spectre.py 只适配数学等值的表达式分隔符和数值后缀，未调整器件阈值。原源17位导出实跑指标见 por_source_ngspice.json，数字实际 Spectre 边界见 por_digital_spectre_r2.json，全量语法等值核验见 por_spectre_translation_r3.json；r3 解析时发现12个电阻公式使用重复引号，r4只删除冗余引号，等值核验见 por_spectre_translation_r4.json。这些证据不替代尚待执行的完整候选校准。

POR 归属 Spectre 扩展。整个 POR 的纯 VA 开源替代仍未校准，不作为本轮真实闭环的替代验收。原模型文件约7.26MB，Agentic 按文件读取完整资产；公开cases用路径和SHA引用独立文件，不复制模型内容。one-shot 适用性仍待实际接口核查。当前适配器把全部公开文件串成一次文本输入，去重后的公开文件共7,450,283字节；模型配置的32k max_tokens是输出上限，不能据此推断输入窗口。须保留全部材料并核对模型输入限制或实际接口拒绝证据，不能按文件体积主观排除。

POR checker 的独立行为测试：

    python3 -B experiments/benchmark_v2/testing_characterization/test_por_checker.py

POR 超时分支按公开半开窗口处理。test_por_timeout.py 对实际发货源码的 timer 条件执行有限控制流回归，覆盖截止前50us、截止时刻、截止之后及缺事件；test_por_checker.py 使用独立端口波形拒绝提前欠压。首轮仅观察[启动,开始欠压)，到欠压边界冻结；边界同刻事件一律排除，欠压后下降沿不能补齐首轮。新增缺首轮下降沿的真实接口故障，保留首POR高电平直到实际power欠压下降。test_por_timeout.py还覆盖同刻cross/timer次序；独立波形回归拒绝将欠压诱发的下降沿计入首轮。该源条件回归不等同VA仿真，完整Spectre校准仍待运行。

r5 处理实际Spectre解析出的重复参数与实例作用域差异。282个重复全局参数等值，保留定义并显式报告warning；原实例几何值展开后，12个顶层和870个模拟子电路表达式由独立AST算术与Decimal逐项核对。模型文件与cells文件SHA未变。核验见 por_spectre_translation_r5.json，实际r5来源仿真已经完成，完整候选仍待执行。

实际 mixed Spectre r5已完成来源校准，原源刺激下两轮各13个振荡器上升沿、POR第6/13沿断言/释放均成立；实测指标与原ngspice源的描述性差值见 por_source_mixed_spectre_r5.json。完整闭环候选尚待25条件校准，来源校准不计模型分数。qualify_por_source.py 从原始PSF及17位ngspice数据重建上述事实，未读取自报指标或内部计数flags。

POR 公开包只含原始MF6健康自测及完整资产引用，materialize_case.py可核对SHA并重建它。独立终评的5个固定负载实例保留在tests，公开包不含参考解、checker或终评参数；公开/终评材料不是同一组。test_por_public.py校验该边界及资产身份。

私有终评同样用tests内路径/SHA引用去重原模型；五种条件保留各自RC与故障参数，模型字节不变。完整任务材料为15,160,726字节，小于16MiB包上限。test_por_public.py通过runtime进程fixture准备全部五条件并逐项核对运行目录原bytes/SHA；此项只检验包适配，不是电路仿真。
