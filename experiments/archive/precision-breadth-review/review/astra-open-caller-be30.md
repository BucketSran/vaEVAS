# Open evidence caller 独立审查（be30 + f125）

**没有发现可行动的 P1/P2。** 固定比较为 `0e1f91d116820f74a560b21d5a20b9c25b69e71e` → `f12598d2d0636ebb5329761afaa865c1cb03650f`（含 `be30baa6b49bea444a8c931d58fe727bf0b50463`）。仅 reanalysis 与其测试两个文件。接入的 adapter 固定 `d844b79584b8a42d361e340ce918658f3609d9a9`，文件 SHA256 `0a0ee2537eb5aee65d77d0c07f80b1f4fcc2c8b4b809540309f3bdc9244db1fb`。本次只读 tracked，无远端、无模拟器运行；允许接入继续本地取证，不构成正式 proof 批准、科学升级或 merge 授权。

## 信任链与评分边界

- 外部 adapter/proof/attachments/原执行 MANIFEST 复制到独立 external-open-evidence，全部 seal 的 hash 由 OPEN_EVIDENCE_IDENTITY 绑定，再由 ANALYSIS_IDENTITY 绑定。原科学 source_hashes 和 cards 不变；原 RESULT、raw 与原级别继续单独保留。
- 调用者先验证外部 adapter 的精确批准 digest，再验证 proof 的精确批准 digest。它们由 caller 的 CLI 参数提供，proof 自身的 approved 布尔值不能替代。**批准这些参数仍是人的正式双审决定**；任意自选 hash 不会自动获得真实性。当前真实包没有这样的批准。
- 原输入六项 digest 来自经逐成员验证的 execution MANIFEST；原始输出七项 digest 来自经全库存、尺寸、hash 验证的 FILE_MANIFEST。不是调用时从候选 work 现算一组新 hash 就授予来源。d844 随后比对实际文件、完整 argv、固定安装、环境、run scope、compiled artifact 与 RESULT 波形/编译产物关联。
- configuration 资格采用 legacy configuration **AND** official binding **AND** adapter identity/config/integrator。native/runtime 仍由各自 adapter 轴独立判定；外部适配器的观测/诊断要求已进入 native 门。数值 assessment 先独立完成，没有 proof 只保留资格 unknown，不覆盖数学结果，也不把原执行失败改成成功。
- 非 open 后端的 actual_integrator 明确是 `not_applicable`，现有 EVAS/Spectre 方法资格及评分逻辑不变。无 proof 的 open 轴是 unknown；不能把这一新增外部证明义务套到非 open 后端。
- slot_status 原有执行/数值/证据判断未改；通过仍需 config/native/runtime 全 qualified。原 Q profile 绑定、固定 selection、Probe 的科学判据仍是原实现；本 diff 没有容差、cap、stop、16 ulp 或分母修改。

## 独立执行

在固定、干净 precision-core checkout 执行 `python3 -B -m unittest discover -s experiments/backends/support -p 'test_precision_breadth_*.py'`，29 项通过（15 reanalysis + 14 aggregate）。原输出保存在 `astra-open-caller-f125-tests.log`。另单独先跑 15 reanalysis 也通过；最初同批两个 sed 命令使用了错误 cwd 相对路径，未读到文件，随后已用正确路径读完，不计作验证成功。

独立链式故障注入保存于 `astra-open-caller-fixed/probe.py` 和 `probe-results.json`。caller、adapter、settings_readback 与 fixture 均从固定 git 对象导出。NG/GN 各 7 个完整 caller→sealed adapter 控制：合成有效包、缺 adapter 批准、缺 proof 批准、错误冻结输入、已重新 seal 但超出原 proof 的 compiled artifact、缺实际 integrator、原 raw 漂移。两组合成正控确实通过全部门，12 个负控全部阻止资格；原科学 source_hashes 逐次不变。另真实 F02-base--Q1 加原 batch-v2 execution MANIFEST 的缺批准检查七轴均 unknown，共 15 个控制通过。合成正控仅证明接线可达，不是实际机制证据或审批。

## 实际无 proof reanalysis 抽检

owner 完成的 `analysis-open-caller-no-proof-ngcomp2-v1` 被独立逐文件核对：159 个 analysis manifest 成员 hash/size 全匹配。36 槽与原 `analysis-composition-openvaf_r_ngspice-part2-guarded-v1` 按 label 对齐，assessment、execution_status、identity、settings、profile_binding、source_compatibility 逐 JSON 全等；9 waveform、15 compile_failed、12 missing_waveform 保留。9 波形槽外部七轴均 unknown；无新增 analysis_error，不能取得完整资格。实际 adapter/proof 批准 hash 都为 null。COMPLETION 明示原 raw manifest 未改。这是对 owner 实际本地 reanalysis 结果的独立审计，不是我重跑了 36 槽或任何 simulator。

审计身份保存在 `astra-open-caller-fixed/actual-no-proof-audit.json`。原 baseline 选择和 raw 没有被此次试验收据替换。

## 限制与后续

当前真实正向 proof/startup/export/实际 integrator 证据仍待收齐；不以合成正控、旧八条件或数值相近转授资格。正式批准前仍须逐一审查 proof 附件、环境/安装身份、每个 run scope 和实际完整 deck，确认批准 hash 与新 analysis 中 seal 的字节相同。缺 proof、未知或失败保持原状态。最终 852/v3 和正式批准后的 caller 正向证据需另外审；本报告未声称那些工作完成。
