# Flash ADC 阈值扫描候选

原创 8-bit 采样 flash ADC，用单调比较器阈值阵列表示固定的偏置/INL。
baseline 每次模拟求值计算255个比较器阈值，再在时钟上沿保存码；当前reference在
采样事件内执行相同的255次线性扫描。两者相同电压接口、阈值阵列与输出过渡。
阈值扫描确实参与最终输出，不含 spin、死代码或人为重复运算。
旧二分参考保留为reference_binary_original.va，其CPU收益未转成整体进程收益，
没有准入。当前事件内扫描已完成实际功能与5对测量，仍待准入窄审，不计正式题；
固定身份、原始点重判与分项结果见profile/EVENT_ONLY_ADMISSION.md。

固定 bank-throughput 为 100 us、100 MHz 时钟、10000 次转换，输入是
1.37 MHz 满幅正弦，覆盖上下越量程。其它两 case 验证正负偏置、不同满量程。
独立 oracle 从公开正弦公式及阈值合同计算每次采样码，检查实际时钟边数、
采样后 2 ns 和 8 ns 的保持电平及复位。误差 0.3 mV，小于输出半 LSB。

先三 case 各侧功能校准。若输出满足合同，profile baseline 确认实际 AHDL 阈值
计算是 limiter。性能case热身后至少5对AB交替，固定同机单线程与求解设置；记录
Spectre simulation CPU/elapsed、accepted/rejected步数、harness端到端时间、缓存、
启动/许可证/网络开销与机器负载。若收益未超过波动，则退回候选。
参考 REQUEST 与 benchmark-checklist 的方法一致，所有远端运行由协调者排队。
