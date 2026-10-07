这个原创小仓库把时间间隔测量接入外部触发系统。已有 capture、quantizer 和 formatter 的模块接口，顶层仍使用原始宽度输出。请找到接线与状态路径，完成可配置量化、饱和、忙状态、超时和复位的端到端集成。工程供研究评测使用，没有工业版本史。

提交 `dut.va` 与 `rtl/capture.va`、`rtl/quantizer.va`、`rtl/formatter.va`。顶层 `tdc_chain(start,stop,reset,result,valid,busy,overflow)`。所有信号相对地，输入以 0.5 V 上升交越为事件；输入脉冲宽至少 0.2 ns，交越间隔至少 0.1 ns，未同时发生 reset/start/stop。reset 高电平禁止开始与停止，reset 上升清除结果和全部状态。

空闲 start 开始测量，busy=1、valid=0、overflow=0，result 保留上次结果。busy 期间重复 start 必须忽略。首次 stop 结束测量，busy=0、valid=1，result 为 `0.02*min(31,floor((tstop-tstart)/(lsb_ns*1 ns)+0.5))` V。输入时间单位为秒；`lsb_ns` 在 0.25 至 0.75 内。量化原码大于31时饱和到0.62 V并置overflow。无效 stop 不改变状态。超时 `timeout_ns` 在10至16内，start 后达到deadline且尚未stop，busy=0、valid=0、overflow=1，result 保留；超时报告不得晚于deadline+0.08 ns。超时之后可以重新start。未完成转换的结果不覆盖旧结果。

所有状态在事件后0.12 ns内建立，结果电压误差不超过0.002 V，逻辑稳态误差不超过0.01 V。边沿不得漏报或多报；波形检查也覆盖事件间保持、无效stop、超时和复位。使用平滑电压贡献，不依赖电流/负载模型。