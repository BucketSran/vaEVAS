# 修复ZOOM ADC的SAR、积分与细转换时钟关系
ZOOM ADC先采样、粗SAR、残差移交、积分，再作细转换。人工故障starter的子时钟索引误用父周期，造成细转换漏脉冲；需要修复九路时序并保持整个相位合同。这一错误类型与历史首轮ZOOM参数接线故障相关，但本题源码及错误独立编写。
实现 `zoom_timing(rst,sample,sar,residue,integrate,clk_sar,zoom,clk_zoom,rst_zoom)`，九端都是electrical 0/1 V输出。参数nbits=4（允许4–5）、step=0.8 ns（0.7–0.9 ns）、frame=18 ns（18–20 ns）、tick=20 ps、tr=50 ps。相位t从每个frame开始，相位0初始；不加端口/侧信道。
每帧：rst在[0,0.6 ns)，sample在[1,2 ns)，sar在[2.4 ns,F)，F=2.4 ns+nbits*step。clk_sar有nbits个脉冲，第j个在[2.4 ns+j*step,2.7 ns+j*step)，j从0开始。
residue在[F+0.2,F+0.7 ns)，integrate在[F+1,F+2 ns)，rst_zoom在[F+2.1,F+2.3 ns)，zoom在[F+2.5,F+5.5 ns)。clk_zoom恰有3脉冲，第j个在[F+2.5 ns+j*step,F+2.8 ns+j*step)，j=0..2。其他时刻所有对应目标为0；输出有限tr平滑，允许tick量化延迟0–20 ps。状态机/事件日历写法不限。
这是电压域时序控制架构，不模拟ADC器件电流。验收完整脉冲数、采样/粗SAR/残差/积分/细转换先后与重复帧，不以单点电平替代时序。电平20 mV、50%边沿100 ps容差；错过一个脉冲即失败。公开/隐藏只改变上述合法nbits、step、frame。

提交 `/work/dut.va`。只能使用标准 constants.vams / disciplines.vams；禁止文件I/O、系统调用及外部include。公开自测网表在 `/work/public/visible.scs`，用有授权的 Spectre 自测；远端公开调用入口由评测环境提供。最终评分独立运行，不能作为解题反馈。
