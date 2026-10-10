# 按规格建立内部采样的 Alexander BBPD

<!-- workbench:begin -->

| 项目 | 当前记录 |
| --- | --- |
| Case / 设计版本 | case-0012 / r2 |
| 工程动作 / 电路家族 | 按规格构建模型 / PLL 与时钟 |
| 细分 / 上下文规模 | 基础单模块、Alexander 三点采样与历史对齐 / 单个工作单元 |
| 阶段 / 设计 review | 题目草案 / 待 review |
| 已 review 的设计版本 | 无 |
| 拟定形式 | 给采样及输出合同，提交内部采样和历史对齐的单个 VA Alexander BBPD |
| 公开自测形式 | 固定公开测试 |
| 固定后端 | 待选定；尚无运行验证 |
| Review 关注 | Alexander 内部采样方向已确认；r2 初始化、发布、重合窗口与 checker 待 review |
| 来源 | [v4-single-module-migration](../../../../sources/v4-single-module-migration.md)、[vaevas-behavioral-seeds](../../../../sources/vaevas-behavioral-seeds.md)、[alexander-bbpd-primary](../../../../sources/alexander-bbpd-primary.md) |
| 电路资产 | [v4-bbpd](../../../../circuits/v4-bbpd.md) |
| 同源组 | v4-family-001、cdr-phase-original |
| 关联 Case | 无 |
| 正式任务 | 尚未建立 |
| 运行 / 校准证据 | 无；当前仅有材料阅读与题目草案 |

<!-- workbench:end -->

## 当前方向与 r2 草案

2026-10-10，用户确认采用完整 Alexander 单模块，采样和历史对齐均由模块内部完成。本题属于按规格构建模型，仍是基础单模块，不包含 CDR 或 ADPLL 闭环。

新接口拟为 `VDD, VSS, DATA, CLK → UP, DOWN`，移除外部 retimed_data。每两个相邻上升沿及中间下降沿组成一组三点采样，在取得第三点后发布结果。本版进一步提出初始化无有效历史、按拍保持输出及窄重合窗口内允许自洽采样历史的规则，详见 [r2 题面草案](instruction.md)。这些细节和容差尚待 review，不把方向认可视为整份规格已批准。

[checker 设计](checker-design.md)从实际输入独立建立采样序列，并核对全段输出。普通时序有唯一答案；重合采样保留可行历史集合，同一中心值跨两组使用时必须一致。尚未实现新 reference、checker 或正式运行包；后端与容差须经校准后固定。

## 来源与行为变更

v4-001 及已有 spec-cdr-phase-detector 提供旧需求背景；Alexander 结构依据另见 [主源卡](../../../../sources/alexander-bbpd-primary.md)和[三采样学习说明](../../../../migration/alexander-bbpd.md)。新规格由我们根据该结构定义，不复制旧参考代码或论文中的实现。

r1 的 data 边沿触发、外部 retimed_data 和下一 clk 边沿清除，均不再作为新题合同。新题改为时钟采样、内部历史对齐及每组结果保持。旧两路条件与校准结果不能作为新规则正确性的依据。

本卡保留 v4-family-001 与 cdr-phase-original 的需求派生关联，不将新旧题重复计作独立电路来源。正式移植时优先处理已有派生任务的版本关系，不能直接改旧验收答案却继承历史成绩。当前只修改设计卡和草案。

## r1 旧资产核对记录

以下保留的是旧规格与代码的阅读结果，供追溯改题原因，不是 r2 的有效合同。

旧题给出的可执行规则是：每个 data 双边沿按 clk/retimed_data 电平重设方向；每个 clk 双边沿清零；retimed_data 单独变化不更新状态。初态全低。这份逻辑能被独立状态表检查，但尚缺 retimed_data 的采样时刻、延迟和与 data/clk 的合法关系，无法仅凭题面说明 UP/DOWN 为什么对应时钟早或晚。

