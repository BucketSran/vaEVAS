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
每题reference和四个可编译语义错版需分别送现有circuit harness，
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
