# Flash事件内扫描准入提案

新`reference.va`与`sampled_linear_scan.va`逐字相同，SHA256为
`723e3129453deb04607d94c43eb5a152960bd5ea9702f397f48c029ea97606ae`。
原基线SHA256为`c35882d198a41c80a81257711c4e8f9ab8f9c83d3421c6472d376ca2d79663a6`。
旧二分参考原样保留为`../reference_binary_original.va`，旧五对CPU下降16.1%但进程
反慢4.51%的未准入结果仍保留，解析逆候选也未进入参考。

这次优化保持255个阈值及原比较顺序，只将扫描从每次analog求值移到原采样事件。
这是sample/hold模型：采样间的live_code不参与输出，held_code才驱动transition；
初始held_code=0和clock上升采样、0.2ns delay、0.3ns线性rise都保持。固定工作量仍是
100MHz下10000次转换；没有改变负载、网表、容差或输出分辨率。诊断计数与两种
独立消融见`DIAGNOSTIC_FINDINGS.md`，计数版没有进入正式测速或评分。

`current_reference_fullraw_proof.json`在当前独立oracle上重放真实基线与新参考各3个
条件的全部原始保存点，6/6通过；同时校验原/执行VA、网表、原report/PSF身份、
returncode、原生零错误与真实merged stdout/stderr。它保留旧执行checker身份和新
回放checker/cases身份，明确是旧真实波形重判，不是新仿真。

`event_only_quiet_receipt.json`精简保留实际热身一对及5对AB交替的全部身份和统计。
原分析SHA256为`504d89e1aa58ad4cc2878bc45079b0ec69428a35dd97d22ae8f1c3f1aba67283`，
来源是主工作树`runs/benchmark-first-batch-20261008/flash-event-only-pairs-v2/analysis.json`。
每份archive/native/PSF/source/criteria/网表的hash均保留，原始档案只在本地保留，
没有公开下载地址，也没有称这批分包运行是正式同job grader执行。

| 实际5对指标 | 基线中位数（范围） | 新参考中位数（范围） | reference/baseline | 获胜 |
| --- | --- | --- | --- | --- |
| intrinsic tran CPU(s) | 4.20408（4.18145–4.23663） | 3.96201（3.87824–4.07509） | 0.942420 | 5/5 |
| solver process elapsed(s) | 3.321539（3.271028–3.722963） | 3.071027（2.970903–3.121364） | 0.924580 | 5/5 |
| accepted tran steps | 152093（固定） | 152093（固定） | 1 | 0/5 |

CPU下降约5.76%，进程耗时下降约7.54%，步骤数没有下降。不能将CPU分项等同于进程
或网络耗时。进程计时包括Spectre启动、初始化和冷编译，不含远端调度/传输；固定
`+mt=1`，原生Spectre版本和host身份由收据绑定。64核host开始观察的1/5/15分钟
负载为0.30/0.40/0.45，结束为1.04/0.82/0.62，两次均未观察到活动Spectre。
这些只代表两个观察时刻，不能证明全窗口绝对独占。
原生日志时钟窗口为04:17:04–04:20:33，精度1s且时区未知；该3分29秒包括热身、
测量及间隔，不能当成求解总耗时。

`hypothesis.json`在执行前预定CPU中位ratio≤0.97、至少4/5对获胜，并要求实际整体
进程改善；没有因结果调整阈值。提案`admission_flash_proposed.json`仍admitted=false，
待独立窄审与主任务准入后才允许生成第五题。正式评分目标是原生intrinsic CPU，
编译/进程耗时会单列；本次参考准入还使用真实进程改善这一工程实用性检查。
后续仍须正式参考和负例校准；这份准入证据不宣称正式grader已执行通过。

进程改善只用于这次事件内扫描参考的准入判断，不是每个满分候选的硬门槛。
旧二分实现若实际满足公开CPU与功能规则，也是合法的CPU优化替代实现；它不是
checker负例，其已观察到的端到端回退必须保留。任何满分报告都须把CPU结果与
实际进程计时分开，不能从CPU满分推导端到端更快。
