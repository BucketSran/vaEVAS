# 四后端起步试点

2026-09-27 的试点比较了八张起始案例卡、15 个条件在四条链路上的行为：
Spectre、旧 EVAS 0.8.7、OpenVAF-R＋ngspice、Gnucap＋modelgen-verilog。
模型、刺激和数学答案固定，后端只适配调用与输出格式；本轮没有修复仿真器，也没有做速度排名。

## 实验范围与结果

每个条件运行基础档、细化档，共 **120 条配置记录**。
实际启动 114 次仿真；6 条配置因共享源码的编译失败未启动，失败仍保留。
结果与方法审查见 [RESULTS](RESULTS.md)，后续 20 个诊断探针见 [DIAGNOSIS](DIAGNOSIS.md)。

输入使用外部 PWL，演示尺度为 `S=1 V`、`T=1 μs`，停止时间 `4 μs`。
两档请求的输出间隔/最大步长分别为 `1 ns`、`0.1 ns`，并记录每个后端实际生效的设置。
设置名称或数值相同，不代表各后端提供相同精度。
完整执行前约定保存在[冻结原协议](../../evas/validation/versions/v1/run-protocol.original.md)。

试点发现了原低通数组语法问题和 Gnucap 数值选项遗漏；修订作为新身份另行执行，
没有回写本批输入与成绩。后续扩展为原 31 条件，见[四后端历史矩阵](../dvs2-four-backend-validation/README.md)。

## 目录中的工具

| 文件 | 用途 |
| --- | --- |
| [suite.py](suite.py) | 从案例卡生成条件、参数、PWL 刺激和网表外壳；后续实验复用此入口 |
| [run_remote.py](run_remote.py) | 在已经配置的四后端环境编译、运行并保存阶段记录 |
| [analyze.py](analyze.py) | 对导出波形检查输入、状态、边沿和解析答案 |
| [report.py](report.py) | 汇总结果与图表；绘图另需 matplotlib |

共同 VA 源码在 [validation/cases](../../evas/validation/cases/README.md)，
独立契约在 [CASE_CARDS](../../evas/validation/CASE_CARDS.md)。
全部观察满足仅表示本批有限观测通过；完整事件历史、沿长指标和观察不确定度尚未取得正式资格。

## 如何复核

从仓库根目录运行检查器校准，无需后端：

```sh
PYTHONPATH=experiments/dvs2-starter-pilot python3 -B -m unittest discover \
  -s experiments/dvs2-starter-pilot -p test_analysis.py -v
```

持有原始证据时，可在副本上运行 `analyze.py <root>`，再用
`report.py <root> --output <curated-output> --plot` 重建报告。
`analyze.py` 会写入分析文件，因此必须保留原归档，使用副本或新目录。

公开材料包含协议、脚本和整理结果。完整原始日志、私有容器辅助模块和商业后端配置
仅本地保留；`run_remote.py --help` 说明接口，但从空环境不能一键复现旧执行。
新执行需要具备对应安装和冻结清单，并记录自己的源码、工具与输出身份。
