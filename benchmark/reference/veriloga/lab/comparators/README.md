# 课题组工程资料：比较器

[分类入口](../README.md) · [历史来源总表](../../SOURCES.md)

说明依据源码静态阅读；使用前按具体工程核对供电、时序、接口及仿真器支持。

| 模型文件 | 功能与使用场景 | 原始 module 与端口（顺序不变） | 关键参数／使用说明 |
| --- | --- | --- | --- |
| [clocked_comparator_offset_noise.va](clocked_comparator_offset_noise.va)<br>[来源](../../SOURCES.md#lab-comparators-clocked_comparator_offset_noise) | 带输入失调与高斯随机判决扰动的时钟比较器。 | `` L2_comp(DOUT, GND, VDD, CLK, VINN, VINP) `` | `` real td = 1n ``；`` real tr = 100p ``；`` real vos = 0 ``<br>vos、vn、seed_init 可设；在初始化时读取电源和门限。 |
| [clocked_comparator_reset_high.va](clocked_comparator_reset_high.va)<br>[来源](../../SOURCES.md#lab-comparators-clocked_comparator_reset_high) | 时钟上升沿比较差分输入，下降沿将双输出置高；用于动态比较器行为替代。 | `` L2_CMP_Ideal(input electrical CMPCK, input electrical VINN, input electrical VINP, output electrical DCMPN, output electrical DCMPP) `` | `` real vdd = 0.9, td_cmp = 30.0p ``<br>VINP=VINN 时双输出为低；默认 vdd=0.9、比较延时 30 ps。 |
| [clocked_comparator_reset_low.va](clocked_comparator_reset_low.va)<br>[来源](../../SOURCES.md#lab-comparators-clocked_comparator_reset_low) | 时钟上升沿比较差分输入，下降沿将双输出置低。 | `` comp_ideal(input electrical CMPCK, input electrical VINN, input electrical VINP, output electrical DCMPN, output electrical DCMPP) `` | `` real vdd = 1, td_cmp = 100.0p ``<br>默认 vdd=1、比较延时 100 ps；复位极性与 reset_high 版本不同。 |
