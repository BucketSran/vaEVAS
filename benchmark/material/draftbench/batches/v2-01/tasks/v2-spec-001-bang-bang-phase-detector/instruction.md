# 完整Alexander判相器

实现module alexander(data,clk,rst,enable,retimed,up,down)，所有端口electrical。输入data、clk、rst、enable为0/0.9V电平，输出后三个端口。参数vdd=.9V、vth=.45V、trf=10ps、td=0。

内部三次采样必须来自data。A是前一次clk上升沿保存的数据，B是紧邻下一上升沿之前下降沿的数据，C是当前上升沿的数据。初始三者为0，输出为0。每次下降沿保存B；每次上升沿依次取A=旧C、C=data，输出up=vdd当A!=B且B==C，down=vdd当A==B且B!=C，否则0。retimed=vdd*C。输出保持至下次上升沿，td传播延迟和trf平滑。

rst高或enable低异步清零全部采样和输出。重新使能后从清零状态开始。data与clk交点至少隔2*trf，初始clk低，不检查同刻事件。采样结构是规定职责，不能由外部retimed输入代替。


实现方式不限，合法Verilog-A语法不另行限制。不得读取评分材料或重放固定测试答案。提交/work/dut.va，固定Spectre环境运行。允许2mV电压误差；终评覆盖公开合同内不同激励，不检查未定义的同刻事件。公开自测为public/visible_test.scs。实际校准pending。
