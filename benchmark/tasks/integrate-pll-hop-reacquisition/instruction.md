# 集成 PLL 跳频重捕获

系统需要在工作中切换PLL频率。已有连续时间频率跟踪器和相位振荡器，旧lock输出只相对初始频率判断。请接入面向最新命令的锁定判据，并保证连续相位、连续频率和跳频后重新捕获。

提交 `dut.va` 和 `rtl/tracker.va`、`rtl/oscillator.va`、`rtl/lock.va`。顶层 `hopping_pll(command,hop,reset,frequency,wave,locked)`。command电压表示GHz，在0.6至1.4之间；hop上升交越0.5 V锁存命令，未hop的command变化不得改变目标。初态frequency=1 GHz、相位0、locked=0。频率合同为 `df/dt=(target-f)/(tau_ns*1 ns)`，`tau_ns`为3至7。跳频时频率与相位连续，不允许重启振荡器。相位以cycle为单位，`dphase/dt=frequency*1e9`，wave=`0.5+0.5*sin(2*pi*phase)` V。frequency输出的电压数字等于GHz值。

每次hop立即撤销locked。只有最新目标的频率误差连续不大于lock_tolerance GHz达到dwell_ns才置1。lock_tolerance在0.008至0.02，dwell_ns在0.4至0.8。重捕获过程中再次hop必须以当时实际频率为初值，重新计时，不能沿用旧deadline。locked边沿允许0.12 ns实现延迟，不得提前超过0.02 ns。

reset高时frequency=1、wave=0、locked=0，禁止hop；解除reset以相位0、频率1重新开始，并重新累计dwell。其他控制事件相距至少0.2 ns，command距hop至少0.3 ns。frequency误差0.001 GHz，wave误差0.01 V，标志误差0.01 V。此题是规定闭环动态的电压域集成任务，不要求晶体管VCO或电流建模。

公开工程在 `/work/public/`，请在 `/work/` 建立提交工程，入口为 `/work/dut.va`。可修改的提交文件清单见公开 `SUBMISSION.json`。同目录运行 `python3 public/smoke.py --candidate /work/dut.va` 可检查公开波形。终评输入均在上述合同范围内，不能访问隐藏测试或用时间表输出答案。
