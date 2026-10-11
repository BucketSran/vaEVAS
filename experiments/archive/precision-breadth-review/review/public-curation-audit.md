# 公开整理收据独立核查：597 基线与校验硬化

当前 597 基线正确保留完整 852 槽、各状态轴、失败与未知，未通过去重删掉执行槽。发现整理器 manifest 覆盖检查存在 P2 缺口；经 root 授权，仅修复两个 ignored 整理器文件并生成新试验收据。原 597 收据未变，没有修改 tracked/production/index，没有重跑仿真，也没有把证据不足升级为通过。

## 固定身份与范围

- 原收据：`public-receipt-baseline-597-v1/PUBLIC-RECEIPT.json`，SHA256 `c00c1d3720b283b16670399e61ae75d974861088f2c1f6468ffde6b236996eb4`。
- 原 aggregate：`official-draft-open-foundation-part1-guarded-v1`；原 failures：`failure-inventory-open-foundation-part1-guarded-v1`；卡片：`analysis-foundation-spectre-part1-guarded-v1/OFFICIAL_CARDS.json`。manifest/卡片 hash 全部等于原收据声明。
- 独立检查脚本 `review/audit_public_curation.py`、日志 `review/public-curation-audit.log`、结构化结果 `review/public-curation-audit-evidence.json`。
- 本轮按 evas-validate 检查归档身份、分母和各资格层；不递归复制实际 runs 大目录，仅逐个读取相关小文件。

## 事实：分母与资格层保留

852 个唯一键恰好等于 71 个冻结变体 × 四后端 × Q1/Q2/Q3，无遗漏、额外键或重复。每后端 213 槽。已收集 597，未收集 255（NG 81、Gnucap 174），未收集保持 final=evidence_insufficient / original_execution=not_collected，没有被当作执行或通过。

独立逐槽比对八轴 final/numeric/behavior/evidence/config/native/runtime/original_execution，误差上下界、预算、原 RESULT/kernel/tool/source 身份、请求与实际设置，全部等于原 aggregate。按四后端八轴重新 Counter，全部等于收据 counts。失败 inventory 的非 pass 键匹配；条件性或无法证明的 witness 没有自动变 pass。NG 与 Gnucap native/runtime 各 213 unknown 明确保留；例如 NG 数值 pass 49 也未因此变为完整 pass。

| 后端 | 完整 pass | 数值错 | 执行失败 | 证据不足（含未收集） |
| --- | ---: | ---: | ---: | ---: |
| EVAS | 105 | 0 | 31 | 77 |
| Spectre | 49 | 1 | 3 | 160 |
| OpenVAF/ngspice | 0 | 2 | 60 | 151 |
| Gnucap | 0 | 6 | 3 | 204 |

这些是固定 597 中间快照，不是最终 852 实际执行成绩，也不是修复后 v3 的结论。

44 组对应 20 foundation + 24 composition。528 个机器格恰好为 44×4×3；每格 variants 完全等于卡片该组所有 mandatory variants，数量一致；所有 group pass 必须其全体 mandatory variant 都 pass。原 group 全字段与公开投影一致。独立运行 `human_summary.py` 重生 `review/human44-independent-replay.md`，与原 `44-group-human-summary-open-foundation-part1-v1.md` 字节一致。支持探针未计通过，停止回调额外工程要求仍有文字提示。人工表是压缩展示；F03“执行拒绝”不能单独当语言缺失原因，应与单槽原因/开源失败归因报告并读。

## 来源与可取得性

597 个原 RESULT、597 份 dut.va、597 份 INPUT_IDENTITY、597 个 slot tool identity hash 全部逐项与实际本地文件匹配。71 个模型的 declared_source_sha256 都等于固定卡片源码。11 份 analysis manifest、11 份 analysis identity、11 份 ORIGINAL_TOOL_IDENTITY 副本 hash 匹配；副本与真实 raw TOOL_IDENTITY 的 JSON 内容一致。两种 tool identity hash 的字节不同是因为副本重排格式，不能误报 binary 变更；slot hash 指原文件、analysis-level hash 指副本。

