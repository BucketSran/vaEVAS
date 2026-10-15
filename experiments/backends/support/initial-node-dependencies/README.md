# 初始化节点依赖的三个有限对照

三个微例检查 `initial_step` 读取电压前，驱动节点及其初始状态是否已经确定。本次固定 EVAS v4 内核与同源码 Spectre 21.1.0.509.isr12 对照全部通过。它们只证明下表三例，不证明原 MUX 任务通过，也不新增 Q 资格。

| 目录 | 独立常数答案 | 为什么得到这个答案 |
| --- | --- | --- |
| [initial-transition](initial-transition/tb.scs) | ctrl=1 V，y=1 V | 驱动初态 s=1，transition 初值为 1；负载读 ctrl>0.5。 |
| [initial-coupled](initial-coupled/tb.scs) | ctrl=1 V，y=1 V | ctrl=0.5a+0.5、a=0.5ctrl+0.5，联立得到两者为 1；负载再采样。 |
| [initial-nonground-state](initial-nonground-state/tb.scs) | aux=1 V，ctrl=2 V，y=1 V | aux=1 使驱动初态 s=1，ctrl-aux=s；负载读 ctrl>1.5。 |

[固定判据](case.json)预先采用 1e-9 V 绝对门槛。每个后端的所有实际导出点都独立检查上述答案；0、0.25、0.5、0.75、1 秒必须精确存在。只在时间完全相同的点配对，不插值，不排除事件窗口。每例 EVAS 有 13 行、Spectre 有 19 行；五个共有强制点的最大后端差为 0。全部原生点的最大数学误差为 2.23e-16 V，来自 coupled 参考的 ctrl。缺零时刻、相邻浮点替代、旧初始化状态和非有限值四个负控均被拒绝。

[紧凑结果与身份](summary.json)记录模型、SCS、PSF、执行记录、Python wrapper、固定内核和编译快照的哈希。各目录的 `dut.va` 与 `tb.scs` 是实际参考执行输入的逐字副本，EVAS 使用相同文件，没有删除 strobeoutput 或改写刺激。wrapper 来自单独识别的 SCS 入口版本，内核固定为已验明的 `initial-final-v4-debug-kernel`；不能把这个组合说成最终整合版本。

[复算脚本](pair.py)仅依赖 Python 和 EVAS Python 包。给它 `--python-root`、`--kernel`、`--kernel-receipt`、`--reference` 和 `--output`；reference 指向本地 `joint-raw`，receipt 指向保留的 `FINAL-V4-RECEIPT.json`。脚本核对同源输入和内核身份，重新执行 EVAS，并读取原生 PSF 复算全部判据。完整响应、原始 PSF、执行命令及编译来源保存在本地任务目录 `directed-closure/initialization/reference-pair-v4` 和相邻 reference/initialization 归档中。公开文件没有商业参考输出或内核下载，因此不构成公共独立重现数据集。

## 当前 main 的整合复验

主线程在 `146ea2ed` 上仅加入受审初始化代码后，重新构建并执行同一三例，复用已核对身份的实际 Spectre 原生参考。新旧结果分别保留在 [main 整合收据](summary-main-integration.json)和上方 v4 收据。三个模型的全部原生值及五个精确强制点仍满足原 1e-9 V 要求，三例的有限配对最大差均为零。新内核 SHA 为 `6bc62d6e144fd737f93e02d9e857f8417d0d41203e68f8bb9a4bb62c66f5f218`；这不是原 MUX 整题验收。

`pair.py` 只将内核身份说明改为读取所给收据，未修改数学答案、观察范围或门槛。首次本地复验误用了未失效的旧构建缓存，已保留失败日志；触发真实重建后才产生这里的新收据。
