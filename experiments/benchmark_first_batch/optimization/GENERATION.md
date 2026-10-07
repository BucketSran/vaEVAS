# 正式任务生成的准入门槛

`generate_admitted_tasks.py` 已准备VCO/flash/power/SAR/UART五个工程合同，尚未运行生成
任何正式目录。它只接受人工已review的admission配置及实际五对配对分析；不因候选存在
或单轮快就立题。配置示意如下，值保持pending，不能直接执行：

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
        "experiments/benchmark_first_batch/optimization/second_waveform_replay.json",
        "experiments/benchmark_first_batch/optimization/third_calibration.json"
      ]
    }
  }
}
```

准入校验包括：actual分析kind、五对AB不漏、同host/原生版本/网表/判据/线程参数、
baseline/reference当前源码身份、全部功能条件两侧通过、所提门槛确由actual中位数和
逐对数据支持。旧失败power源码不符合当前baseline身份，不会进入准入分母。没有
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
评分校准，再做Agentic；该生成器不越过这些交付步骤，也不自行push/PR。
