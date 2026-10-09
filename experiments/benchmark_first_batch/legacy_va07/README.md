# VA07 入口迁移与重新校准

本目录只准备候选和检查执行边界，不实现远端生命周期。实际运行由首批公共
`runtime.py` 和既有 circuit harness 执行，协调者限制 Spectre 总并发。

`first_batch_triangle.evaluate` 调用原 `triangle_oscillator.evaluate`。
只有 `BehavioralRejection` 转为 `passed=false`；结构错误仍向公共执行层传播。
原数学、容差、参考源码以及 `tests/cases.json` 的全部字节保持不变。
观察信号 `ctl/z/count` 声明在新 `contract.json` 中，公共执行层在内存中补全映射；
三个电压均以已接地的 `r` 为参考。旧 EVAS frozen cases 身份因此不变。
任务中的 canonical 副本位于 `tests/triangle_oscillator.py`，而非新的入口 `verify.py`。

在仓库根目录准备六份候选：

```sh
python3 -B experiments/benchmark_first_batch/legacy_va07/prepare_candidates.py \
  --output runs/va07-new-candidates
python3 -B -m unittest discover \
  -s experiments/benchmark_first_batch/legacy_va07 -p 'test_*.py' -v
```

生成器直接复用原 `oscillator_compatibility.py`，不改写负例语义。
`plan.json` 绑定原生成器、参考、canonical checker、cases 和每份候选源码的 SHA-256。
计划包括参考的八个原条件、四份历史负例各一个原条件，以及一份 product-guard
等价实现的两个原条件，共十四个条件。后两项是同一源码的两种刺激。
生成器的 `cases` 动作只重建原配置，不重建 Harbor 入口，因此无需改动原生成器。

协调者同步公共 runtime 后，逐候选使用已有打包命令，并按 `plan.json` 的 `cases`
重复传入 `--case`；输出目录必须全新：

```sh
python3 -B experiments/benchmark_first_batch/runtime.py prepare \
  --task benchmark/tasks/va07-triangle-repair \
  --candidate runs/va07-new-candidates/reference/dut.va \
  --output runs/va07-new-reference-package \
  --harness-checkout /path/to/circuits/harness
```

`prepare` 只冻结源码与逐条件包，不调用 Spectre。每个包保留原条件数值与网表，
公共执行层绑定完整原 cases 和新 contract 身份。实际校准仍需八个参考条件和四个
负例条件的新归档；旧 EVAS 构造波形与本目录单元测试不能替代这些证据。

当前任务和旧支持文档未新增 Spectre 或 EVAS 通过结论。历史 actual Spectre 结果
可用于核对候选身份；旧 raw 波形尚未恢复，不能声称已用当前入口重新评分。
