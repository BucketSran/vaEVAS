# Flash 真实消融与计数诊断

四个指定诊断已在主队列实际执行，功能均通过。`actual_diagnostics.json` 保留归档/原始
VA/波形/native/新checker身份；`analyze_diagnostics.py` 对同一原始PSF用当前全保存点
oracle重判，四项均通过。这里是诊断轮，主任务用了3个worker；每项只有一次，不能
和之前安静五对的中位数混合成性能结论，也不能将打印计数版本放入计时分母。

| 诊断 | compile elapsed(s) | intrinsic CPU(s) | process elapsed(s) |
| --- | --- | --- | --- |
| instrumented continuous linear | 1.170 | 3.96863 | 3.772555 |
| instrumented sampled binary | 1.180 | 3.62232 | 3.420642 |
| event-only sampled linear（无打印） | 0.806 | 4.01365 | 3.071200 |
| search-only continuous binary（无打印） | 1.160 | 3.54506 | 3.371877 |

受信原始源码精确匹配后，merged stdout中的诊断计数给出：两侧152094个保存回调、
10000次采样；连续线性扫描38783715次比较，采样二分80000次比较。计数是模型状态，
拒绝求解尝试可能回滚，不宣称完整Newton调用总数。Spectre stdout把profile换行并
接在进度标记后面；严格计数提取器支持这两种实际排版，仍要求唯一三元组。
这些打印是明确声明的profiling-only任务，在正式性能source guard下仍必须拒绝。

消融给出的事实：连续二分的CPU与旧采样二分quiet中位数接近，采样线性只显示较小
CPU差；因此不能把原16% CPU收益全归因于搬移采样事件。两种二分源码均需要约1.16s
冷编译；事件内固定线性循环编译0.806s接近原基线quiet0.779s。推断：下一项合理
候选是只搬移扫描的 `sampled_linear_scan.va`，可能减少等待时间且避开二分编译代价。
其单轮process3.0712s值得再测；没有五对重复，不声明提升。编译器生成代码的具体
热点未采集；不从源码长度猜测编译器机制。

语义依据：公开合同只要求时钟正向cross的瞬时输入决定held_code，之后保持至下个
采样。基线live_code在每次模拟求值扫描，只有cross才赋给held_code；候选在同一cross
内部执行完全相同的255阈值公式、`>=`比较和最终整数赋值，输出transition完全相同。
阈值函数u+skew*u*(1-u)在u∈[0,1]的导数1+skew*(1-2u)≥0.7，许可参数范围保持单调；
事件内线性扫描不依赖二分的单调优化。输入不在cross间使用，故不会改变保持语义。
实际诊断已证明主负载语义；另外两个skew/vref条件及新quiet五对尚需主任务执行。

下一步不延长工作量、不改accuracy、VA接口、输出有限边沿或后端：先验证该候选
全部3条件，再冻结source+新checker做原100us/10000转换五对AB。旧二分参考、原来
五对CPU下降但端到端反增的证据继续保留，只有新证据能决定第五题是否成立。
