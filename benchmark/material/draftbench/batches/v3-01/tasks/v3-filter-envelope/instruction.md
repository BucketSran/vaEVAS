# v3-filter-envelope

实现 `envelope(i,q,en,reset,env)`，连续能量状态 e'=2πbandwidth*(P-e)，env=sqrt(max(e,0))。
P=i²+q²（en>0.5）；禁用时P=0，因此包络指数衰减而非保持或瞬间归零。bandwidth为100–300Hz。
e(0)=initval，initial为0–0.02 V²。reset>0.5 时 e=initval，释放后继续积分。
输入I、Q在±0.5V。本题为包络动力学的独立交付，与混频题不构成完整接收机计数。
误差上限0.01V，复位切换模拟过渡区除外。

交付文件仅为 `/work/dut.va`，保持模块名、端口和参数。公开目录提供接口壳与自测网表。只允许修改候选文件；固定DUT和工程可读。后端固定Spectre，不限制合法Verilog-A写法。自测不能代替独立终评。权重1。
