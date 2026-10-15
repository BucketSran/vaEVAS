# 隐式 DAE：固定 timer 后保留物理历史

原模型在 .5 s 改变积分速率后，EVAS 候选保留原积分状态并继续求解。与实际 Spectre 的9个原生点比较，y 最大差 **62.41 nV**，低于实现前固定的100 nV外部门槛；w 最大差2 fV。这里只有有限点数值结论，没有新增 Q、精确回调时刻或一般 DAE 事件支持声明。

## 检查什么

原模型满足 `z=y+y²`、`z'=rate*(1+2y)`、`z0=.3125`，采用初始 y=.25 的局部正规分支。相同 z 也对应 y=-1.25，不能宣称全局唯一。对选定分支求导得 y'=rate，因此在 .5 前 `y=.25+t`，rate 从1改为2后 `y=.75+2*(t-.5)`。独立积分 w 从3出发，答案始终为 `3+t`。在事件处应保留 z=1.3125 和 w=3.5，而非重新应用原 IC。

`original/dut.va`、`tb.scs` 是原冻结反例的原样副本。两端均使用该 VA、刺激与容差请求；EVAS 使用自己的认证方法。当前实现只覆盖精确固定 timer 改变保持 forcing/步长参数。一般 cross、非精确事件窗、约束跳参、复位和任意代数分支选择仍不由这个实验证明。

固定分母为3个模型、每个模型2个后端配置。正例只含1个模型；另2个是负控制，分别判断，不能合成“全部配置通过”。每份 Spectre 保存9行；正例9个指定时刻全部保留。两后端先各自核对独立答案，再按同一100 nV门槛比较，不插值、不排除事件窗口。

| 模型 | EVAS 候选 | 实际 Spectre 及限制 |
| --- | --- | --- |
| 原模型 | 完成，9个指定点满足数学及配对门槛 | 9个原生点齐，y 对答案最大误差62.41 nV |
| 奇异初态 z0=-.25 | 初始根认证拒绝 | rc0、9点接近 y=-.5 平衡；F_v=0，不提供 index-one 唯一性证书，不能记为通过 |
| .5 时参数改变代数约束 | 结构拒绝，尚无分支重选 | rc0但有 Newton 不收敛、SPECTRE-17087 断点被跳过；.5 点缺失，仅保存 .5000000000020149，不能记为通过 |

最后一项若保留原 z(.5)=1.3125 且 shift 从0变2，则应有 `y+y²=-.6875`，没有实根。参考的其余点接近旧 rate1 流；原 VA 没有导出 rate、shift 或积分内部状态，不能反推出其隐藏处理。日志片段和缺点在 compact records 中保留，没有要求 EVAS 模仿此恢复路径。

## 设置与证据范围

实际 Spectre 为21.1.0.509.isr12，PSF读回 reltol=1e-9、vabstol=1e-9 V、iabstol=1e-12 A、maxstep=1 s、traponly、moderate、lteratio=3.5、relref=sigglobal，stop=1 s。EVAS 原请求为 vabstol=1e-9 V、reltol=1e-9、max_step=1 s；`$bound_step(.0625/rate)` 仍来自原 VA，不把 Spectre method/preset 视为 EVAS 等价控制。事件前后内部网格和失败回退另由实现回归检查，九个输出点本身不能证明内部步长。

[records.json](records.json)只保留实际原生 PSF 十进制 token、EVAS 同点 binary64 十六进制值、实际诊断与选定设置，数值可无损重读。[result.json](result.json)是 checker 重算的摘要。[receipt.json](receipt.json)给出输入、候选源码、固定内核、工具、完整输入/输出 inventory 及原始资产的散列和可用性；包内 `compact_schema_version=1` 是本目录自己的数据格式，不是模拟器 IR 或原始收据 schema。

候选以 base `4e04ec77` 加收据中列出的源码散列标识，运行核为固定 release；不是合并或发布状态。完整 PSF、日志、构建、执行包及工具配置仍在收据标明的 local-only 归档，散列不是下载地址。这里没有复制私有 profile、机器配置或完整原始波形。公开包可复核这些 compact 有限记录，不能从中完整重演商业 Spectre 执行。

原 VA 未增加回调打印。timer 请求、strobe 点和事件后的电压不证明 Spectre 内部精确回调时刻或同刻次序；PSF十进制导出也未新增格式校准。因此这些记录不授予 Q 或全时域逐点正确性。

## 本地重算

以下命令从仓库根目录运行，只需 Python 3.10+ 标准库，不调用内核或 Spectre：

```sh
python3 -B experiments/backends/implicit-event-restart/check.py
python3 -B -m unittest discover -s experiments/backends/implicit-event-restart -p 'test_check.py' -v
```

checker 验证包内保留文件散列，按独立分段答案重算正例，保留两类负控制，并核对缺点、设置、事件状态及六行后端矩阵。校准实际执行接受和拒绝控制，包括独立手算样点、超差、配对单独超差、缺首点/事件点/终点、重复或乱序点、负控误标、错误诊断、超时、丢失 warning 和资格冒升。运行结果见 [calibration.json](calibration.json)。这次整理是对已完成运行的重分析，不是新的 Spectre 实验，也不改变原历史判据或分母。
