# 来源与发布范围

同源组 adb-ldo-ota5，规格 #148。固定 ADB 提交972f7cd7c95381134387b250edf18f3bd23bdd25的参考晶体管电路，电路内容CC-BY-NC-4.0，原作者Analog Design Bench contributors。许可证与完整许可正文随公开资产分发。固定SKY130 PDK提交f62031a1be9aefe902d6d54cddd6f59b57627436，Apache-2.0。自有VA测量解与独立checker不取上游评分代码。外围网络与输入工况是注明的任务适配。

本题为Spectre扩展集，未提供经过校准的开源候选VA执行环境。原电路、适配差异、实际校准身份和许可依据见[路线记录](../../../../../../../experiments/benchmark_next/ldo/README.md)。341/372/340仅是后续控制素材，没有形成本题的新计数。

## 2026-10-29 vsource 写明 type 与 sinedc（typedc-sweep-r1）

项目协调方 2026-10-29 批准、Benchmark 维护方统一写入：题包里每一份网表副本（各 cases.json 的每个用例网表与全部 `.scs`），没写 `type=` 的 vsource 在 `vsource` 之后补 `type=dc`（这些行都写了 `dc=`），别的字节不动。checker、参考解、候选、题面、`task.toml` 都不改。未仿真。

- 改了哪些文件（2 个文件，共 4 处；改前 → 改后 sha256）：
  - `environment/public/public.scs`（1 处，`cc8d7ecb…` → `eed0acfc…`）
  - `tests/cases.json`（3 处，`93f58021…` → `09adfdcb…`）
  - 本页只在末尾追加本节，原文不动；本页改后的 sha256 记在交付记录里。
- 改了哪些行（同一行出现在几份副本里，每份各改一次）：
  - `VOBSOUT (vout vout_read) vsource dc=0` → `VOBSOUT (vout vout_read) vsource type=dc dc=0`（4 处）
- 依据（网表约定清单第 4.14 版，2de4ab22…；只引条目、行号与短句）：
  - type：第 1 节第 75 行，vsource 的 `type` 缺省为 dc，分级“必须”。
- 补上不改电路，以确认作业的逐位比较为准。vsource 的缺省类型就是 dc。
- 确认作业：无。新基线：本题这几份网表没有上过 Spectre，第一次上就带新写法（`environment/public/public.scs`、`tests/cases.json#healthy`、`tests/cases.json#offset-timeout`、`tests/cases.json#slow-cap`）。
- 改前原文件逐字节存于 `runs/t3-spectre-wave2-20261029/typedc-sweep-r1/orig/benchmark/material/draftbench/batches/v3-01/tasks/v3-ldo-response-experiment/`；记录：`runs/t3-spectre-wave2-20261029/typedc-sweep-r1/disposition-1.md`（本地记录，不入库）。
