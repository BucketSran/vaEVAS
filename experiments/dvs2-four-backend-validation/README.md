# 原 31 条件的四后端对照

本目录记录 2026-09-28 在 thu-sui 完成的历史基线，运行编号
`dvs2-four-backend-20260928-01`。原 31 条件在四个固定后端、两档设置下形成
**248 条配置记录**，用于发现支持、数值和事件语义差异。
这里的 EVAS 是旧版 0.8.7；新版内核的验证另见[当前证据](../parallel-gap-integration/README.md#当前证据)。

## 结果概要

| 固定后端 | 基础档达标 | 细化档达标 | 两档均达标 |
| --- | ---: | ---: | ---: |
| Spectre 21.1.0.509.isr12 | 31/31 | 31/31 | 31/31 |
| EVAS 0.8.7 | 18/31 | 8/31 | 8/31 |
| OpenVAF-R＋ngspice 46 | 16/31 | 16/31 | 16/31 |
| Gnucap＋modelgen 2026.07.29 | 17/31 | 16/31 | 16/31 |

逐条件结果见 [MATRIX](results/MATRIX.md)，数据见 [CSV](results/matrix.csv)
和 [JSON](results/matrix.json)。达标表示满足固定有限观测判据；
完整连续时间观察资格仍为 **I（未决）**，不能据此排名整个仿真器或声称普遍收敛。
答案来自共同的独立数学关系，不以 Spectre 波形作黄金答案。

## 哪些是新执行，哪些是复用

本轮增加 130 条配置：EVAS 与 OpenVAF-R 各 34 条，Gnucap 62 条。
另外复用 Spectre 的 62 条，以及 EVAS/OpenVAF 各 28 条旧执行，共 118 条。
复用项按本轮判据重判，没有直接继承旧标签。

130 条新增配置中，104 条生成波形、18 条编译失败、8 条执行失败；
实际启动 112 次仿真和 34 个编译阶段。旧 `v5-main` 两档超时继续保留。
完整执行预算与复用条件见 [PROTOCOL](PROTOCOL.md)，身份和计数见
[RECEIPT](results/RECEIPT.json)。

## 工具与归因

[build_inputs.py](build_inputs.py) 固定输入，[remote.py](remote.py) 在既有环境串行执行，
[matrix.py](matrix.py) 统一分析，[audit.py](audit.py) 核对执行后的元数据与归档。
[audit.py](audit.py) 不参与数值判定。

[DIAGNOSIS](DIAGNOSIS.md) 记录追加的 15 个诊断探针，区分贡献、事件、调用形式、
复位和编译链路问题；诊断变体不替换原矩阵条件。主要失败仍保留如下：

## 未达标结果

下表的计数仍按“基础档 / 细化档”，每列各有 31 个条件；编译和执行失败没有被剔除。

| 后端 | 输出/历史违反判据 | 编译失败 | 执行失败 | 超时 |
| --- | ---: | ---: | ---: | ---: |
| Spectre | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| EVAS | 8 / 18 | 0 / 0 | 5 / 5 | 0 / 0 |
| OpenVAF-R＋ngspice | 5 / 5 | 9 / 9 | 0 / 0 | 1 / 1 |
| Gnucap＋modelgen | 12 / 13 | 2 / 2 | 0 / 0 | 0 / 0 |

主要新增证据如下；这里只报告已观察到的行为，不把诊断线索写成已确认的内部根因。

- **EVAS：** `v6-standard`、C2 在 lowering 阶段报告 `no_event_transition_ir`；
  D1 的两条件报告 `continuous_body_not_lowered`。E2、C1 和 `e1-aligned` 存在基础档达标、
  细化档违反事件历史的差异；例如 `e1-aligned` 细化档终点上穿计数输出为 0.1 V，合同要求 0.2 V。
  S1 两条件两档的最大解析误差均约 0.7 V，目标为 1 mV；D2 两条件两档则均达标。
- **OpenVAF-R＋ngspice：** E2、C1、C2 的共同采样器源码在 `or cross(...)` 组合事件处
  被编译器拒绝，共覆盖 14 条本轮配置。E1 三条件违反事件历史；D1 自由积分达标，
  持续复位条件的标志波形不属于合同允许的历史。标准低通、D2 和 S1 均在两档达标。
- **Gnucap：** D2 在 modelgen 阶段报告 `unresolved symbol: idtmod`，覆盖 4 条配置。
  C1 主条件不达标，交换实例声明顺序的条件两档达标；核对网表确认两者仅改变实例声明顺序。
  C2 基础档达标、细化档采样历史不达标，而低通中间节点两档均满足解析误差目标。
  D1 自由积分达标，持续复位条件违反电压历史。所有这些失败保留于矩阵。

104 份本轮可用波形都通过输入、时间范围、单调时标、最大观察间隔和有限值检查；
Gnucap 的零参考观察也全部满足阈值。因此没有被“观察不合格”替代的数值失败。
旧 EVAS/OpenVAF 的 56 条配置也按当前固定判据重判，不继承旧成绩标签。

## 复核

复核适配器（当前校准读取本地已归档的 Spectre 输入，需保留该私有证据副本）：

```sh
python3 -B -m unittest discover -s experiments/dvs2-four-backend-validation -p 'test_*.py' -v
```

持有三批私有原始归档时，可重新分析到一个不存在的新目录；不覆盖本目录中的结果：

```sh
python3 -B experiments/dvs2-four-backend-validation/matrix.py \
  runs/dvs2-four-backend-20260928-01 \
  runs/dvs2-starter-20260927-01/evidence \
  runs/dvs2-spectre-20260928-01 \
  runs/dvs2-four-backend-recheck
python3 -B experiments/dvs2-four-backend-validation/audit.py \
  runs/dvs2-four-backend-20260928-01 \
  runs/dvs2-four-backend-20260928-01.tar.gz \
  runs/dvs2-four-backend-recheck
```

本轮完成的是缺失基线补测。完整观察资格及依据这些结果修复 EVAS 属于后续工作。

<details>
<summary>实际设置、工具身份与原始归档</summary>

## 设置与证据

[设置回读审计](results/settings-audit.json)检查了 EVAS 26、ngspice 20、Gnucap 58 份运行日志。
ngspice 采用 `tran` 之后的最后一组 `option` 回显；之前的回显可能还是默认值。
Gnucap 日志确认 `short=1e-9`、`method=trap`、输出精度及两档容差。
EVAS 的日志确认请求值回显，不把这些值解释为已实现 SPICE 误差控制。
步长请求与实际导出间隔分别留在输入与分析结果中，不假定各后端设置含义等价。

OpenVAF 包由固定镜像和 `v24.0.2mob` 工件路径标识，但自身 `--version` 输出为
`OpenVAF-reloaded unknown`；EVAS 的 build revision 也为 `unknown`。
完整镜像身份、版本回显、源文件哈希和证据复用计数见 [RECEIPT.json](results/RECEIPT.json)。

- 本轮私有原始归档：`runs/dvs2-four-backend-20260928-01.tar.gz`，45,953,489 字节。
- 归档 SHA-256：`24d66162e7120e22a4b0ae4a863b747e7b97a3a64e2ca5cf7388f2ead4d0a09a`。
- 文件清单 SHA-256：`28d7ddbf9afb8d1dfc0952fa3904352eb6f74bf4a2d8bf02504da73092cdb82d`。
- 已逐文件校验本轮 1,662 个文件、旧试点 1,894 个文件和 Spectre 批次 1,216 个文件。

固定输入后，没有改变共享判定器、DUT、阈值或已完成的 v1/Spectre 归档；
[audit.py](audit.py) 是运行后元数据检查程序，不参与数值判定。

</details>
