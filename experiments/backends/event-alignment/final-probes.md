# 最终两个单因素探针

Spectre 21.1.0.509.isr12 实际执行两个冻结配置，均取得波形。
原始归档 SHA256 为 `371a1e184ad96b39b83baaacd96f20d42d1340cb7888f95bebf8557a4570ca7d`，
原输出清单含 44 项；共同 API 校验整个归档的 63 个普通成员，含附带输入与收据。
原始材料为 local-only。复验入口先以共同 archive API
绑定固定归档和所有解包文件，再检查冻结源/网表 hash，才解析原生 PSF 和日志。
不插值、不补缺失行、不改变原判据。

## M1：求解收紧后的有限覆盖补齐

以已执行的 timer ttol18、solver-tight 原模型为基准，只把 Spectre maxstep
从 125 ns 改为 1 ns；VA、173 个指定查询、stop、其他设置和预算均保持原样。
该配置不是原 ttol18 基线的替代结果。

| 实际有限检查 | 结果 |
| --- | --- |
| Spectre 原生行数 | 10215 |
| 原指定查询覆盖 | 173 / 173，P |
| q/n/m 相对独立阶段和候选 EVAS | 全部原生行零失败，P |
| Spectre 相对精确独立积分 z 最大误差 | 3.72528619e-10 V |
| EVAS 相对精确独立积分 z 最大误差 | 1.42108547e-13 V |
| 实际 EVAS/Spectre z 最大差 | 3.72528494e-10 V，原 1 µV 预算内 P |

EVAS 实际重算全部原生时刻，保留原 max_step=125 ns、vabstol=1 µV、reltol=1e-8。
其他输出的最大直接差不超过 1.777e-15 V；sample/stamp 原 0.1 µV 预算同样满足。
独立答案是 `1e6*min(max(t-2e-6,0),6e-6-2e-6)`，按原 binary64 常量用精确有理数计算。
这里建立的是冻结新配置的有限原生与指定查询 P，不是连续域误差证书。
旧 ttol18 基线的 1.587 µV F、原 solver-tight 缺三查询的 I 均保留。
收紧求解控制使参考误差实际降到原预算内；没有为追随参考误差修改 EVAS 数值或预算。

## VCO：原 idtmod 返回量的低侧结果

原 `original--tight` 只在既有 `p=idtmod(...)` 之后加入四个根 ±2^-40 s
窗口内的普通 `$strobe`，打印同一个 p、abstime、V(phase)、V(out)。
没有第二个积分器、timer、cross、历史、步长约束或查询变化。

新旧完整 PSF 仅日期头一行不同；全部 32811 个原生时间及 ctl/freq/phase/out
逐字节相同。九条打印的时间回读为 binary64 后，逐条唯一匹配原生时间；
日志 phase/out 与对应 PSF 值逐值相等，没有最近点拼接。

在第一根左邻点 `1.6689300537109373e-6`，打印 p 本身为 0，
V(phase)=1.1102230246251565e-16；独立精确 phase=0.9999999999999999。
这排除仅端口求解或 ASCII 保存转换把高侧值变成低侧的解释。
差异已位于原 idtmod 返回量/历史求值层；本探针仍未暴露未包裹内部累加器，
不能据此确定专有积分/模运算的公式。

原 ordinary phase 最大差约 1 周，仍为 F；circular phase 最大差
4.441e-16 周、sine 最大差 1.610e-12 V 在原预算内。
原 22 个指定查询仍缺 11 个，覆盖仍为 I。日志不能补成 PSF 查询覆盖。
普通相位 1e-3 周、圆周相位 1e-3 周、sine 3e-3 V 的原判据均保留。

## 本地复验与交付边界

保留两个 collection（各自包含固定 `raw.tar.gz` 及已解包成员），从仓库入口执行：

```sh
python3 -B experiments/backends/event-alignment/final-probes/analyze.py \
  NEW_COLLECTION ORIGINAL_VCO_COLLECTION runs/final-probes-replay.json \
  --receipts runs/final-probes-replay
```

`NEW_COLLECTION` 对应本文的 371a…归档，`ORIGINAL_VCO_COLLECTION` 对应
[VCO 原四配置](vco-controls.md)的 287bf5bd018082e8928da9063de532e688080df4d47a85c135e0cf4e2e4d1613 归档。
需要本地已构建的 EVAS 内核，亦可传 `--kernel PATH`；入口不构建、不运行远端 Spectre。
[冻结输入](final-probes/manifest.json)和[逐项结果](evidence/final-probes.json)留在仓库；
完整原始输出和 EVAS request/stdout/stderr 留在 local-only `runs/`，不声称公开完整复现包。
原 VCO 四配置分析入口也接入同一个归档 API 和共享 PSF 读取模块；
重新读取后原全部科学字段逐项相同，仅新增来源绑定记录。

本次可交付的是极近混合事件的精确排序/有界闭包/回滚修复，以及冻结新 M1 配置
的完整有限对齐证据。原 C1 严格名义查询阶段 F、#79 stop=3 阶段 F、
原 M1 ttol18 电压 F、VCO ordinary phase F 和指定查询覆盖 I 仍未满足。
C1 在工程窗口内共享一个实际时刻解释全部原生消费者的 P 不替代原查询覆盖 I。

因此仍需用户明确验收范围：可以验收上述已完成修复并将旧严格边界作为保留的
开放问题，或坚持旧配置全部严格边界通过才验收 #108。后一个要求尚未达到。
本文没有自行批准版本例外，也不将 F/I 改记为 P。

[最终收据](evidence/final-probes-receipt.json)记录实际生效设置、内核/分析器 hash、完整 EVAS request/stdout hash 及归档 mutation 校准；VCO deck 的 reltol=1e-8 在 conservative 控制下实际生效为 1e-9，新旧配置一致。

EVAS 配对在消费 solutions 前通过公共 protocol 校验：实际 returned times 逐项等于 request，nodes/state names 对应 program，行数/列数及值均合法有限。对实际 10215 行 response 的错一 ULP 时间、错误节点次序、短电压行、非有限电压四个负控均在比较前拒绝；没有以请求时间重新贴标签来掩盖响应身份差异。

M1 的公开 VA 文本只去掉一个空行上的两个空格；manifest 分别记录公开文本和原执行 source hash。复验使用归档中的原 source，未改冻结执行输入或已跑判据。
