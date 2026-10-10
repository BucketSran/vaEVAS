# 异步迟滞窗口

实现hysteretic_window_comparator(vin,rst,enable,low_trip,high_trip,inside_flag,state_metric,toggled)，接口端口均electrical。参数vdd=.9V、vss=0、vcm=.45V、vth=.45V、tr=200ps、hyst=10mV、pulse=1ns。

初始状态outside，输出均vss。门限low_trip和high_trip在一次运行内固定，low_trip+hyst<high_trip-hyst。rst高或enable低异步清零且取消待结束脉冲。使能且非复位时，在vin向内越过low_trip+hyst或high_trip-hyst进入窗口；已inside时只在vin向外越过low_trip-hyst或high_trip+hyst退出。释放reset或enable上升时按当前vin检查进入条件。inside_flag和state_metric编码相同历史状态。每次有效状态变化发pulse时长toggled脉冲，间隔至少pulse+2*tr。输入跨越不能在门限停留，输出用tr有限过渡。异步交点立即更新，不允许周期轮询漏掉短窗口。


实现方式不限，合法Verilog-A语法不另行限制。不得读取评分材料或重放固定测试答案。提交/work/dut.va，固定Spectre环境运行。允许2mV电压误差；终评覆盖公开合同内不同激励，不检查未定义的同刻事件。公开自测为public/visible_test.scs。实际校准pending。
