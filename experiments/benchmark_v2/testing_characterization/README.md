# 电路测试与表征任务

候选实现可读 Verilog-A 仪表或测试台。固定电路产生实际响应，独立 checker 从保存的波形重算结果。正确测出坏电路也能通过，例如比较器延迟变大、DCO 分频比错误或放大器在公开窗口内没有建立；输出目标常量不能替代观测。

九题已经生成，实际后端校准由统一运行清单调度；生成目录和本地 checker 测试通过均不代表发布资格。真实 POR 完整测试台仍在源电路与数字适配校准阶段，尚未完成。

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

build_tasks.py 生成 Harbor 任务、正确参考、另一种实现和三种行为突变；calibration.json 是调用清单，不含已运行声明。每题公开输入、端口、单位、窗口和容差。060 仅在公开 1fs 边沿不确定度使区间跨过半 LSB 时接受相邻两个完整码，八个位必须同时匹配其中一个码。其余周期严格匹配单码。

本地独立 checker 测试：

    python3 -B -m unittest discover -s experiments/benchmark_v2/testing_characterization -p test_checker.py -v

统一执行依赖父分支的 v2_runtime.py 和 PSF 读取器，不另行实现评分路径。工具链失败应记录为环境错误，不据此给候选零分。实际校准、Harbor reference、模型试跑和审查通过后，才能完成发布资格与证据记录。
