# ajcci：SKY130 可编程 POR

固定来源：[ajcci/sky130_ajc_ip__por](https://github.com/ajcci/sky130_ajc_ip__por/tree/db8745ef4d7d85a1852fc60c251ba34c6cebe497)。
版本：`db8745ef4d7d85a1852fc60c251ba34c6cebe497`。
许可：[Apache-2.0](https://github.com/ajcci/sky130_ajc_ip__por/blob/db8745ef4d7d85a1852fc60c251ba34c6cebe497/LICENSE)，使用资产时一并保留该版本 NOTICE。

## 实读范围

2026-10-10 的已有静态阅读：README、LICENSE/NOTICE、模拟原理图、数字行为及 XSPICE 模型、CACE 配置，以及 transient、trip_up_down、response_time、DC 测试和对应测量逻辑。没有重新执行源工程，保存的波形和图不算本轮复现。

- [transient.spice](https://github.com/ajcci/sky130_ajc_ip__por/blob/db8745ef4d7d85a1852fc60c251ba34c6cebe497/cace/transient.spice)：AVDD 用 2 ms 升到 3.3 V，随后降到 2 V、保持约 200 μs 再恢复；适合上电、欠压与恢复场景。
- [trip_up_down.spice](https://github.com/ajcci/sky130_ajc_ip__por/blob/db8745ef4d7d85a1852fc60c251ba34c6cebe497/cace/trip_up_down.spice)：上升、下降触发点和迟滞测量。
- [response_time.spice](https://github.com/ajcci/sky130_ajc_ip__por/blob/db8745ef4d7d85a1852fc60c251ba34c6cebe497/cace/response_time.spice)：实际计时采用振荡器首次上升事件到 POR 上升；不等同于供电越过门限到复位释放。
- [CACE 配置](https://github.com/ajcci/sky130_ajc_ip__por/blob/db8745ef4d7d85a1852fc60c251ba34c6cebe497/cace/sky130_ajc_ip__por.txt)：相关条目设为 skip，不能把默认工程视为已通过。

## 改题时保留的缺口

原工程有模拟电路、数字计时、可编程门限和 `force_pdn`。模拟 deck 引用 XSPICE 数字模型，完整依赖与固定后端尚待整理。正常模式和缩短计时的测试模式需要核对 README、时钟及数字常量。

`force_pdn` 现有激励只在 1 μs 设置工况值，没有完整动态休眠→唤醒验收。第一版 POR 草案不默认加入该要求。具体可复用资产及配套 VA 模型状态见 [电路记录](../circuits/sky130-ajc-por.md)。
