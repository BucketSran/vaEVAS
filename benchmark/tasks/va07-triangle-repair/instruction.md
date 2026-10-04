# 修复积分三角波振荡器

将完整、可供 Spectre 使用的 Verilog-A 模型保存到 `/work/dut.va`。
模块为 `triangle(ctl,z,count,r)`，所有端口为 electrical；ctl 是输入，z 和 count 是输出，r 是参考端。

模型应在 lower 与 upper 之间往返。初始电压为 initial_voltage，初始运动方向为 direction（+1 或 −1）。
`V(ctl,r)` 始终严格为正，表示运动速度的数值，单位按 V/s 使用。
每到上限就开始下降，每到下限就开始上升。ctl 可以随时间连续变化；电压必须持续积分，
换向时不复位。count 初始为 0，每次实际换向增加 1，并作为相对 r 的电压输出。

保留 real 参数：lower=-0.5、upper=0.5、initial_voltage=0.0、direction=1.0、ttol=1e-10、vtol=1e-10。
测试保证 `lower < initial_voltage < upper`，direction 为 ±1，两个容差参数为正。
允许等价实现；不能硬编码振荡周期或换向时刻。不得读取外部文件、启动进程或检测仿真器身份。
只允许标准 `disciplines.vams` / `constants.vams` include。

下面的事件规则会在边界附近反复换向。修复它，并补全模块和初始化：

```verilog
V(z,r) <+ idt(sign*V(ctl,r), initial_voltage);
@(cross(V(z,r)-upper,0,ttol,vtol) or cross(V(z,r)-lower,0,ttol,vtol)) begin
    sign=-sign;
    n=n+1;
end
V(count,r) <+ n;
```

验收改变初态、上下限、初始方向和 ctl 的时间轨迹。还会在两档已规定的求解容差下运行。
在测试时域内，波形误差须不超过 1 µV，换向时间误差须不超过 200 ns，换向次数必须正确。
初始状态也会检查。事件的定位误差可以影响附近波形，但不能增加一次换向。
