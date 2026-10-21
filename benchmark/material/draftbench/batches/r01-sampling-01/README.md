# R01 采样第一批

本批有两份 R01 题包，不计入原 56 题。ideal 已从原电路重新编写草稿并完成本轮纯软件检查，数值域、边界与运行校准待定；basic 保留合同草稿。电路价值与分工见[R01 人工 review](../../circuits/r01-sampling/README.md#单模块当前判断)。

| 题目 | 内容与运行状态 |
| --- | --- |
| [ideal 理想跟踪保持](tasks/r01-spec-ideal/README.md) | 2026-10-21 运行链路增量：冻结 VA、原生 PSF 测量、有界执行与终评分数写入已实现，38 项纯软件检查通过，独审发现已修复。Spec 范围、边界和精度仍在用户讨论中，配置阻止启动；真实运行与校准未执行，保持 implementation、grading/runtime pending |
| [basic 有限采集](tasks/r01-spec-acquisition/instruction.md) | 参数已由 starter 移入题面，保留原数值与公开台架；尚缺新格式 gold 和完整验收 |

## basic 已有合同与运行状态

| 方面 | 当前事实 |
| --- | --- |
| 内容 | 全 VA 路线；方向已保留，2026-10-14 合同草稿仍待人工审核，未录取 |
| 作者执行与独立验收 | 已有公开材料；新格式完整环境、参考解、checker 和作者校准尚未完成 |
| Agentic 与后端 | 公开台架声明 Spectre；当前题包完整运行、EVAS 兼容和公开反馈迭代未验证 |

## basic 后续合同审核

先判断基础实现题的定位，以及行为范围和精度标准是否符合用途。2 mV 是对规定连续响应的实现误差，
不是要求采集结束时距输入只剩 2 mV；该标准的数值可行性尚待校准。

材料入口：[英文题面](tasks/r01-spec-acquisition/instruction.md)、[接口](tasks/r01-spec-acquisition/environment/starter/circuit.va)、
[公开台架](tasks/r01-spec-acquisition/environment/starter/testbench/tb.scs)、[合同与验收方案](../../circuits/r01-sampling/module/basic/README.md#有限采集建模题合同审核)。

## 后续执行

按[R01 本阶段安排](../../DISCUSSION.md#r01-本阶段安排)先收口 R01。各全 VA 题按应用与行为依据、gold、验收与题面完善的顺序建设，之后在获准执行时进行作者校准和首轮模型解题实测。记录通过情况、失败原因和迭代成本，作为后续难度设计的依据。

真实电路结合题在本阶段讨论清楚并写出 instruction 与 gold，暂不实际测试；尚未运行的 gold 不能登记为已校准。器件级建模研究在 11 月 DAC 投稿之后另行推进。

2026-10-19，先固化范式与静态 lint，再按本轮授权完成 ideal 题目设计和作者侧检查。EVAS 固定到已合入 main 的 `e2c7aac7`，未修改另一线程文件。正确候选的运行拒绝保留为环境缺口，不删用例或限制求解者写法来规避；详细状态与唯一证据见 ideal 题包。
旧格式材料继续保存在[恢复快照](../../DISCUSSION.md#整合与归档结果)，原记录不代表新版本验收。
