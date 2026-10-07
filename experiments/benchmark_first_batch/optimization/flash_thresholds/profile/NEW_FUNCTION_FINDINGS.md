# 两个新增Flash候选的实际功能收据

`new_candidate_function_receipts.json` 包含6个实际档案：事件内线性扫描和解析逆各3个
完整条件，都通过冻结判据、真实returncode0/native零错误以及当前原始保存点oracle。
新回放检查全部152094点主负载或1636点短条件，最大原始点电压误差小于4.8e-8V，
未更改功能容差、输出延迟/线性rise、网表或10000次转换。收据列出原/执行VA精确
身份、archive/native/PSF/网表、执行checker/runtime/contract、当前oracle/cases的hash。
Raw保留本地，没有声称公开下载；这次收据提取没有启动新仿真。

| 新候选 | 条件 | accepted steps | intrinsic CPU(s) | solver process elapsed(s) | 冷编译elapsed(s) |
| --- | --- | --- | --- | --- | --- |
| event-only sampled linear | bank-throughput | 152093 | 3.93537 | 3.021129 | 0.777 |
| event-only sampled linear | positive-skew | 1635 | 0.052318 | 1.066705 | 0.791 |
| event-only sampled linear | negative-skew | 1635 | 0.053964 | 1.066687 | 0.788 |
| analytic inverse | bank-throughput | 152093 | 3.50341 | 3.421969 | 1.220 |
| analytic inverse | positive-skew | 1635 | 0.052640 | 1.517856 | 1.230 |
| analytic inverse | negative-skew | 1635 | 0.053530 | 1.517716 | 1.230 |

每个条件只跑一次，功能队列可能与其他工作并发，不能从这6次推导可重复速度差。
解析逆的数学边界证明与功能执行得到支持，但冷编译依旧较贵，没有证明整体更快。
事件内线性候选保留原255比较，只把采样间不使用的live_code计算移至原cross事件；
约0.78s编译与原基线接近，主负载进程3.021s值得进入预声明的新quiet五对。
下一测量以CPU中位ratio≤.97、至少4/5对获胜为待审标准，并另外要求真实整体耗时
收益；这里只记录主任务预声明，未宣布通过。保持旧二分`reference.va`不变，不覆盖
旧五对“intrinsic CPU省16.1%、进程反慢4.51%”结果。

工程用途、公开合同与算法解释见`ANALYTIC_CANDIDATE.md`和`DIAGNOSTIC_FINDINGS.md`。
解析逆不是新功能；邻界校正仍用原阈值式和原sample比较，必须保持`>=`等值语义。
新candidate收据不更新正式任务计数，也不替代后续正式评分的完整实际校准。
