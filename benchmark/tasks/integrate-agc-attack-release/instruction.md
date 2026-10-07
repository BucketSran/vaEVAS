# 扩展接收机 AGC 的 attack/release

接收机AGC需要在突发强信号到达时快速降低增益，在信号减弱时缓慢恢复增益，降低过载并避免噪声泵动。已有幅度检测、增益控制和限幅输出路径，旧控制器只使用一个恢复常数。请扩展并集成不同的attack/release行为，保持检测延迟、增益范围、复位及限幅标志。

提交 `dut.va` 和 `rtl/detector.va`、`rtl/gain.va`、`rtl/amplifier.va`。顶层 `receiver_agc(signal_in,clk,reset,signal_out,gain,clipped)`。输入幅度不超过1.5 V；clk在0.5 V上升交越采样，周期sample_ns在2至4 ns。每次采样更新包络 `e_new=(1-alpha)*e_old+alpha*abs(signal_in)`，alpha在0.25至0.6。增益控制使用上一个周期的e_old，因为检测与控制各是一个寄存级。目标增益 `g_target=min(8,max(0.25,target_v/max(0.05,e_old)))`，target_v为0.3至0.5 V。若g_target小于旧g，tau=attack_ns，否则tau=release_ns，`g_new=g_target+(g_old-g_target)*exp(-dt_ns/tau)`。attack_ns在1至3、release_ns在8至18；dt是有效clk间隔，复位后第一次采样使用sample_ns。初始化和reset上升使e=0、g=1，reset高禁止采样。

控制周期之间增益保持；输出信号持续为 `clip(g*signal_in,-0.9,0.9)` V，不能把信号输出错做采样保持。clipped表示未限幅乘积绝对值大于0.9。reset高时signal_out和clipped为0，gain保持1。所有参数需传递到正确模块。采样相关输出在事件后0.15 ns建立；gain与输出误差0.004 V，标志误差0.01 V。输入在clk前后0.2 ns稳定，reset距clk至少0.3 ns。此题只要求电压域动态，不要求可变增益放大器的电流和阻抗。

公开工程在 `/work/public/`，请在 `/work/` 建立提交工程，入口为 `/work/dut.va`。可修改的提交文件清单见公开 `SUBMISSION.json`。同目录运行 `python3 public/smoke.py --candidate /work/dut.va` 可检查公开波形。终评输入均在上述合同范围内，不能访问隐藏测试或用时间表输出答案。
