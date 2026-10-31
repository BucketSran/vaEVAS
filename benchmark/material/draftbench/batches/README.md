# 草稿题包批次

每批保存实际题包，批次 README 作为续聊和人工审核入口。共用电路仍在
[circuits/](../circuits/README.md)，56 题的功能覆盖、同源变体和缺口仍由[总览](../TASKS.md)维护。

| 批次 | 题包数 | 当前工作 |
| --- | ---: | --- |
| [v2-01](v2-01/README.md) | 37 | 原五类首批；保留原实现与作者记录，等待本版题目审核 |
| [v3-01](v3-01/README.md) | 19 | 原扩充批；保留原实现与作者记录，等待本版题目审核 |
| [r01-sampling-01](r01-sampling-01/README.md) | 2 | ideal 设计与实现齐备，作者校准待解决后端缺口；有限采集合同保留，其余 R01 方向仍在功能族资产中 |
| [harbor-batch2-01](harbor-batch2-01/README.md) | 0 | 第二批23道v2/v3草稿的迁移集合（题包仍在v2-01、v3-01，不另计）：已迁20（A组复审关闭到只剩F01；B组审核发现全部关闭；按用户决定新迁071、370、online-gain、segmented，独审11条在修），3道converter记为segmented的变体 |
| [r01-sampling-02](r01-sampling-02/README.md) | 1 | P0 试点：C056-S1 已建（implementation，未仿真）；C056-R1 判与 S1 重复，用户已确认不建 |
| [r06-filter-01](r06-filter-01/README.md) | 3 | P0：试点 C260-S1，铺开后 C264-S1、C266-S1 已建（均 implementation，未仿真） |
| [r03-power-01](r03-power-01/README.md) | 1 | P0 试点：U18-S1 已建（implementation，未仿真） |
| [r04-clock-01](r04-clock-01/README.md) | 2 | P0：试点 U15-S1，铺开后 U16-S1 已建（均 implementation，未仿真） |
| [r08-comparator-01](r08-comparator-01/README.md) | 1 | P0：C176-S1 已建（implementation，未仿真） |
| [r09-adc-01](r09-adc-01/README.md) | 2 | P0：C105-S1、C109-S1 已建（implementation，未仿真） |
| [r06-equalizer-01](r06-equalizer-01/README.md) | 1 | P0：U17-S1 已建（implementation，未仿真） |
| [r01-sampling-03](r01-sampling-03/README.md) | 3 | P1（R01 族）：C061-S1、C057-S1、C067-S1 已建（均 implementation，未仿真）；独立审核 r1 的发现已在修正 r1 处理；修正 r2 补 C061 合法域一句与台架检查，同步决定单第 20、21、25–33 项的状态；修正 r3 写明 C067“vdd 不变”的门限，并按样板第 4c 节改三题的验证总时限，待复审 |

旧的 41 个题包已归入[历史题包](../../historyref/tasks/README.md)，不在这 58 个草稿的分母内。PR255 规划池新建的 P0、P1 题包也不计入这 58 个。
正式题集当前为空。批次名只表示建设范围，不表示审核认可；旧 v2/v3 题号保持不变。
按题录取后，原批次保留审核人、审核版本、结论与正式位置，不留下第二份有效题包。
录取与配置更新见[建设流程](../docs/evaluation.md#按批次管理与逐题录取)。
