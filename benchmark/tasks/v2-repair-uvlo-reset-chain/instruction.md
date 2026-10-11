# 修复v2-repair-uvlo-reset-chain

修复UVLO、复位释放、使能与有状态下游链。vin上穿0.65V产生pgood，下穿0.55V撤销，迟滞区保持。pgood连续高10ns后resetb释放；任何失效均立即断言并取消旧计时，再次有效必须重计完整10ns。enable为pgood与resetb同时有效。下游activity初始0，enable且resetb有效时每个clk上升沿加0.1V，否则清零；保护撤销时清零。正常供电必须出现下游递增动作。

可修改dut.va顶层连接、uvlo.va、release.va、enable.va、downstream.va及设计参数，或整体重建满足接口与合同的系统。验收电源/时钟激励固定；逻辑高0.9V，传播与平滑须在0.15ns内完成，10ns资格允许0.15ns传播容差。公开参数范围：上阈值0.64..0.66V，下阈值0.54..0.56V，release delay=9.9..10.1ns；即使调参仍须满足公开外部合同。此系统为原创行为控制工程，未声称晶体管POR等价。

输入源码位于 `/work/`。可整体重写指定模块；保持公开端口和行为。验收激励与checker固定。逻辑阈值0.45V，禁止条件也须满足按时启动要求。提交指定文件，不依靠运行外部程序或隐藏终评材料。Spectre是本题固定后端；公开自测执行 `/tests/test.sh`，可自行建立诊断激励。
