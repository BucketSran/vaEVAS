# Analog Design Bench：LDO 启动测量

固定来源：[sky130-ldo-ota5-robust-pvt-mc](https://github.com/Arcadia-1/analog-design-bench/tree/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-ldo-ota5-robust-pvt-mc)。
GitHub 版本：`972f7cd7c95381134387b250edf18f3bd23bdd25`。此前 Hugging Face 阅读版本另记，不混作同一快照。

2026-10-10 已有静态阅读包括 instruction、参考电路、reference.json、启动 deck、verify.py 的启动分析和许可说明。没有运行原任务或复验其结果。源任务的工程动作是设计晶体管 LDO；我们的候选将固定 DUT，改为开发 VA 测量模块。

## 已有指标与场景

[启动测试台](https://github.com/Arcadia-1/analog-design-bench/blob/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-ldo-ota5-robust-pvt-mc/tests/benches/tb_startup.spi)包含供电斜坡、反馈、输出电容/ESR 和负载。VIN 在 1 μs 开始上升，用 20 μs 到达 1.8 V；记录到 70 μs。

[Python checker](https://github.com/Arcadia-1/analog-design-bench/blob/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-ldo-ota5-robust-pvt-mc/tests/verify.py)的启动分析定义：

- t90：记录中达到目标 90%，此后所有记录不再低于阈值的最早采样时刻。
- 建立时间：在斜坡结束后，首次进入目标 ±2% 且剩余记录始终在带内的时刻，减去斜坡结束时刻。
- 过冲：记录的输出峰值减目标电压，下限为 0。

这里的“此后”止于规定记录末端，不是无限时间保证。未找到合格建立时刻时，原算法使用无穷值；新题的明确状态码和输出格式仍需定义。VA 事件测量与离散记录算法的差异须校准。

## 使用边界

[项目许可](https://github.com/Arcadia-1/analog-design-bench/blob/972f7cd7c95381134387b250edf18f3bd23bdd25/LICENSE)区分软件 Apache-2.0 与 SPICE、题面、参考电路等内容的 CC-BY-NC-4.0。引用方法和复用具体文件分别登记，发布资产时按文件保留条件。

现有 DUT 没有 EN、shutdown 或 PG，70 μs 窗口也没有覆盖供电下降沿。该来源支持启动测量候选，不能直接称为休眠/唤醒题。电路依赖和配套 VA 缺口见 [电路记录](../circuits/adb-ldo-ota5.md)。
