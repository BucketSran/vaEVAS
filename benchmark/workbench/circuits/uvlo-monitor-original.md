# 原创 UVLO 及拟建复位控制链

已存在的资产是 [repair-uvlo-recovery](../../tasks/repair-uvlo-recovery/SOURCE.md) 中的单模块电压监控器，来源组沿用 `uvlo-monitor-original`。文件身份与本轮阅读范围见 [行为资产来源](../sources/vaevas-behavioral-seeds.md)。

| 部分 | 已有或拟建 | 验收作用 |
| --- | --- | --- |
| UVLO | 已有 starter、参考与单模块合同 | 连续资格、迟滞、复位及旧 deadline 取消 |
| reset-release | 拟建 VA 模块 | 只有 power-good 满足公开条件后释放系统复位 |
| enable-gate | 拟建 VA 模块 | 由复位/使能决定下游开始工作 |
| 多模块错误起点 | 尚未建立 | 让短暂电源扰动引起可观测错误启动，同时保留正常运行与恢复 |
| 系统 checker | 尚未建立 | 由输入电压和控制序列独立计算资格、复位和启动时刻 |

原错误为人工构造的语义故障，没有器件实测缺陷的来源。多模块版本必须增加可观察的模块协作，不只是把原文件拆开。第一阶段全部为 VA，实际器件比较器属于后续范围。当前没有新系统运行或校准证据。
