# 课题组工程资料

从有历史来源线索的课题组目录恢复的源码。目录来源不等于原创作者证明；在课题组工程中找到的官方原版副本统一列入 Cadence，使用线索仍保留在来源总表。

[返回总览](../README.md) · [历史来源总表](../SOURCES.md)

功能说明依据原代码与注释整理，不代表已通过编译或仿真。源码接口、参数和注释均保留原样。

| 功能 | 文件数（含版本） | 查阅内容 |
| --- | ---: | --- |
| [数据转换与编码](data_converters/README.md) | 41 | ADC、DAC、CDAC、量化与码值重构 |
| [比较器](comparators/README.md) | 3 | 时钟比较、复位极性、失调与噪声 |
| [校准与逐次逼近控制](calibration_control/README.md) | 17 | SAR 握手、比较器失调搜索、增益校准与修调码 |
| [时钟、采样与数据对齐](clock_sampling/README.md) | 14 | 多相时序、采样保持、时钟复用、分频及鉴相 |
| [逻辑与寄存](logic/README.md) | 17 | 逻辑门、触发器、计数、加减法和寄存器 |
| [模拟信号处理](analog/README.md) | 8 | 放大、滤波、积分、复用、迟滞与限幅 |
| [测量与激励](measurement_stimulus/README.md) | 6 | 码型、波形、采样记录、静态线性度与事件测量 |

所有源码共用 [Cadence include 目录](../cadence/include/README.md)。已有原始 include 名称未改写。
文件名用于检索功能，实例化时使用源码中保留的 module 名。多个文件可能声明同名 module，须按用途选择版本，不能直接把整库一次性编译。
