# Verilog-A Benchmark

本模块评估模型与智能体能否用 Verilog-A 完成工程任务，按任务要求验收交付物。
任务格式已确定：使用 **Harbor 原生格式**。

当前有 6 个来自真实资产的内部初筛任务，覆盖逻辑对照、SAR 握手、ZOOM 时序、
增益校准、动态 VCO 和带负载运放。题目清单、校准和 GLM/Codex 运行协议见
[能力初筛说明](../experiments/va_screen/README.md)。它们尚不是正式 benchmark 发布版。
[reference/](reference/README.md) 保存历史 vaBench 发布包（v1 完整、v4 最新快照+文档），
以及按来源和功能整理的[原始 Verilog-A 资料](reference/veriloga/README.md)。
原始资料分为课题组工程模型与 Cadence 安装库模型，仅供内部研究，不对外分发。
另有一个仓库自有的候选修复题：[积分三角波振荡器](tasks/va07-triangle-repair/instruction.md)。
它检查双向事件导致的边界反复换向，单独校准，不加入原六题的初筛成绩。
原创 [ADC DNL/INL测量首题](tasks/va08-adc-linearity/SOURCE.md) 已有本地checker校准与任务资产，实际 Spectre/Harbor 校准及模型试跑待完成，也不加入原六题分母。
任务位于 `tasks/`；每题 `SOURCE.md` 说明原始资产和必要改编，原始源码保持不变。

## 目标与边界

新题以实际 Verilog-A 使用场景为依据，建设目标是形成有可信评分、能区分模型能力的工程任务。
现有初筛成绩只说明已测题目与模型的表现；新增题型的难度和区分度需要实际校准。

