# Cadence 安装库模型

从 IC618Hotfix4、ICADVM201 安装树提取的 Verilog-A 模型。相同文件合并来源，不同版本源码分别保留。

[返回总览](../README.md) · [历史来源总表](../SOURCES.md)

功能说明依据原代码与注释整理，不代表已通过编译或仿真。源码接口、参数和注释均保留原样。

| 功能 | 文件数（含版本） | 查阅内容 |
| --- | ---: | --- |
| [数据转换与编码](data_converters/README.md) | 11 | ADC、DAC、CDAC、量化与码值重构 |
| [时钟与锁相环](clock_pll/README.md) | 13 | PLL、VCO、电荷泵、鉴相及单稳脉冲 |
| [逻辑与寄存](logic/README.md) | 23 | 逻辑门、触发器、计数、加减法和寄存器 |
| [模拟信号处理](analog/README.md) | 38 | 放大、滤波、积分、复用、迟滞与限幅 |
| [测量与激励](measurement_stimulus/README.md) | 36 | 码型、波形、采样记录、静态线性度与事件测量 |
| [电气器件](devices/README.md) | 30 | 无源器件、受控源、半导体、开关与故障模型 |
| [其他物理域](multidomain/README.md) | 17 | 机械、机电与磁路模型 |
| [控制环路](control/README.md) | 8 | P/PI/PD/PID 与超前滞后补偿 |
| [数学运算](math/README.md) | 17 | 加减乘除、幂、对数及多项式 |
| [调制、解调与信道](communications/README.md) | 20 | AM/FM/PM、PCM、QPSK、QAM 与传输信道 |

所有源码共用 [Cadence include 目录](../cadence/include/README.md)。已有原始 include 名称未改写。
文件名用于检索功能，实例化时使用源码中保留的 module 名。多个文件可能声明同名 module，须按用途选择版本，不能直接把整库一次性编译。
