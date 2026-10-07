# ADC采样保持的有限采集建立
ADC前端在采集窗口内追踪输入，在转换阶段保持最终采样值。实现 `sample_hold(vin,sample,rst,vout)`，全部electrical；参数tau=2 ns,vinit=0.45 V,vth=0.5 V，可覆盖。sample/rst为0/1 V，vin为0.05–0.85 V。
初态vout=vinit。rst高时输出固定vinit并取消过去采集历史；rst释放后从vinit继续。rst低且sample高时满足一阶建立 `dy/dt=(vin-y)/tau`；sample低时保持y不变。sample/rst以vth穿越切换模式。本电压域理想输出不包含输入电流、输出阻抗和负载耦合；不声称晶体管采集电路。
恒定输入的采集残差为 `(y_start-vin)*exp(-duration/tau)`；验收采集全轨迹、采集结束残差、保持期间不跟随输入和复位恢复，输出最大误差3 mV。输出不添加transition延迟，不允许离散更新近似破坏误差界。输入变化离采集模式转换至少200 ps；tau公开范围1–4 ns。

提交 `/work/dut.va`。只能使用标准 constants.vams / disciplines.vams；禁止文件I/O、系统调用及外部include。公开自测网表在 `/work/public/visible.scs`，用有授权的 Spectre 自测；远端公开调用入口由评测环境提供。最终评分独立运行，不能作为解题反馈。
