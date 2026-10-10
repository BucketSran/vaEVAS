# POR真实上电、欠压与恢复闭环测试台

实现 `/work/dut.va`，保留以下公开接口与行为。固定 DUT 源码位于 `/work/public/dut/`，只读。不得驱动观测输入。测量不达标 DUT 时，报告正确结果仍可通过。

模块 `por_bench(avdd,por,power,osc,first_response_us,first_period_us,first_width_us,first_valid,first_ok,recovery_response_us,recovery_period_us,recovery_width_us,recovery_valid,recovery_ok,done)`。只允许驱动avdd及报告输出，por/power/osc均为只读观测。DVDD=1.8V，VBG=1.2V，原POR short-one-shot模式，不包含休眠。事件阈值均0.9V。

启动从0V在2ms线性升到3.3V。首轮实际POR下降后至少100us、且初始斜坡结束后至少100us，才能开始欠压。若首轮缺POR下降，等到3ms超时后继续完成测试。用100us从3.3V降至2V；2V保持至少100us且距实际power下降至少100us，再开始恢复。没有power下降时保持2V到低压平台开始后1ms再恢复。恢复用100us升至3.3V。恢复POR下降后保持100us，再报告；恢复高压平台开始1ms仍缺下降时报告未完成事件。三种等待均使用半开事件窗口：首POR下降必须发生在3ms之前，power下降必须发生在低压平台开始后1ms之前，恢复POR下降必须发生在恢复高压平台开始后1ms之前。窗口内已发生事件时，始终等满事件后100us；只有窗口内缺事件才在截止时刻超时。恰在截止时刻或之后的事件不延长当前状态。该截止规则不改变各轮测量valid和三个指标所需的事件条件。输入状态每1us评估，其他正确实现可更精细评估。实际供电与重建流程相比允许30mV误差以覆盖1us离散调度，禁止省略欠压。

每轮 response_us 严格等于该轮首个实际osc上升至首个POR上升的时间，不能改成从供电门限计时。period_us=(第9个osc上升-第3个osc上升)/6；width_us=实际POR下降-上升。单位都是微秒。两POR事件及至少9个osc事件齐全时valid=1，报告实测值；缺事件则该轮valid及全部三个指标为0。ok=1仅当POR上升发生于第6个osc之后且第7个之前、下降发生于第13个之后且第14个之前，且真实power欠压下降已发生。性质判断基于实际端口，不读取内部计数结束flags。逻辑报告高为1V，低为0。done最终为1，指标误差≤0.15us，输出更新宽限5us。故障DUT正确报告ok=0可以通过。

只读DUT含原晶体管电源检测/滤波/RC振荡器/输出缓冲、忠实原数字状态的可读VA边界。公开健康自测使用原RC；终评使用独立固定的RC负载实例，性质覆盖健康、较慢振荡器、漏掉恢复POR的接口故障及提前释放POR的接口故障，具体终评负载不进入公开包。不得把固定预期时间当实测结果。公开默认台架为 `/work/public/public-default.scs`，只引用原RC健康资产并加载候选dut.va。`python /work/public/materialize_case.py --output visible-cases.json` 可核对独立资产SHA并重建该公开自测的完整材料。

固定后端为 Spectre；语法遵循该后端的 Verilog-A。源码按原字节运行。工具链故障单独诊断，不作为候选零分。公开自测实例位于 `/work/public/cases.json`，固定DUT实现位于 `/work/public/dut/`，可据此运行自己的Spectre自测。终评在提交后使用合同范围内不同的参数、事件及故障实例；终评台架和checker不进入解题材料。判定目标与数值容差以本题公开合同为准。