旧公开测试分别用三个 PWL 源驱动 data、clk、retimed_data，没有生成 retimed_data 的锁存或重定时路径。可以验证各电平组合，不能据此声称验证了实际 CDR 中的早晚响应。按旧 PWL 和0.45 V门限静态推导，9.95 ns 的数据边沿置 UP，12.05 ns 的时钟边沿清除；19.95 ns 置 DOWN，28.05 ns 清除。这是文本推导，未执行仿真。

旧参考在下一个 data 边沿也会重设状态，因此“保持到下一 clk 边沿”在期间又来 data 边沿时不够完整。另有同时事件优先级、阈值相等、短于平滑/延迟的脉冲，以及方向翻转时模拟输出互斥的含义需要定义。第一题可以通过公开合法时序排除歧义，不必强行加入所有边界条件。

### 已有派生任务应优先复核

[spec-cdr-phase-detector](../../../../../tasks/spec-cdr-phase-detector/instruction.md)已经使用同一关系，补充初态、retimed不单独触发、边沿间距及无同刻仲裁等条件。其[SOURCE](../../../../../tasks/spec-cdr-phase-detector/SOURCE.md)明确需求参考旧 v4-001，同时声明实现独立编写。本卡保留 v4-family-001 与旧 cdr-phase-original 两个来源记录，并注明需求派生关联；不能把它们算作互不相关的工程来源。

正式迁移时先复核现有派生任务的参考与 checker，再记录新旧版本关系，不另复制一道同义题。该任务的旧语言禁用项、编译失败统一零分和历史运行资格不自动沿用。其文字在连续 data 边沿的处理上仍有“重新判相”与“脉冲保持”的边界，不能仅凭补过容差就认为合同已完整。

### 电路依据与建议

2026-10-10 阅读了 Ken Kundert 的 [Verification of Bit-Error Rate in Bang-Bang Clock and Data Recovery Circuits](https://designers-guide.org/analysis/bang-bang.pdf)第4节，以及 SciAnalog 的[官方 CDR 模型概述](https://www.scianalog.com/asset/modelbox/CDR_BangBangPLLCDR/doc_xmodel.html)开头的架构说明。两者把判相输出关联到数据与恢复时钟的早晚关系；SciAnalog 示例明确采用 Alexander 型 PD。这里只核对用途，没有据此证明旧 v4 真值表等价于该结构。

r1 阶段的建议是先确定检测结构，不能靠推测补全旧 retiming 合同。后续用户已选定内部采样的 Alexander，当前 r2 据此重定义接口与时序。

后续已核对 Alexander 的三采样关系、XOR 早晚逻辑与旧题差别，见[学习说明](../../../../migration/alexander-bbpd.md)。A/B/C 是三个有序的历史样本，旧题的 data/clk/retimed_data 三路瞬时电平不能直接对应。学习后选定的方向及 r2 规则草案见本页开头；该阅读本身不提供运行证据。

## 留给同行的问题

本轮优先 review 两项：按拍保持的输出接口是否适合基础题，以及窄重合窗口内允许自洽采样历史的验收方式。初始化与异常三元组规则已写入草案；窗口和输出过渡容差须在实现阶段校准。不要求同行现在评估完整环路性能。

## Review 记录

- 2026-10-10，r1：旧资产静态筛选后登记，选题方向与具体设计均待讨论。未复制正式任务、编译、仿真或模型试做。[本轮迁移入口](../../../../migration/README.md)汇总与其他候选的取舍。

- 2026-10-10，r1，继续审阅：核对旧题、reference、公开 PWL 和现有首批派生任务，记录 retiming 与连续事件协议缺口；方向及具体结构尚未获用户确认。补充证据不改变本版拟定交付，未增加新题或运行证据。

- 2026-10-10，r2：用户确认完整 Alexander 单模块，采样及历史对齐放在内部。补写公开规格和独立 checker 方案；新增细节仍待 review，未修改正式题或运行仿真。