当前聚焦[电压域行为模型](../GLOSSARY.md#电压域行为模型)。这一边界限制待建模的行为，
验收电路可以包含交给 Spectre 求解的晶体管及其他器件。例如，电压接口的校准控制器可以
接入真实比较器验收；要求候选模型实现电流、输出阻抗与负载耦合的任务暂不纳入当前范围。
出现足够的范围外工程需求时，再讨论是否扩展，不能由单个新题隐式改变范围。

Spectre 是最终验收后端，题目规格与独立判据定义正确性。源码、输入、初态及数值设置需要
固定并校准；EVAS 的通过记录不能代替 Spectre 验收。若 Spectre 结果不符合预期，先区分
模型写法、语言语义、容差、后端实现及环境原因，再按下节记录候选，不直接将该波形定义为正确答案。

属于约定范围且已经具备可信 Spectre 验收的题目，可以在 EVAS 尚不支持时继续建设。
EVAS 将相关缺口纳入候选需求，按影响的任务类别、工程使用频率和实现成本决定优先级。
公开任务的开源复现范围需要单独验证，不能从参考解在某个后端通过推导任意提交或整个题库均可复现。

## 评测方式与题目建设

主评测采用 [Agentic 评测](../GLOSSARY.md#agentic-评测)，允许智能体在约定预算内读取文件、
运行仿真、查看反馈并修改交付物。以任务完成率衡量工程能力，
[One-shot 评测](../GLOSSARY.md#one-shot-评测)作为对照。
具体工具范围、反馈内容和交互预算由后续评测协议确定。
评测需要私有 checker；其保密范围、与公开自测及开源复现的关系仍需专题设计。

任务设计需要覆盖多样的工程工作，具体分类与首批范围尚未确定，见
[任务体系设计议题](https://github.com/BucketSran/vaEVAS/issues/72)。
评测协议后续参考 CVDP 和 [Analog Design Bench](https://github.com/Arcadia-1/analog-design-bench)
另行讨论，不将已有示例题型或工具反馈建议视为定案。

核心挑战题需要在合理的工具交互预算下仍有区分度。首次提交出错、随后根据仿真反馈立即修好，
可以作为过程分析的结果，但不足以单独证明题目困难。

先按工程价值确定任务类别，再在各类内建设挑战题。保留少量容易但重要的任务作为基础覆盖，
不让它们占据主体；也不单凭某个模型失败就收题。按以下顺序建设并校准新题：

1. 选择真实使用场景，说明任务的工程价值。
2. 明确候选需要交付什么，并依据规格建立验收判据。
3. 用参考解和有代表性的错误版本校准验收程序。
4. 用多个模型试跑，区分题目缺陷、环境问题与模型能力不足。
5. 根据工程目标和试跑证据调整难度，完成校准后冻结题目版本。

## 开源复现与结果报告

[开源复现](../GLOSSARY.md#开源复现)首先指对同一份已保存的候选交付物重新验收：
使用规定的输入、初态和独立判据，在声明范围内得到与 Spectre 一致的通过或失败判断。
不同后端不要求逐采样点完全相同，但必须满足同一组行为要求和误差限制。
重新调用模型生成交付物是另一项实验，不能与重新验收已有提交混为一谈。

正式发布按完整验收环境的依赖分为两集，分别报告题目数、成绩、工具版本和复现范围：

| 集合 | 发布要求 |
| --- | --- |
| 公开主集 | 不依赖商业工具即可重新验收；具备开源环境与 Spectre 的判分对照证据 |
| Spectre 扩展集 | 完整验收仍依赖 Spectre；公开可分发的任务、判据和运行说明，明确商业依赖 |

公开主集的判分对照应覆盖参考解、校准用错误版本和实际模型提交，检查错误放行与错误拒绝。
对照证据须绑定已测源码、配置和版本，不将有限样本的一致性宣称为任意提交的保证。
如果原任务需要实际器件电路验收，只在简化的电压环境通过不能证明原任务已经可以开源复现。
集合归属随版本固定；EVAS 补齐能力后，完成对照验证才能在后续版本中调整归属。

工具依赖分组参考 CVDP 的官方 `commercial` / `no_commercial` 数据发布方式，见
[数据说明](https://huggingface.co/datasets/nvidia/cvdp-benchmark-dataset/blob/main/README.md)。
[CVDP 论文](https://arxiv.org/html/2506.14074v1#S3)说明部分验证任务需要商业工具；
这不等于已经证明同一提交在不同后端上的判分一致，后者需要本项目独立验证。

## 从开发问题积累候选

[CANDIDATES.md](CANDIDATES.md) 记录开发中发现的问题及可能形成的建模任务。
先保留最小触发条件、独立预期、实际失败和证据；后续再集中做题目改造、评分和环境适配。
记录候选不自动创建 Harbor 目录，不增加正式题目或评分分母。
已经存在的振荡器题目是候选原型，仍需按登记表完成正式改造审阅。
开发、验证和 review 入口都执行这项记录规则，具体步骤见
[协作流程](../docs/contributing/validation.md#development-bench-candidates)。

[任务设计稿](examples/README.md) 给出六类方向：真实电路闭环校准、从数据建立模型、
故障修复、功能扩展、测量工具及仿真优化。每份说明题面、输入材料、交付物、
独立 checker 和落地缺口；这些设计稿尚未实现与验证，不计入当前六道可运行初筛题。

## 任务结构

任务放在 `benchmark/tasks/<task-id>/`。每个任务使用以下结构：

```text
benchmark/tasks/<task-id>/
├── instruction.md
├── task.toml
├── environment/
│   └── Dockerfile
├── solution/
│   └── solve.sh
└── tests/
    └── test.sh
```

| 文件 | 用途 |
| --- | --- |
| `instruction.md` | 说明建模要求、可用输入和完成条件 |
| `task.toml` | 配置任务信息、运行资源和时间限制 |
| `environment/Dockerfile` | 建立任务使用的工具与输入环境 |
| `solution/solve.sh` | 执行参考解，用于验证任务和评分程序 |
| `tests/test.sh` | 检查提交的模型，并输出评分结果 |

本项目的任务随任务保存参考解。Harbor 的结构和环境选项见
[官方任务说明](https://docs.harborframework.com/core-concepts/tasks/overview)。
评分程序按 Harbor 约定写入 `/logs/verifier/reward.txt`，或使用其支持的 `reward.json` 格式。

## 共享评分程序

[checkers/spectre_waveform.py](checkers/spectre_waveform.py) 是六题共用的评分源码。
[任务生成器](../experiments/va_screen/build_tasks.py)将它复制到每题的 `tests/verify.py`；
任务运行时执行该副本，`tests/cases.json` 保存各题的网表、独立期望值与容差。

修改共享源后，需要同步受影响的执行副本，并重做其参考解和错误版本校准。
生成器会重建全部六题文件，运行前应保留正在修改的任务。提交前使用
[身份检查](../experiments/va_screen/README.md#身份与再校准)确认源、副本及校准记录一致。
校准通过证明这些已测条件，不能证明评分程序覆盖任意错误实现。

[checkers/triangle_oscillator.py](checkers/triangle_oscillator.py) 单独负责振荡器修复题。
它使用正速度的分段解析积分和三角波折返关系；固定题目配置与错误版本校准见
[来源和验证边界](tasks/va07-triangle-repair/SOURCE.md)。无需 Spectre 的检查器回归：

```sh
python3 -B -m unittest discover -s experiments/backends/dvs2-spectre-validation -p test_triangle_oscillator.py -v
```

当前 EVAS 的本地接入验收入口是 [triangle_evas.py](checkers/triangle_evas.py)，
通过操作者指定的 circuit harness 执行，仅覆盖 `constant-tighter` 开发配置。
[调用方式、配置映射与未完成的负例验收](tasks/va07-triangle-repair/SOURCE.md#local-evas)
由该任务维护；原 Spectre verifier 和正式评分入口保持不变。

## 环境与结果

每个任务在自己的 `environment/` 中声明运行环境。
当前使用固定 digest 的 Python 基础镜像与远端 Spectre verifier；
任务镜像本身不包含商业仿真器，运行时必须按初筛说明指定 verifier。
镜像应记录依赖版本和构建方法；执行记录应保存实际使用的镜像身份。
完整运行日志与临时输出放在 Git 忽略的 `runs/` 中。

Benchmark 评分与 [EVAS 正确性验证](../evas/validation/README.md)分别维护和报告。
EVAS 的构建与运行方法见 [仿真器说明](../evas/README.md)。
