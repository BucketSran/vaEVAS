# 非计时求值计数版本

仅用于一次不计时的 profile，不能用其时间或CPU作为最终性能数据。
每个实际模拟回调/比较/采样事件累加计数，final_step 输出到日志。
模拟器对试探状态的回滚可能影响统计，所以计数描述保存的执行状态，不保证
包含所有被拒绝尝试。它用来核验重复比较确实发生，不能替代原始提交的重复计时。
必须同时保持独立波形判据通过，并用默认未加计数的源码作至少五对性能测量。

`sampled_linear_scan.va` 只把原255阈值扫描移入采样事件；
`continuous_binary_search.va` 只把线性扫描改二分，仍每次模拟求值解码。
两项是定位重复求值与算法成本的消融，非新增题目。它们没有插入计数或无用计算。
在独立功能判据通过后比较相同步数与intrinsic CPU，可解释最终收益的来源。
消融单跑仅作诊断，不替代原始两侧至少五对交替测量。

REQUEST.json声明四个精确诊断请求，只用bank-throughput，排在quiet timing之后。
read_counters.py只接受与本目录baseline/reference逐字节一致的instrumented source，
要求完整功能PASS、实际10000samples、唯一profile前缀；单独保留counter语义，不调用
正式performance guard或把带计数时间拿来评分。active $strobe使这些提交不具正式
性能源码资格。消融源码不含计数，用原生分项诊断；最终ratio仍来自未插桩五对。

将计数比较次数与真实转换次数和nativeaccepted对照，回答重复扫描是否确实执行。
将sampled_linear_scan/continuous_binary_search的单次成本与原两侧对照，只解释已测
负载的成本组成。若剩余时间主要是solver/ASCII波形写入，明确说剩余limiter，不期望
255/8比较次数比直接变成相同倍数端到端加速。编译及许可证开销另外报告。
