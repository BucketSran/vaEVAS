# 动态辨识首批建设

五题是针对不同电路工作目标原创的行为辨识题，公开轨迹均标记`behavioral_synthetic`。
没有将厂商曲线、人工系数或参考VA执行包装成器件实测。
当前仅完成本地材料和行级判据测试，实际Spectre与Agentic状态以协调者收据为准。

各题生成器分别是`build_sh.py`、`build_sc.py`、`build_driver.py`、`build_comparator.py`、`build_pll.py`。
它们生成public数据、刺激网表与隐藏整实验合同，不调用模型API或仿真器。
`build_common.py`只负责包装与公开拟合代码的基础线性代数，不定义电路目标。
参考`fit.py`只读public观测，产生候选VA。原始隐藏系统系数不写入solution。

准备实际Spectre候选：

```sh
python3 -B experiments/benchmark_first_batch/identification/prepare_candidates.py
```

默认输出到ignored`runs/identification-candidates/<task>/<variant>/dut.va`。
每题reference和至少四个语义错版需分别送现有circuit harness，
协调者管理Spectre总并发4，不在这里建立另一套SSH编排。
task-local`circuit_task.py`与checker副本由协调者同步规范源码并绑定身份。

无需后端的判据行为检查：

```sh
python3 -B -m unittest discover -s experiments/benchmark_first_batch/identification -p 'test_*.py' -v
```

这些检查覆盖五题20个隐藏合同的正波形、局部错误、缺失/非有限观测、
比较器crossing遗漏/迟到和PLL正确频率但错误相位。
它们不能替代VA编译、Spectre数值校准或Agentic运行。

每题public selfcheck接受导出的time_s/out_V CSV，PLL还需tune_V。
公开CSV校准与终评分别维护，不能在解题时开放隐藏coefficients或case包。

SH 首次实际后端失败的可重放诊断见 `sh-v3-diagnosis.json` 与
`diagnose_sh_archive.py`。修正刺激后需重新准备候选并冻结新的任务、checker
和刺激身份，由协调者调度实际 Spectre；原归档不能算作修正版通过。

准备候选后，用协调者实际冻结的共享执行边界做静态校验：

```sh
python3 -B experiments/benchmark_first_batch/identification/static_check_candidates.py \
  --runtime /absolute/path/to/benchmark/checkers/circuit_task.py
```

`candidate-static-check.json` 保留一次27候选全部通过的来源哈希与运行时哈希。
这只证明 submission I/O 合同合规，不证明VA可编译或电路行为正确。
PLL参考与错版生成器使用2π数值字面量，符合共享边界禁止候选宏的规则。

SC保持判据覆盖每周期的高、低时钟相位，避免只在高相观测而遗漏低相清零。
PLL在完整实验上按声明的10 ns观测间隔检查out，压缩为`sample_grids`数组，
保留既定8 mV容差与独立解析目标，避免500 ns稀疏网格漏掉周期内纹波。
`low-phase-reset`和`grid-alias-ripple`行级回归逐一证明旧判据接受、修正版拒绝；
真实VA后端正负校准仍由协调者冻结并调度。公开观测数据不因这次判据修复改变。

`sc-full-hold-regrading.json` 对已归档的实际Spectre参考波形重评分，四实验均通过
新增高、低相保持要求。`regrade_archived.py` 要求旧目标、刺激和实际候选字节均未改变，
才允许添加sample grids后重评；不把重评分称为新的后端执行收据。
