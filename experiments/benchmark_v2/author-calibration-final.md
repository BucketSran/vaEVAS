# 作者校准最终固定审计

37 题、179 个登记变体的当前作者校准证据全部齐全，其中79个正确变体、100个语义错版，覆盖 584 个条件位置，无剩余缺口。这只证明作者正例和语义负例校准，不代表模型最终评分或整个 spec 已完成。

Run ID：`final-a5-cb789-equivalent-20261010T2140Z`；输入观察时间：`2026-10-10T21:39:07.562727+00:00`；audit SHA256：`011e1fb5e1fd81689da38161ce0a845003d90c57edcfd22993910bb56452d30b`。科学来源固定为 `a5c12a1a01a47e40a7f37b611e55836e59db65cf`；与发布版本 `cb78985f0509d3dbf01c3c6dc174dce9238ad4c9` 的整个 benchmark Git tree 及六份校准 manifest 逐字相同，证据见[固定机器摘要](author-calibration-final.json)的 `source_git_identity`。这些是原作者及集成版本的身份关系；本次仅更新说明文档，不把新文档版本称为整个 benchmark tree 相同。

31 个变体、110 条条件使用新的完整实际运行；另 148 个变体、474 条条件严格引用已封存 provisional 的当前 checker 真实归档重判。引用记录保留原 audit SHA、重判记录 SHA、原 job 和波形身份，并核验当前候选、每条 raw case、source identity 和执行资产相同。这次没有重复 evaluate，也没有把归档重判记作 fresh solve。

保留全部 1104 个 distinct 实际 job：1064 已评分、40 当前未评分。旧快照的 43 条未评分观察完整保留；其中 3 条当时 pending、随后确实完成评分，转变的 job ID 单列，旧记录未改写，旧 1070 个 job 无一删除。历史正例失败和负例意外通过仍在实际尝试分母，环境或编译失败不作为有效语义拒绝。

类别变体分母：spec 68、data 8、extension 20、diagnosis 33、testing 50。新增 349、16 个 alternative、九题独立终评实例及 POR 的新实际证据均纳入。本次封存审计没有启动新的模型请求或仿真，原始 summary 未改。

[固定机器摘要](author-calibration-final.json)保留封存的 publication JSON 原字节，SHA256 为 `2a0fa259912f997598f7756afb6ada7c27ef3fa82ea61d331a7cf2f233f49c87`：保留 source Git、case、候选、报告、archive 和重判 SHA，以及完整实际尝试分类与历史观察；去除本机绝对路径和隐藏 case 值，不包含 log_tail。完整内部 audit、curated 和引用 index 保留在原封存记录，本页不发布本机路径或隐藏条件值。

任务入口见[五类任务索引](README.md)，逐题来源见各任务的 SOURCE.md。历史 Git 身份保留在固定机器摘要中；当前作者摘要不会升级旧模型结果，也不宣称任意合法实现必过或所有负例在每个条件都失败。
