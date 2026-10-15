# 双边界轮询窗口检测器

实现window_comparator_ref(VDD,VSS,vin,out)，端口electrical。参数vlow=.3V、vhigh=.6V、tedge=200ps、tick=500ps。VDD和VSS固定，VDD>VSS。初始状态由vin相对VSS决定；在全局时间k*tick，k=0,1,...轮询vin，严格位于(vlow,vhigh)时输出VDD，否则VSS。每次目标变化用tedge平滑。两个tick之间保持决策，即使输入越界也不立即更新。范围涵盖非零VSS、精确边界值以及短于tick的窗口；此题考察确定轮询语义，314考察异步迟滞历史。


实现方式不限，合法Verilog-A语法不另行限制。不得读取评分材料或重放固定测试答案。提交/work/dut.va，固定Spectre环境运行。允许2mV电压误差；终评覆盖公开合同内不同激励，不检查未定义的同刻事件。公开自测为public/visible_test.scs。实际校准pending。
