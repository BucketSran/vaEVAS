# Verilog-A 参考模型

按来源先分为 **课题组工程资料** 和 **Cadence 官方安装资料**，每类内部再按功能查找。所有模型保留原始源码内容；历史路径、原文件名和 v3 记录统一放在 [SOURCES.md](SOURCES.md)。

**仅供课题组内部研究，不对外分发。** 这里保存原始模型资产，尚未构建 benchmark 任务、checker 或通过仿真认证。

| 来源 | 模型文件（含版本） | 入口 |
| --- | ---: | --- |
| 课题组工程资料 | 106 | [lab/README.md](lab/README.md) |
| Cadence 安装库 | 213（171 个 module 名） | [cadence/README.md](cadence/README.md) |
| 公共 include | 6 | [cadence/include/README.md](cadence/include/README.md) |

## 按功能查找

| 功能 | 课题组资料 | Cadence 资料 |
| --- | --- | --- |
| 数据转换与编码 | [41 个文件](lab/data_converters/README.md) | [11 个文件](cadence/data_converters/README.md) |
| 比较器 | [3 个文件](lab/comparators/README.md) | — |
| 校准与逐次逼近控制 | [17 个文件](lab/calibration_control/README.md) | — |
| 时钟、采样与数据对齐 | [14 个文件](lab/clock_sampling/README.md) | — |
| 时钟与锁相环 | — | [13 个文件](cadence/clock_pll/README.md) |
| 逻辑与寄存 | [17 个文件](lab/logic/README.md) | [23 个文件](cadence/logic/README.md) |
| 模拟信号处理 | [8 个文件](lab/analog/README.md) | [38 个文件](cadence/analog/README.md) |
| 测量与激励 | [6 个文件](lab/measurement_stimulus/README.md) | [36 个文件](cadence/measurement_stimulus/README.md) |
| 电气器件 | — | [30 个文件](cadence/devices/README.md) |
| 其他物理域 | — | [17 个文件](cadence/multidomain/README.md) |
| 控制环路 | — | [8 个文件](cadence/control/README.md) |
| 数学运算 | — | [17 个文件](cadence/math/README.md) |
| 调制、解调与信道 | — | [20 个文件](cadence/communications/README.md) |

## 查阅方式

1. 先选来源和功能；分类页逐文件说明功能、端口顺序、关键参数与已观察到的使用限制。
2. 文件名为查阅方便按功能整理，源码里的 module 名和接口没有改动。需要实例化时以源码为准。
3. 与官方文件相同的课题组副本归入 Cadence，来源总表仍记录出现过的课题组工程。对其余文件不推断原创性。
4. 同名 module 的不同版本须择一使用；公共 include 文件路径见头文件说明。该目录不是可直接整体编译的库工程。
5. 功能描述来自代码和原注释的静态整理。原代码中的不一致已在相应条目注明，没有在归档中修复。
6. 新资料继续沿来源与功能两层添加，并同步更新分类页和唯一的来源总表；没有实际源码的历史线索只列在待恢复清单。

## 当前范围

覆盖 124 个历史来源路径，另有 45 个仍待定位；现存文件是否与当年的原始汇总包一致尚未确认。
完整工程、原始测试平台、使用结果与其他安装库配套文件不在本目录的此次整理范围中。
