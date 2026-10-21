# AnalogBench 与 CVDP 的时序说明核对

2026-10-20，只读题面与配套代码。用于完善 VABench 的作者检查，不运行模型或仿真，也不证明这些外部题目已经正确校准。
采用的规则见[题包约定](../docs/task-package.md#时序边界与验收说明)，这里仅保留来源事实和借鉴边界。

## AnalogBench

读取 `Arcadia-1/analog-design-bench` 的固定版本 `972f7cd7c95381134387b250edf18f3bd23bdd25`，
与此前保存的 HF 样例对照；本次没有重新审核全部台架或终评。以下是具体样例的写法，不是整个数据集的统一格式保证。

| 样例 | instruction 实际说明了什么 | 可借鉴之处 |
| --- | --- | --- |
| [Ahuja OTA](https://github.com/Arcadia-1/analog-design-bench/blob/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-ahuja-compensated-two-stage-load-range-pvt/instruction.md) | 输入脉冲边沿 10 ns；从命令幅度的 1% 穿越开始计时；输出在 2 us 内进入并保持在目标的 6 mV 误差带，命令电平结束时也检查 | 输入变化、计时起点、响应截止和误差目标分别定义 |
| [divide-by-two](https://github.com/Arcadia-1/analog-design-bench/blob/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-transistor-divide-by-2/instruction.md) | 复位后 100 ps 内输出低；两次时钟沿之间释放复位时保持低，直到下一上升沿；另给时钟到输出延迟上限 | 复位响应与释放后的下一次有效事件分别说明，不能只写“支持复位” |
| [bottom-plate sampler](https://github.com/Arcadia-1/analog-design-bench/blob/972f7cd7c95381134387b250edf18f3bd23bdd25/tasks/sky130-bottom-plate-sampler-pvt/instruction.md) | 时钟源转换 50 ps；描述先采正输入、保持中反转输入、再采负输入，并给 5 mV 保持/采集预算 | 行为要求可以用可观察的输入序列说明，源转换时间与保持误差分别给出 |

这些数字属于各自电路任务，不能据此给 ideal VA 设定过渡时间或容差。题面中的稳定时间定义也不等于指定某种内部实现。

## CVDP

实读 NVIDIA 官方数据集 revision `5b807d945f6a99aa645f7e43a64a2115e281b4bf` 的
[v1.1.0 agentic no-commercial JSONL](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/5b807d945f6a99aa645f7e43a64a2115e281b4bf/cvdp_v1.1.0_agentic_code_generation_no_commercial.jsonl)。
下载文件 SHA256 为 `2007f4311ed731a985a4ed9187479ad2cfc2462bc4013eba0d72a9f35642fdcf`。
按 ID 抽读题面、context 与 harness；不是全量质量审核。与已有 [heavy 交付核对](cvdp-heavy-multifile.md)属于不同子集。

- 第 7 行 `cvdp_agentic_DES_0001`：题面定义从 `i_valid` 被读取到 `o_valid` 有效的延迟为 16 个周期，声明上升沿工作和低有效异步复位。`harness/src/test_des_enc.py` 在下降沿驱动/观察，并对延迟计数断言 16。这说明可以把行为时间参考放进题面，把具体驱动/读出相位留给台架。所读等待循环没有局部次数上限，不能把该实现整体当成可靠性模板。
- 第 69 行 `cvdp_agentic_phase_rotation_0038`：题面声明时钟/复位方式并引用公开 `docs/proc_fsm_spec.md`。该文档给出 valid 周期计数、单周期输出和等待计数的规则。`harness/src/harness_library.py` 的复位辅助函数分别等待 10 ns 再释放、再等待 10 ns；这属于该台架的安排，不是题面承诺的 DUT 响应时间。
- 另抽读第 57 行 `cvdp_agentic_lfsr_0005`，题面用逐周期期望/实际值表描述故障。其测试注释对 reset 的断言/释放称呼不一致；未运行设计，不把这些注释作为复位语义依据。

数字周期的延迟定义不能直接转换成模拟电路的 ps 容差。可借鉴的是明确触发事件、何时响应、何时观察，并逐项核对文字与台架。
输入斜坡、DUT 输出过渡、复位等待和观察偏移应分别命名；`transition()` 也不能由某个台架等待时间自动变成必选实现。

## 行为描述的详细程度

2026-10-20 再读上述原始样例，比较题面与实际公开规格的总信息量，不运行测试。

- AnalogBench 的 bottom-plate sampler 用先采正输入、保持时反转输入、下次采负输入的序列定义可观察行为，同时允许任意内部拓扑。divide-by-two 仍明确写出复位释放后的下一有效边沿，不能由其篇幅短推断边界行为省略。
- CVDP 的 DES 题除接口与周期关系，还写出初始置换、密钥调度、16 轮 Feistel 运算和最终置换，引用具体算法资料，并要求 `S1.sv` 至 `S8.sv` 文件。这比仅说明输入输出更具体。
- CVDP 的 control FSM 主 prompt 引用公开 `docs/proc_fsm_spec.md`。该文件逐状态定义转移、有效周期计数和单周期输出，还要求复用通用计数器、锁存等待值。短 prompt 不代表完整公开材料只有简略功能。

这些是已读样例的事实，不是整个数据集的统一格式或正确性保证。VABench 对行为定义题采用等价实现原则，
不照搬上述内部结构要求；已确认的本项目规则维护在[行为说明与草稿边界](../docs/task-package.md#行为说明的详细程度与草稿边界)。

## 首轮时序核对的修改范围

本轮只更新生成流程、模板提示、人工链接和链接静态检查。R01 ideal 的事件边界与具体数值仍待按该规则讨论，未改 instruction、gold、checker 或运行回执。
失败任务计 0 分、原因另记来自本轮人工确认，见[评分规则](../docs/evaluation.md#任务分数与失败原因)；这不是从外部数据集推导的统一评分政策。
