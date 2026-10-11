# adc-spectrum

实现 `/work/dut.va`。模块 dut(code,clk,rst,sample_ok,sndr,sfdr,dc,enob,valid)，tone_bin可覆盖整数3至7。记录是带明确来源的行为合成12bit unsigned码值，code以1V/码表示0至4095整数，sample_ok为对应样本完整标志。采样率200MHz，64次clk上升沿为一条相干记录，矩形窗，不加窗或拟合。rst上升清空历史与输出，rst高不采样；初始零。64样本前输出全零valid=0；完成后保持直到rst。任何sample_ok低、越界或非整数码使整记录无效，所有指标清零valid=0。DFT归一化单边功率：1至31号bin为2*(C²+S²)/64²，Nyquist32号为(C²+S²)/64²，DC排除；基波为tone_bin唯一bin。SNDR=10log10(基波功率/其他1至32号bin总功率)，SFDR=10log10(基波/最大非基波单bin)，谐波计入失真，ENOB=(SNDR-1.76)/6.02，dc为原码均值。基波、总残差或最大杂散功率<=1e-8时无效，指标零。频谱全部核心计算必须由候选VA完成。公共及终评可改变tone、幅度、谐波、Nyquist和完整标志；不含噪声统计或非相干窗口。

固定后端 Spectre，候选源码按原字节运行，不作语言子集限制。仅 dut.va 可修改；输入及固定器件只读。初态及事件后允许1ns建立，之后输出绝对误差1mV，频谱dB误差0.03dB、ENOB误差0.006bit。输出可用 transition(...,0,100p,100p)；无需复制参考结构。公开台架见 `/work/public/cases.json`，终评改变合同内输入、端点、样本和控制时刻。测量 DUT 性能差仍可通过，评分只看报告正确。源代码、reference与私有checker不进入公开包。
