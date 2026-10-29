从公开 `fixed_lp.va` 的健康固定低通扩展模块 `programmable_lp(u,code,reset,y)`。
参数 base 单位 Hz（800–1200），initval 是初态及复位电压（±0.1）。code 电压在0–3，c=clip(round(code),0,3)。fc=base*2^c。
连续状态 y'=2πfc*(u-y)，y(0)=initval。code 跨舍入阈值即时改变速率，必须保持 y 连续，不清空历史。
reset>0.5 时 y=initval；释放后从此状态积分。码0必须保留基线行为。输出误差上限0.008 V，复位切换的模拟过渡区除外。
固定基线可读且不能修改；交付可任意选择等价实现，不强制沿用内部形式。
