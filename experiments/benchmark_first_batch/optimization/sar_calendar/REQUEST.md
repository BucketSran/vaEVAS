# 传感器 SAR 转换器事件日历候选

原创12bit SAR行为控制器，固定每次转换12个50ns位周期；20次转换分布在100us内，
用途为200kS/s传感器前端的系统瞬态仿真。输入start的上升沿在空闲时采样一次，
每个位周期驱动真实DAC试探值并比较被保持的输入，最后输出完整码及valid。busy时
的新start忽略；异步reset取消在途转换、清busy/valid及码；完整码保持到下一完成或
reset。valid在完成时置位，下一被接受start/reset清除。没有人为增加位数、spin或
额外计算；所有循环实际消费电路输入并推进控制状态。

baseline为常见1ns精度轮询控制器，每次轮询实际观察reset/start并检查位到期状态。
该精度服务公开2ns输出事件误差合同，不能任意降精度。reference用start/reset的
cross及动态位deadline timer，空闲不轮询，但真实12位工作、DAC阶梯及时间必须保持。
每位DAC试探输出也列入独立判据，不能直接计算最终码并假装等待后完成。

公开输出busy/valid、归一化code以及SAR内部DAC控制电压dac；输出有限线性边沿0.5ns。
code采用4095端点归一化，dac采用4096电平缩放。sample/hold与理想12bit转移分别定义，
无符号量程外钳到0..4095。oracle从公开PWL求start/reset阈值边沿及采样电压，以独立
floor量化和码前缀构造每一位试探值，核验busy/valid/码/每一DAC阶段。所有稳定点误差
4uV，事件误差2ns；相对检测的各输出中点核验25/75%有限边沿形状。三case含100us固定
吞吐、busy重复start和reset中断、80ns位周期/vref0.8。input在转换期间改变以验保持。

v3 actual两侧三个功能条件均过，真实20转换/240决策与公开DAC阶梯正确；
仍无五对重复结果、无性能结论，不是正式题。纯解析fixture已核验
20完成/240决策、冲突reset条件3完成/42决策/1取消/1忽略、不同位周期3完成/36决策；
这些不是Verilog-A执行证据。

请协调者通过已有harness排baseline.va/reference.va重命名dut.va，使用
`probes/optimize-sar-calendar`。先双侧三case功能全过，再获取native步骤数及intrinsic
tran CPU/elapsed，独立profile轮询产生的实际事件工作；无真实性能信号则退回候选。
只有选题鉴定通过才做至少五对交替、记录负载/编译/许可证/独立process耗时等分项，
遵循上级REPEAT_REQUEST。错误基线不可参与优化计时，任何功能修复单独记录重校。
