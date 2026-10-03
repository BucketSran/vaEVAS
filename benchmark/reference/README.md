# 历史基准参考（v1 / v4）

本目录存放 vaBench（behavioral-veriloga-eval）的历史发布包，作为**只读参考**：
供后续按本项目要求重新整理 benchmark 任务时查阅来源、清单与认证记录。
这里的内容不是当前可运行的 Harbor 任务集（见[上级 README](../README.md)），
不参与评分，不随本仓库的验证资格声明。

## 来源与身份

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

- 本目录内容保持原字节，不做本地修改；引用时注明来源 commit。
- 正式整理 benchmark 任务时，从这里的 manifest/任务定义出发按 Harbor 格式
  重建到 `benchmark/tasks/`，不直接改造本目录。
- v3（`benchmark-vabench-release-v3`）未迁入；如需补充，按同样方式登记来源。
