# Verilog-A 资料与历史基准参考

本目录保存原始 Verilog-A 模型资料，以及 vaBench（behavioral-veriloga-eval）的历史发布包。
**资料仅供课题组内部研究，不对外分发。** 原始源码与历史包保持内容不变，功能索引和来源说明随整理更新。
这里的内容不是当前可运行的 Harbor 任务集（见[上级 README](../README.md)），
不参与评分，不随本仓库的验证资格声明。

## 原始 Verilog-A 资料

入口：[veriloga/README.md](veriloga/README.md)。先按来源分为
[课题组工程资料](veriloga/lab/README.md)与
[Cadence 官方安装资料](veriloga/cadence/README.md)，各自内部按功能分类。
每个文件的功能、原始接口和使用提示写在分类页；历史路径与 v3 关联统一记录在
[SOURCES.md](veriloga/SOURCES.md)。

本次整理 106 个课题组源文件、213 个 Cadence 源文件版本（171 个 module 名），
以及 6 个公共头文件。同一官方源码在课题组工程中的副本统一归入 Cadence，并保留工程来源记录。
尚有 45 个历史来源路径未定位；未运行编译或仿真。

## 历史发布包的来源与身份

| 项 | 值 |
| --- | --- |
| 来源仓库 | https://github.com/Arcadia-1/behavioral-veriloga-eval |
| 迁入时快照 commit | `7b5616dc52195ec275ec6d21c71d7763613702cd`（2026-07-28） |
| 迁入日期 | 2026-10-03 |

## v1（完整迁移，23 MB）

`benchmark-vabench-release-v1` 原样迁入：86 项 L1/L2 发布目标
（73 核心 + 13 辅助测量/激励支持项）、manifest、评估器说明、
证据与报告。入口：[v1/README.md](v1/README.md)。

## v4（最新快照 + 文档，194 MB）

原包 `benchmark-vabench-release-v4` 共 1.2 GB，其中 `release/` 下有 9 个
累积发布快照（benchmarkv4 及 r45–r53，每个 96–137 MB，内容大量重复）。
迁移取舍：

- **保留**：全部 SOP/需求/认证文档、provenance、evidence、operations、
  runners、schemas、scripts、reports、public-agent-runtime，
  以及 `release/benchmarkv4-r53`（最新发布快照，含 RELEASE_SEAL 绑定的 SHA256）。
- **未迁移**：`release/benchmarkv4` 基线及 r45–r52 八个旧快照（约 1 GB）。
  需要旧快照时从来源仓库对应 commit 获取。

入口：[v4/V4_TRI_FORM_BENCHMARK_REQUIREMENTS.md](v4/V4_TRI_FORM_BENCHMARK_REQUIREMENTS.md)、
[r53 发布封印](v4/release/benchmarkv4-r53/RELEASE_SEAL.json)。

## 使用约定

- `v1/`、`v4/` 保持原字节；引用历史包时注明来源 commit。
- `veriloga/` 按功能整理文件名和路径，源码内容不变；来源统一记入 `SOURCES.md`。
- 后续开发 benchmark 任务时，在 `benchmark/tasks/` 中创建派生任务，引用所用原始资料；
  原始资产整理本身不要求创建题目、参考解或 checker。
- v3（`benchmark-vabench-release-v3`）完整发布包未迁入；本次仅用其历史导入记录追溯原始模型来源。