原 public receipt 没有显式可取得性字段，也没有 raw 公共下载入口。retention_id/hash 足以关联已保留的本地数据，不能建立公共可复现性。当前人工中间表尾部含本机路径，仍是 ignored 本地稿；最终公开人工表需要公共或仓库定位方式，不应直接发布这个路径。最终 release 需分别说明：公开模型/checker 源码可以发起新的执行，但原波形、日志、工具二进制及 licensed Spectre 环境不是因此可公开取得。此次新收据显式区分这些边界，未造下载 URL。

## P2 负控、修复与新身份

原 `verify()` 只检查 manifest 声明的成员，未要求 main 将要读取的 OFFICIAL-DRAFT.json / FAILURES.json 必须列入。独立小负控：空 manifest 与未列出的 payload 并存时，旧 verify 接受，允许未封存输入进入整理流程。当前真实 aggregate/failures manifest 包含所需 payload，因此未发现原 597 本身受污染。

root 授权后保留旧脚本、测试、负控日志于 `review/curation-before-hardening/`，再仅改 ignored `curate_public_receipt.py`、`test_curate_public_receipt.py`：main 对两个入口分别要求必需 payload 是 manifest 成员，再核路径、symlink 与 hash；manifest 本身是 symlink 也拒绝。增加 availability：原 raw / analysis local-only；模型与 checker 源码 repository-contained，使用固定 source hash / checker revisions；新的重跑需 backend 环境，不等同于历史 artifact 或 binary 可公开取得。

- 旧脚本 SHA256 `ce8d5f436ce627c74d6b6b36143d3493d8060c8ab3720ad456cd96d24ec0a721`。
- 新脚本 SHA256 `c0571c882ba75543f0294d8381623809b3ad897f5f789a68b7731bf88b4d2f7c`。
- 新测试 SHA256 `d12de68c9e12c341106786b3f7a677e1bbf1287eecae6c16f2a3a9299a228b3f`。
- 新试验版 `public-receipt-baseline-597-hardening-v1/PUBLIC-RECEIPT.json`，SHA256 `0c4377a3b22a87020fde8db566a19e843b0603a1786ff95892306fd265467606`。

原 9 项校准通过；独立 5 项小控制验证失败计数篡改/重复失败拒绝、确定误差 witness 选取、列入 manifest 的漂移拒绝，并暴露上述覆盖缺口。修复后全部 14 项校准通过，另实际 CLI 对 empty manifest + unlisted OFFICIAL-DRAFT.json 拒绝且不创建输出。日志 `review/curation-hardening-tests.log`，身份与 CLI 结论 `review/curation-hardening-identity.json`。两次最初检查命令因错误 cwd/把 CATALOG 列表当 dict 报错，修正后按以上真实文件完成核查；这些命令错误不计测试通过。

新试验版除新增 availability 与 curation_source_sha256 外，完整 JSON 对象逐项等于原 597；852 槽、tables、groups、counts、错误界、预算与其他身份字段全不变。原收据 SHA 再核未变。写权已释放，并将新固定脚本身份通知 root 与负责后续封存的执行准备 agent。

## 后续 delta 仍待完成

最终 852 与 EVAS v3 收齐后，使用新的固定脚本生成独立目录，保留旧 597/690 与 before 执行。独立 delta 应核预先冻结 selection，而非以最好结果改选；旧/新 original RESULT、kernel、源码、输入、requested/actual settings、checker revision 分别说明继承或新执行。再次核 852 唯一键、71 模型、44组 mandatory variants、全部八轴和人工表。新执行后的通过不回写旧结果。实际 source 公共发布与 raw local-only 标记仍要分别确认。

## 实际 GLM c057 审查后的最小 delta

保留完整原审稿 `review/glm-v2-curation-c057-scoped/review.md`。root 授权只修其 F1/F2/F3 及 manifest size/output boundary 小问题；原 c057 脚本与测试另保存于 `review/curation-before-glm-delta/`。没有扩大私有路径 regex、引入新架构或改科学判分。

