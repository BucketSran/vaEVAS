# 正式任务生成的准入门槛

`generate_admitted_tasks.py` 已据独立review生成VCO/flash/power/SAR/UART五个正式资产。
VCO/power/SAR/UART配置在`admission_step_tasks.json`，Flash配置在
`admission_flash.json`。原`admission_proposed.json`和
`admission_flash_proposed.json`保留当时pending身份，不改写历史提案。生成器只接受
已review的准入配置及实际五对配对分析；不因候选存在或单轮快就立题。以下是pending
配置示例，不能直接执行：

```json
{
  "paired_evidence": "实际quiet配对分析.json",
  "tasks": {
    "optimize-vco-step": {
      "admitted": false,
      "metric": null,
      "max_median_ratio": null,
      "min_winning_pairs": null,
      "functional_evidence": [
        "experiments/benchmark_first_batch/optimization/raw_point_waveform_replay.json"
      ]
    }
  }
}
```

准入校验包括：actual分析kind、五对AB不漏、同host/原生版本/网表/判据/线程参数、
baseline/reference当前源码身份、当前独立evaluate.py与cases.json哈希绑定的实际PSF回放
全部功能条件两侧通过。热身与测量共12条记录各自绑定当前性能网表，并从原
attempts/records重算摘要与声明比较；所提门槛须由实际中位数和逐对数据支持。
旧失败power源码不符合当前baseline身份，不会进入准入分母。没有
原始actual证据或待定门槛时直接拒绝，先校验全部计划后才写目录，不覆盖已有任务。

实际通过review后才运行（读取本树已有共享runtime，或显式指定其路径）：

```sh
python3 -B experiments/benchmark_first_batch/optimization/generate_admitted_tasks.py \
  --admission /path/to/reviewed-admission.json \
  --shared-runtime benchmark/checkers/circuit_task.py
```

公开starter和visible网表只含合法原始基线，参考优化源码只在solution；题面明确电路
行为、独立容差、真实工作、原生性能比率/五对一致性及后端设置。测试保存全部功能
cases、基线、参考与至少3语义/无效优化负例，评分入口使用guard+同job重复求解。
没有把Dir存在、纯fixture或生成动作计作backend校准/Agentic完成。SOURCE明确Spectre
扩展集、商业工具依赖、原始波形保留与性能专用profile资源要求。

生成后由主任务更新首批inventory、同步METADATA、运行reference和负例的完整正式
评分校准，再做Agentic；该生成器不越过这些交付步骤，也不自行push/PR。当前正式参考15条件、
30个负例90条件及Flash合法二分替代3条件已完成实际执行与封存审计。参考15/15与
替代3/3通过，30个负例各至少一个条件被拒绝，36个变体全部满足预期，没有pending。
统计在[formal_calibration_receipt.json](formal_calibration_receipt.json)，范围说明见
[FORMAL_CALIBRATION.md](FORMAL_CALIBRATION.md)。它仍不代表Agentic完成。

执行资源已修正：harness私有profile收集硬上限256MiB，不能声明1GiB突破该上限。
采用256MiB/900s，paired完整PSF无损gzip、逐字节往返SHA相同后移除重复原件；主功能
PSF和所有源码/日志保留。压缩不进入solver计时。归档必须复核每份gzip及总大小。
早期源guard零分也必须包含core schema的candidate/cases/contract/checker/runtime/parser
哈希，使用这些真实受信文件的字节身份，不以缺省字符串伪造receipt。

正式评分采用step ratio≤0.1且5/5获胜，或Flash CPU ratio≤0.97且至少4/5获胜。
Flash事件内线性参考准入另有整体进程改善证据，该证据不是每个CPU满分候选的硬
门槛。旧二分实现实际通过CPU合同且功能通过，仍保留其旧端到端回退，归为
`equivalent_cpu_only`，不作负例。所有报告均须分开列CPU/steps与实际进程耗时。

封存审计使用当前受信任务文件，核对完整3条件清单、results/report结构值、每个归档
成员身份、主功能全部raw点和paired全部无损PSF，重新解析native/merged流并重算
性能结果。精简收据记录审计工具及数据身份；完整档案在ignored runs，本地回放
不是重新执行Spectre，也不证明未保存时间点的连续行为。

本次完整封存审计覆盖108个主条件和192次paired子求解。负例的90条件包括63个语义
失败、5个性能失败和22个局部通过；局部通过仍保留在分母中。审计核对最大归档与
封存成员字节数均低于256MiB，不把gzip压缩时间计入solver性能。
