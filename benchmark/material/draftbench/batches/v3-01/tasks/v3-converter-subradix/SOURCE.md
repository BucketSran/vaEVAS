# 来源与覆盖

v4-243 原始同源码制素材，新增明确采样与保持合同。

来源固定在 reviewed main 81eb66258b59b0a0cd48cd3decaa767be02cdd58。本题为独立编写的 VA 改编，未复制商业库源码。固定 Spectre 扩展集；开源等价尚未验证。真实校准及已执行分母见[作者校准](../../../../../../../experiments/benchmark_next/converter/author-calibration.md)，旧资产关系见[资产审计](../../../../../../../experiments/benchmark_next/converter/asset-audit.md)。不开展模型试跑。

## 2026-10-29 vsource 写明 type 与 sinedc（typedc-sweep-r1）

项目协调方 2026-10-29 批准、Benchmark 维护方统一写入：题包里每一份网表副本（各 cases.json 的每个用例网表与全部 `.scs`），没写 `type=` 的 vsource 在 `vsource` 之后补 `type=dc`（这些行都写了 `dc=`），别的字节不动。checker、参考解、候选、题面、`task.toml` 都不改。未仿真。

- 改了哪些文件（2 个文件，共 3 处；改前 → 改后 sha256）：
  - `environment/public/cases.json`（1 处，`283deef2…` → `5d074777…`）
  - `tests/cases.json`（2 处，`96fd674c…` → `d47c1d49…`）
  - 本页只在末尾追加本节，原文不动；本页改后的 sha256 记在交付记录里。
- 改了哪些行（同一行出现在几份副本里，每份各改一次）：
  - `Vrst (rst 0) vsource dc=0` → `Vrst (rst 0) vsource type=dc dc=0`（3 处）
- 依据（网表约定清单第 4.14 版，2de4ab22…；只引条目、行号与短句）：
  - type：第 1 节第 75 行，vsource 的 `type` 缺省为 dc，分级“必须”。
- 补上不改电路，以确认作业的逐位比较为准。vsource 的缺省类型就是 dc。
- 确认作业：无。新基线：本题这几份网表没有上过 Spectre，第一次上就带新写法（`environment/public/cases.json#normal`、`tests/cases.json#private-0`、`tests/cases.json#private-1`）。
- 改前原文件逐字节存于 `runs/t3-spectre-wave2-20261029/typedc-sweep-r1/orig/benchmark/material/draftbench/batches/v3-01/tasks/v3-converter-subradix/`；记录：`runs/t3-spectre-wave2-20261029/typedc-sweep-r1/disposition-1.md`（本地记录，不入库）。
