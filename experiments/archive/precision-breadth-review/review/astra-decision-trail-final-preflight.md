# Canonical 决策日志最终矩阵前增量审计

结论：可访问证据支持本轮关键决策，没有发现把 eager 超时、F1 条件性结论、F03 输入未知或开源取证缺口改写为科学通过。仍需追加两处 worktree 指针更正；旧审计的时间边界说明也须澄清。最终 852 实际矩阵、正式 proof 包及 caller 资格授予不在这次结论内。

## 固定范围与覆盖限制

本次 canonical `decisions.tsv` SHA256 为 `2e0bb7c44db435b8a663bfbf693b8158a26623b3330e4340323189a3532a2647`，共 39 条决策，末行 2026-10-11T20:49:17Z。身份记录见 `astra-decision-trail-final-preflight-identity.json`。

上次报告写“18 行，截止 19:06:26Z”不准确：其声明 SHA `0f45d2...ae4` 精确等于当前前 18 条决策（含 header），第 18 条已是 19:09:44Z 的更正行。截止 19:06:26Z 实为 17 条。此次以字节 hash 确定边界，审新增 21 条（19:10:33Z 起），并重审 19:09:44Z 的更正行。原前缀逐字节保留，未改历史。

覆盖来源是本 agent 可访问的消息、现有报告、固定提交和本地实际文件；没有协调者完整 transcript。没有远端调用，也没有重跑完整矩阵或 CI。授权细节和未留本地 receipt 的 GitHub Actions 结论仅核对记录所述身份，未重新获取远端结果。这里不是完整会话、全部科学槽或全仓调用路径的审计。

## 需 root 追加更正的路径

- 19:48:42Z eager 拒绝行的 `worktrees/precision-event-array/runs/strict-q3-diagnosis` 应为 `../worktrees/precision-event-array/runs/strict-q3-diagnosis/`；其中 `runs/astra-timer-stop-and-phase-cost.md` 应为 `../worktrees/precision-event-array/runs/astra-timer-stop-and-phase-cost.md`。
- 同时刻 terminal callback 行的 `worktrees/precision-event-array/runs/astra-timer-stop-and-phase-cost.md` 同样缺 `../`。

这些是可追溯性缺口；文件实际存在，不是数学/生产 P1/P2。19:29:15Z 的 batch-v2、strict-q3-diagnosis 描述也可补完整定位，但后续固定报告已可追到原始证据。旧 mixed-stream 路径已于 19:09:44Z 修正；EC03/EC12 短名已于 20:05:00Z 修正；20:07:28Z 不存在的 GLM 目录已于 20:07:56Z 修正。`open-adapter-integrated-tests.log` 位于 run 根目录，实际存在，末尾是 78 tests / OK，不在 review/ 下。

## 关键结论核对

1. **Eager 版本明确弃用。** 早期 81a/0c700 的 F14/F20 原请求功能通过未被当作成本验收。后续保留旧 99ca VCO 完成、新版超时，以及 148 tests 中唯一 VCO timeout；19:48 行明确不部署 eager。c254 的 lazy 方案从同一 accepted frame 在原预算失败后完整重算代表值、包围与下游，固定点、无事件/根 gate 保留。后来 VCO 完成和 F14/F20 原请求通过，不覆盖 Taylor-only 红记录，也不把局部运行称为全矩阵。
2. **F1 关闭的是当前可达行为疑点。** 读取完整调用者 GLM 原报告、`glm-v2-lazy-f1-complete-callers/final-adjudication-and-history-calendar.md` 与独立 Astra 裁决。精化输出与 ordinary 重查 nominal 不同仍被承认；当前 guard/连续依赖限制和后续整体重算阻断错误消费。fd79 生命周期、6986959e 后续输入 cross、a8446fcc 同刻拒绝及 519d 文档构成具体补证。原首次补审误切 transient 的错误报告保留；history-calendar 后补仅归属 Codex 静态核查。GLM 的 `discarded_trials=1` 推断被附录明确纠正，不能当 retry 计数。未来允许 phase guard、连续历史依赖、同刻增量或旧解/新 nominal 混用即重审；不是无条件正确性证明。
3. **F03 出口与输入边界分开。** `open-backend-failure-attribution.md` 及当前 trail 将 36 槽归因于 wrdata 表达式出口阶段，保留原 missing-output。原实际日志能证明 TRAN 已有数据且导出报错；`lt/le/gt/ge` 保留字的具体机制仍待安装版单次 quoted-name probe。临近 0.5 的输入数值在旧日志仅显示 0.5，不能由出口修复推出比较语义正确；17 位输入读回、完整输出与 native reader 映射仍待核。没有将这一缺口判为语言能力缺失，也没有预授 PASS。
4. **Open adapter 集成不等于真实资格。** d844 最终独立报告、GLM 原报告/disposition 与根目录 78 项集成日志一致。原 49a grammar/environment/scope 负控、1e825 schema 缺陷、9bf3 argv schema 问题及失败模型调用均留存。20:44 行明确实际 proof、caller pending；没有凭机制包自称 approved 或数值像正确升级 native/runtime。后续 caller 新提交属于新的审核边界。
5. **V3 冻结与旧成绩区分。** INPUT_EQUIVALENCE 明示 5116 科学输入 byte equal，CHECKER_EQUIVALENCE 列 64 个 Python 文件不变，四个 Rust 文件变化；这是本地冻结身份声明，与独立先前卡片/配置核查一致。本次没有重新遍历 5116 文件。213 EVAS 新执行计划不等于完成数；旧 852 分母、原 RESULT 与 deferred/unknown 保留。
6. **Curation 硬化不改科学内容。** 独立重新 hash 旧/新收据、脚本和测试，均等于 `curation-hardening-identity.json`。旧收据 SHA `c00c1d...eb4` 不变，新收据 `0c4377...606`。完整 JSON 比较仅新增 availability，已有字段仅 curation_source_sha256 改变；所有 scientific slots/tables/groups/counts/预算/其他身份逐字段相等。空 manifest 未覆盖 payload 的真实缺口、14 校准和实际 CLI 拒绝保留在审计材料。这里的 597 是已收集快照，收据仍列完整 852 槽，未收集不算执行/通过；raw local-only 不声称公开可取得。本轮未独立重跑那 14 项，因此数量依据保留日志与报告。

## 仍待最终 delta

GLM 索引明确保留 timeout 费用/turns unknown、零模型 context 拒绝、混合流和缺上下文报告；没有用后来的成功覆盖它们。本轮阅读索引和本轮关键原报告，没有重新逐项审计全部 33 次调用账本。

待所有 852 槽与 EVAS v3、安装机制取证完成后，还需核冻结 selection、不择优替换、全部实际来源 hash、正式 proof 外部批准链、caller 绑定和最终人工表。当前结论仅允许继续这些工作，不是科学成绩认证或 merge 授权。tracked 文件与 canonical 日志均未修改。