最终 ignored curator 强制正式生成路径的 71 卡片、44 组、852 官方槽完整身份与 528 组唯一键；每组 mandatory 变体数/键/final 必须与卡片及槽表完全相同，组 final 与六个独立资格轴均按上游既定 rollup 规则核对，否则拒绝。原 `expected_slots` 的小 fixture 覆盖仅用于局部测试，CLI 固定 852、不能关闭正式校验。reason dict 增加 scope/limit；behavior/evidence 分别遍历，避免同文双列表被归到一个层。main 在读写前拒绝输出落 aggregate/failure 输入树内；manifest 若声明 bytes 必须匹配实际文件大小，字典缺 digest 受控 ValueError。

固定最终 curator SHA256 `e4830d7c87bcf9e2ecf341d4196317c91eb19a74775622ac7b78ca2ee69e94ef`；测试 SHA256 `d3a4d03a99d6ed16b32cc0864b6cdb76b4666587e8de012d373f62db15faf4ae`。新增控制覆盖 scope/limit、同文不同层、manifest size/digest、两输入树输出边界，以及真实完整基线的缺组/重复组/mandatory数/变体状态/错误group pass/错numeric六种扰动。用同一新增测试对旧 c057 执行得到 9 个预期 assertion failures 与 1 个 scope 缺失 KeyError；新版全部 19 项测试通过。红绿日志分别 `review/curation-glm-delta-red.log`、`review/curation-glm-delta-green.log`。

新独立 `public-receipt-baseline-597-glm-delta-v1/PUBLIC-RECEIPT.json` SHA256 `5760bfbafa6445293c64145bd04ae0251d5e1c16bc9cc0d48b3b1a4bea08dbee`。相对 c057 收据：script 身份改变，reason 表与对应 reason_refs 增加被丢弃的限定文本；213 个槽 expanded reason 有 scope/limit 增量。所有槽的其余完整字段、counts、groups、models、settings、analyses、availability 全部相等。原收据保持不变。固定身份和比较结论在 `review/curation-glm-delta-identity.json`；已通知 root 与执行准备 agent 释放写权。

GLM 的 F6 是其所获压缩审查材料不含完整 per-slot hash/witness 的证据限制，不是工具字段丢失；最终审查必须提供完整实际收据或真正无损表示，不能靠口述校准通过闭合。最终 852 与 v3 data delta 仍未在本报告中核验。


## 外部 provenance 与 cards 可信入口 delta（d9f200，独立试验版）

本轮仅修改 ignored curator/test；e483 脚本及旧 852 compact 原件保留。针对实际 GLM e483 R1，原脚本在完整 852 输入上接受了将 F01 卡片 source 替换为 `forged source` 的负控（`review/curation-external-red.log`）。新 main 必须把 cards 字节摘要绑定到已封存 aggregate 的 `official_cards_sha256`；旧 schema 必须显式提供经批准的 expected digest，不能只对任意输入自算 hash。所有有 source 摘要的槽同时核其模型源码与卡片一致，封存分析内 OFFICIAL_CARDS 摘要逐份核对。输出不得落在 cards 父级冻结目录内。

新增独立 integrator 轴及组汇总，非 open 后端只允许 not_applicable，open 只允许 qualified/unknown；旧 schema 缺字段分别按 not_applicable/unknown 保留，不能默认升格。原 legacy_configuration、settings_provenance、external_qualification 分表去重但保留原 JSON，slot 引用可无损展开；analysis 引用外部原件摘要表。没有由 metadata 重算资格。

每个有 external_evidence 的分析重新验证完整 ANALYSIS_MANIFEST inventory、bytes/hash、路径 confinement 与无 symlink；OPEN_EVIDENCE_IDENTITY 必须是 manifest 成员且与 ANALYSIS_IDENTITY 外部摘要对应。每个 sealed_file 必须是成员且字节摘要一致；adapter/proof、批准摘要及 execution manifest 摘要与原 identity 相同。proof metadata 只接受原 proof 中指定十字段的精确投影，其 attachments 必须逐个在 sealed_files 中且摘要一致。不存在 proof 时 metadata 必须为 null。无公共下载 URL；原始执行和分析附件仍明确 local-only。

