# 公开自测

选择一份公开`.scs`，复制到`/work/test.scs`，将候选保存为`/work/dut.va`后，
在`/work`运行你可用的Spectre transient仿真。网表指定保存的电压信号。
将原始波形导出为CSV，列名time_s、out_V；PLL还需要tune_V。

`python3 /work/public/selfcheck.py --experiment <experiments.json中的name> --candidate-csv /work/observed.csv`

该脚本只比较公开完整实验并报告各输出的最大电压误差，不是终评或奖励。
时钟比较器只比较稳定电平；请另按公开波形查50%crossing延时。
采样保持避开控制事件5 ns护栏。没有后端执行记录时，不把CSV对比称为VA通过。
