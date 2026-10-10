# 新增和维护题卡

1. 从总表和暂缓项确认未使用的全局 Case ID；编号不随分类变化，不回收旧编号。
2. 在 `catalog.json` 已登记的工程动作与电路家族下创建 `case-NNNN-purpose/`。
3. 复制本目录 [case.json](case.json) 和 [CASE.md](CASE.md) 为新目录的 `case.json` 与 `README.md`，替换占位信息。模板本身不参与题目计数。
4. 查已有来源与电路记录；复用相同 ID，缺少时再登记固定版本、实读范围和许可。没有选定电路时用空数组，不能编造资产。
5. 填写设计目标、原材料与新增要求、独立验收、待确认项。实现前可以另写明确标注的题面草案；正式任务建成后链接唯一有效题面。
6. 从仓库根运行 `python3 -B scripts/benchmark_workbench.py --write`，然后 `--check`。生成索引不用手工维护。

元数据中 `task_path`、`evidence_paths` 都相对仓库根目录；来源 ID 对应 `sources/<id>.md`，电路 ID 对应 `circuits/<id>.md`。`backend` 未选定时必须为 null，选定后写工具链及版本说明；具体数值设置保存在任务环境与证据中。

修改公开合同后递增设计版本并重新提交 review。待 review 不是实现失败；设计已认可也不是后端或 checker 已验证。接受本版设计时，填写对应 `reviewed_revision` 并在正文记下真实 reviewer、日期、范围及可用的提交引用。

如果用户只认可选题方向，在正文 Review 记录中写明认可范围，具体设计仍保持 `pending`，不填写 `reviewed_revision`。记录方向反馈本身不改变公开合同，无需递增设计版本。

阶段可用值：`source-screening`、`design-draft`、`implementation`、`calibration`、`model-trials`、`frozen`、`deferred`。设计 review 可用值：`pending`、`changes-requested`、`accepted`、`not-requested`。

上下文可用值：`bounded-work-unit`、`bounded-project`、`full-repository`。公开自测方式：`undecided`、`fixed-public-tests`、`fixed-connections-custom-probes`。即使尚未选自测形式，也应在正文写清拟交付物与终评边界。
