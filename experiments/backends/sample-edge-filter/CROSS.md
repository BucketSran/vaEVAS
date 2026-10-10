# 滤波输出触发 cross

**四类组合已能按原工程预算运行，但还不能承诺任意近根查询都成功。**
本批把采样、保持、边沿和一阶滤波继续接到 `cross`，由穿越事件更新计数器并采样输入。
实现基于已合并的 #124、#129；新支持在 [PR #131](https://github.com/BucketSran/vaEVAS/pull/131) 交付，尚未合入 main。
[紧凑收据](filter-cross-receipt.json)保存版本、完整分母、设置、失败与材料身份。

## 实际结果

2026-10-11 在服务器运行同一份 VA 和刺激，四条件、四档设置，Spectre 与 EVAS 各 16 次。
原 SEF 标准保持为输出 **100 µV**、输入 **10 nV**、事件观测 **±5 ps**。
计数、顺序、采样值、所有原生记录上的边沿与滤波输出都要满足要求。
这批采用原组合预算，不与总表中更严格的八个新精度用例混算。

| 条件 | 滤波穿越次数 | EVAS 工程检查 | Spectre 工程检查 | 首个通过档的 Spectre 最大滤波误差 |
| --- | --- | --- | --- | ---: |
| 周期采样 | 2 | 四档通过 | 收紧容差后通过 | 0.457 µV |
| 时钟采样与复位 | 4 | 四档通过 | 收紧容差后通过 | 0.457 µV |
| 中断未完成的边沿 | 4 | 四档通过 | 收紧容差后通过 | 0.331 µV |
| 双实例、不同参数 | 每实例 2 | 四档通过 | 收紧容差后通过 | 0.300 µV |

EVAS 为 **16/16**；Spectre 为 **8/16**，四个基础档和四个仅缩步档的穿越时刻或观测区间超出 5 ps。
按执行前的档位顺序选取，四条件都选中“只收紧容差”档。其最大穿越采样值误差为 0.645 µV。
这些是相对独立解析答案的有限点误差，不是全时域上界，也不是两端逐点差值。

另一个更严格的检查要求每个请求时刻都能在原生记录中找到，时间只允许 16 ULP 的表示余量。
按该检查，Spectre 原始综合成绩仍为 **4/16**，不能改写为 16/16。
部分记录离请求时刻约 1.25×10⁻¹⁶ s。它们仍按实际时刻参加工程检查，没有移时或拿邻近行代替。
时钟复位条件虽然通过工程检查，但尚未通过这项严格观测检查。

## 精度设置

| 档位，按此顺序选取 | 请求 reltol | vabstol | Spectre iabstol | maxstep |
| --- | ---: | ---: | ---: | ---: |
| base | 1e-5 | 1e-9 V | 1e-13 A | 31.25 ns |
| tol | 1e-8 | 1e-12 V | 1e-15 A | 31.25 ns |
| step | 1e-5 | 1e-9 V | 1e-13 A | 3.90625 ns |
| both | 1e-8 | 1e-12 V | 1e-15 A | 3.90625 ns |

Spectre 为 **21.1.0.509.isr12**，使用 `traponly`、`errpreset=conservative`。
实际瞬态 `reltol` 是请求值的十分之一，已由日志与 PSF 共同确认。
EVAS 接收表中 `reltol`、`vabstol`、`maxstep`，不声称支持 `iabstol` 或可选积分方法。
其强制观测记录来自已接受状态，不能把两端内部参数含义当作等价。
原生导出采用 17 位有效数字，不压缩记录。

## 修复依据与剩余限制

旧版本拒绝把这个滤波历史用作穿越判据。现在用滤波方程
`y′ = (gain·u − y) / τ` 同时包围电压和导数，交给现有根定位和事件事务。
事件后安装新边沿时，滤波电压连续；未来穿越仍重新预测。
回看旧时刻必须同时读取旧滤波状态和旧边沿，不能混用新目标。

查询落在根包围内时，新增只读检查用事件前的历史判断阈值差的符号。
能证明正负就选择对应阶段，不能证明就继续拒绝。
独立检查了四条件共 28 个根前后 `10⁻¹⁹ s` 的查询，计数方向正确；增加查询不改变原结果或事件记录。

**原四个中心点请求仍被拒绝；复算四份 Spectre 完整原生时间网格也全部被拒绝。**
例如在 `7.596128058938788 µs`，EVAS 的阈值差包围约为
`[-1.92×10⁻¹⁴, 1.79×10⁻¹⁴] V`。这个范围包含零，无法证明计数取事件前还是事件后。
Spectre 原生记录确实含此时刻；它的滤波数值仍在阈值上方约 0.256 µV。
这是 EVAS 的精度恢复／查询能力限制，不能记作已解决，也不能靠照搬 Spectre 的计数来解决。

工程网格保留旧 SEF 的全部边界点，并在每个新增根两侧加入 ±2 ps、±4 ps。
中心点探针和原生网格失败独立保留，不计入工程通过，也没有获得 SEF-TIMER-18 的例外。
回调反过来修改滤波输入、任意多历史反馈、高阶级联和滤波外再包 `sin` 等写法不在本批支持中。
数学规则见[算子手册](../../../evas/docs/math/operators.md#transition-filter)。

## 复验与材料

[独立契约](../../../evas/validation/sample_edge_filter/README.md#filter-cross)固定四类模型、解析答案与拒绝边界。
校准既要接受独立答案，也要拒绝漏事件、重复事件、错误采样、超差和缺失边界观测。
如果未来用例把根放在解析分段端点，当前根答案生成器明确拒绝，须先补该类答案，不能静默漏算。

```sh
python3 -B -m unittest discover -s evas/validation/sample_edge_filter -v
python3 -B experiments/backends/sample-edge-filter/cross_run.py freeze runs/new-cross/inputs
python3 -B experiments/backends/sample-edge-filter/cross_run.py run runs/new-cross/inputs runs/new-cross/spectre --backend spectre --profile /path/to/spectre-profile.json
python3 -B experiments/backends/sample-edge-filter/cross_run.py run runs/new-cross/inputs runs/new-cross/evas --backend evas --profile /path/to/evas-profile.json
```

实际运行串行，单阶段 90 秒、单线程、4 GiB 内存、32 MiB 输出文件；未运行另两个开源后端。
原始资料保留在项目 `runs/filter-cross-20261010/`，属于 **local-only**。
仓库只保存可复用模型、判据、执行工具与紧凑收据；哈希不代表原始数据已公开。
新增相位判定后重放 EVAS，并复用模型、刺激和设置未变的 Spectre 实测，具体身份见收据。