固定 curator SHA256 `d9f20088929e7fe1e5ef18ddfa77fbb5ca69b4b8a0c3f21d0b6d255f3b0e773b`；测试 SHA256 `2f3a21a28edca565ad01c4c8ef2c8927fe4d91fb434d59d97bea3f42726d46b8`，归档 `review/curation-external-fixed/`。28 项测试通过，覆盖摘要漂移、unlisted 原件、symlink、无 proof 伪 metadata、原 proof 被重封但附件不在 sealed selection、卡片 source/probe flag 替换、原模型 source 不符、cards 输出边界及 integrator 后端/组轴不符。日志 `review/curation-external-green.log`；归档副本独立重跑同样 28 PASS。此前错误 cwd 的命令不计通过。

实际 aa7cb13d aggregate 候选 `official-draft-complete-v2-external-no-proof-v1` 的 MANIFEST SHA256 `00c28a228427c2ff02298507dbd4b0b99c1d24dee006cd6a9c0672e81345f155`，failure inventory SHA256 `d748f5a79391fc089624c9ca056d8d8c033f9c915d2bf5784663bd07f38c9b4f`。新独立 `public-receipt-complete-v2-external-no-proof-852-v1/PUBLIC-RECEIPT.json` SHA256 `6ba65cacca44828d0790b586accbded9b890f6bf9f28bbdefd6199d5d5de33e3`，1,540,742 bytes，852 唯一槽、528 组。cards 固定 SHA256 `407c42213e71b4f44c7029ae74a5a646f33d059401d84d4391fe02160d6902fb`；实际 16 分析中的一个是无 proof NGcomp2 caller，外部 identity/adapter/execution 原件已独立核验。

与旧 852 e483 compact 逐槽比较，final/numeric/behavior/evidence/native/runtime/original_execution、误差上下界、预算、failure witness、源码/输入/原 RESULT/工具/二进制摘要均相等，模型对象相等；全部外部/legacy/settings provenance 引用能精确展开为 aggregate 原记录。NG EC16–EC18 × Q1–Q3 共 9 槽 config 从 qualified 降为 unknown，是无 proof caller 的保守配置边界；不是数值变更。open 两后端各 213 integrator 为 unknown，EVAS/Spectre 各 213 为 not_applicable。外部 proof 表 1 项（含实际无 proof 身份），qualification 表 2 项（null 和未知七轴）。所有独立 counts 与 852 原槽重数一致。

校准详情 `review/curation-external-identity.json`、`review/curation-external-aggregate-calibration.json`。旧 `public-receipt-complete-v2-baseline-852-v1/PUBLIC-RECEIPT.json` 再核 SHA256 保持 `7e8e65e7efb74149e25f49436f0d4a2d1fa8d4e6db6c451ac7b156edf1dd99b5`。本版是 provenance 校准实例，未授权替代正式 guarded baseline；无 proof 未升级任何未知项。此 delta 及完整实际收据等待 Astra/实际 GLM 的固定版本审查，旧 e483 审查不覆盖本次增量。


设置对象另作来源校准：852 槽 `settings.requested` JSON 表示发生变化，因为 aa7cb13d 上游明确从 `configuration.requested` 切到原 `profile_binding.requested`（增加 tier/id 等请求元数据，使用 `_s`/`_V`/`_A` 字段）。不能称全部 JSON 只有九项变化。actual readback 与 binding_status 全等；对旧已知 reltol、maxstep↔maxstep_s、stop↔stop_s、iabstol↔iabstol_A、vabstol↔vabstol_V 逐项对应，量值差异为零。680 槽原 requested 对象完整保留于 legacy_configuration.requested；另 172 槽原 key 就不存在（旧 compact 默认显示 `{}`），新 legacy 原件仍保留缺失而不填造。新增的原请求信息不表示实际 readback 已知，原 unknown 配置资格保持保守。最初直接断言 requested JSON 全等失败后才做上述来源/量值校准，该失败不计测试通过。
