# #150 交付核对

本表按三个工程目标核对题目合同、台架和行为判据。作者结果见[固定报告](author-calibration.json)：20个新PLL实际仿真与24个D2/D3归档重分析共44条件，14个正例全部通过，15种语义错版全部被拒绝。原执行和新analysis身份分开保留；历史68个实际条件不替代最终版。发布和合并由主协调者处理。

| 要求 | 资产与独立观测 | 反例 |
| --- | --- | --- |
| D1实际N/N+1反馈 | 固定netlist实例化healthy_dco；候选dco为输入。checker重数相邻FB上升沿间的DCO边沿，并要求FB与一个实际DCO边沿对齐 | integer_only、feedback_bypass、detached_feedback |
| D1分数/整数兼容 | n=3/4，fraction=0/.25/.5/.75；窗口平均分频、实际频比及相位均合格 | 固定整数分频或假反馈 |
| D1配置/reset生效 | 固定刺激改变n/fraction，撤销资格、清状态后重新捕获；物理指标与lock分开检查；直接读取rst验证fb/lock清零，25/50/75/125us模式变化及100us reset均撤销资格 | reset_feedback、stale_qualification；无反馈固定调谐在DCO灵敏度反事实下失败 |
| D1运行中扰动 | 固定真实DCO在150us加入±2MHz频率偏移，175us撤除；新增两个恢复窗口保持原全部频率/相位指标 | detached_feedback、open_loop |
| D1恢复期限 | 模式驻留25us，每次实际配置/reset释放/扰动事件后15us检查资格，允许2.2ns有限数值过渡；物理窗口晚于期限，频相容差不变 | within_deadline实际14us恢复通过；late_recovery实际16us恢复因期限失败，单元边界对照亦覆盖 |
| D1非唯一合法序列 | 不比参考比特流；alternate改变累加器初相与比例增益，checker单元检查接受两种3/4序列 | 不合法计数或错误平均比率 |
| D2可辨识失调 | cal为专用零输入窗口；码通过固定前端实际改变差模输出 | fixed_code、wrong_direction |
| D2持续跟踪与正常信号 | 固定台架保留正负信号平台和切换；两种慢变轨迹与执行增益；独立输入输出残差同时覆盖零输入和有用信号 | cancel_signal |
| D3共模与差模同时成立 | 固定前端调节真实两路共模，checker分别计算CM与DM | measure_differential；checker单元检查两路输出相等应失败 |
| D2/D3离散执行码 | -64到64，允许有限过渡沿；非整数平台需拒绝 | fractional_code；单元检查合法100ns码沿 |
| D2/D3停启/reset/限幅 | enable低保持、reset清零、有界码、双路轨约束、大偏置扰动及恢复 | 错方向码饱和；固定码无法跟踪恢复 |
| 来源处置 | source-provenance.json固定302/306/369/390的来源资产SHA；306与369按相同D2合同归并，390保留D3 | 不复制许可未知的旧实现，不把旧v2 TDC改名计题 |
| 固定后端与评分 | v2_runtime原字节执行候选，circuit harness封存/隔离/恢复；编译、checker和基础设施错误均保留未评分 | 实际编译成功的行为错版才算checker语义拒绝；D2/D3以统一新checker逐波形重分析 |

作者校准只验证这些公开范围、条件与已登记变体。它不证明所有算法都正确，不建立噪声或杂散性能，也不代表模型通过率或开源后端等价。
