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

## 公开或外发前

仓库私有只说明访问范围。Cadence 安装库源码的版权属于其权利人；
本仓库未确认这些文件及其派生参考解的对外分发许可。课题组路径也不证明文件原创性。

在实际公开、抽取或外发前，按拟交付范围完成以下检查：

1. 确认第三方源码、include 与派生任务的分发依据；未知或未获准的资料从交付物中隔离。
2. 核对来源总表、源码注释、任务 `SOURCE.md`、结果收据和运行协议，去除对外版本中
   不必要的内部主机、用户名和绝对路径。可验证的来源身份保留，内部映射放在受控存储。
3. 原始资料和机器收据可能保留历史路径；需要另做脱敏副本时记录新身份，不覆写旧收据。
4. 若拟公开整个仓库，检查拟公开的完整 Git 历史；仅删除最新版本的文件不能清理历史。

本说明不代表未来公开或外发已经获准。运行配置只应指向已有授权的仿真器环境，
仓库不保存认证文件或商业仿真器安装包。
