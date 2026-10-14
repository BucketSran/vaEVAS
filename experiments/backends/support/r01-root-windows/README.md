# R01 根窗口交付的紧凑证据

此包保存冻结 release 核 `867a1122…` 的三个独立选择，不能据此宣称完整 R01 与 Spectre 对齐。源码共 325 项与执行时的 dirty freeze 相同，后续提交定位为 `6b065e4f`。完整哈希见 [SOURCE-IDENTITY.json](SOURCE-IDENTITY.json)，源码核对与构建身份限制见 [COMMITTED-SOURCE.json](provenance/COMMITTED-SOURCE.json)。后续 commit 的定位由交付协调者提供；此整理没有重建，二进制的构建 revision 仍未知。

| 固定选择 | 执行结果 | 判定结果与限制 |
| --- | --- | --- |
| 原请求 16 条 | 12 完成，4 拒绝联合非仿射 transient | 原 checker 与有限输出各 12 通过，有限输入加输出 6 通过。相对 ce 的新增成功 0、丢失成功 0。历史 70 条映射未改，其余 54 条未重跑。 |
| 原微控制 19 条 | 13 完成，4 个原 `$strobe` 编译失败，2 个 kernel 拒绝 | 8 条有限原生 query 配对及数学预算通过，5 条完成但缺原生 query。拒绝项为高增益安全控制和 linear filter，保留原异常。 |
| 新 `$display` 变体 4 条 | 2 个 dyadic 完成，2 个 decimal 拒绝 | 每个 dyadic 的 6 个 query 与独立答案恰好相同，预算为原始 0 V，并有 5 次对应回调。decimal 的 `event_resolution` 拒绝和 Spectre 不同回调记录保留。 |

分母不能相加为一种资格统计。新 display 变体只把原模型的 `$strobe` 改成 `$display`，没有覆盖 19 条中的编译失败。`display4/ANALYSIS.json` 保存最初误用 1e-8 V 的历史分析；[最终分析](display4/ANALYSIS-original-budget.json) 恢复 0 V，两个 dyadic 的实测误差均为零，无需重跑。原评分、Q 和旧 grade 没有修改。

## 怎样核验这些结论

在本目录执行 `python3 -B verify.py`。只需 Python 标准库，不导入 EVAS、不调用 kernel、Spectre 或网络。脚本逐项核对 [INVENTORY.json](INVENTORY.json) 的整理后文件哈希，使用保留的原 checker 纯函数与独立 N19 oracle 复算 197 个原生配对和 216 个数学点检查，以及 12 个 display 零预算点。它也检查 16 条 VA/SCS 原输入身份、候选请求与 kernel 身份、参考 VA/SCS 身份、display PSF 实际配置和六条原输入失败见证。

通过是指实际保留的 query 在原预算内。它不证明 query 之间的连续轨迹、全部原生时刻的最大误差或完整闭环资格。19 条的 `qualification` 继续为 null，原参考的 incomplete 或 diagnostic 状态没有升级。缺 query 是完整原 PSF 的历史分析结论；片段中找不到 query 不能独立证明完整文件缺失。

有限 gate 的校准包含零误差接受、超预算拒绝、NaN 和 Infinity 拒绝。display gate 还拒绝任意保留的非零例子。六条输入失败见证在原 2 mV 门槛之外；复算浮点插值允许 1e-12 V 运算顺序舍入差，只用于核对见证末位，不参与原 pass 判定。完整 501 候选点的原 checker 和原始全波形最大值没有由此重新认证。

## 收据、实际配置与可获取性

`controls19` 保留每条模型、请求 SPEC、候选收据、完成项响应、参考 deck、原 PSF HEADER 与精确 query VALUE 块。选择 VALUE 块没有插值；inventory 记录完整原文件哈希和行索引。PSF HEADER 中的实际 `reltol` 与 deck 请求值可能不同，两者均保留。`display4` 另存请求、回调日志原行号与参考执行身份。`original16` 保留全部 VA/SCS、执行诊断、原 checker 身份与 verdict、压缩 regrade 和六条输入差异见证；它没有保留 bulk kernel 请求响应。

包内材料为 repository-contained，不意味着已发布的 public archive。完整原 PSF、完整日志、bulk 请求响应与旧执行目录仍为 local-only，没有公共下载地址。inventory 的 `archive:vaEVAS/…` 是已去机器私有前缀的原位置标记，不是可下载 URL。路径规范化文件保留 original_sha256，整理后文件另记 sha256。目录内原 `MANIFEST.json` 是历史完整运行的 identity inventory，可能指向未收入的 bulk 文件；当前可验证清单是根目录 INVENTORY.json。

原 16 条有限配对沿用 501 个均匀候选时刻，排除原控制边沿 5 ns 窗口，并对两边实际保存点线性读值。六条输入失败保留 0.084 V 或 0.154 V 差异，支持保存网格的有限读值差异，不构成未记录时刻的连续波形错误证明。原输出门槛仍为 2 mV，sample_time 的原时间换算门槛保留。

此包没有新增后端运行，没有改变源码或 checker 预算。安全 probe 只作为历史开发诊断保留，不扩大资格数量。基础 7 控制由另一个交付步骤整理，不包含在此包当前分母中。GLM 等待已由用户豁免，不增加或伪造 review 次数。

## 最终初态与反馈系数：七例实际诊断

[独立收据](feedback-final-seed.json) 保留同源 VA、deck、原生查询、实际设置、告警和身份，不加入上面三个历史分母。Spectre 21.1.0.509.isr12 对原单位反馈模型在 0.5 秒不收敛，灾难恢复越过断点后返回恒零；原、密集和普通查询配置均如此。成功退出不是满足采样方程，恒零不作为新答案。

最终零时刻种子使系数 c=1，事件要求 q=y+1、y=q，无有限解。EVAS 的明确拒绝符合该合同。旧 `[0,0,1,1.5,2]` 依赖已被替换的虚构初始斜坡，原源、旧断言和失败仍保存在 [冻结旧合同](../../../../evas/validation/r01/legacy-transition-coefficient-v1.json)。当前回归检验同源无解拒绝和事件前可执行，不把旧失败改成通过。

赋值 q=1、收缩反馈 q=.5y+1、正时间启用三个独立正控具有全部 11 个精确原生查询点；在事先固定的 1e-8 V 预算下满足独立方程，Spectre 最大点误差分别为 0、0、1e-16 V；与冻结 EVAS 配对差分别 0、0、2e-16 V。这只证明有限正控，不证明任意事件语义或原单位反馈波形对齐。
