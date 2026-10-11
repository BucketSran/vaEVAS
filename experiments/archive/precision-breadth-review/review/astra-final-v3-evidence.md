# v3 EVAS 实际证据独立审查（已补齐 213/213）

最新结论：四条 lane 的 213 槽已核验，最终 105 P / 81 I / 27 X；未发现新的 P1/P2 证据错配。EC21 Q3 的实际超时回退保留，不能把整体变化称为无回退。最终 852/NG36 收据仍待审。下方保留 177 槽阶段记录，213 槽结果见文末追加。

阶段一结论：已收集、已封存的三条 lane 未发现新的 P1/P2 证据错配。可继续完成同一预选矩阵；这不是最终 213 槽、852 槽或行为全面对齐的批准。尚缺 composition-evas-part2 的 36 槽及最终正式 aggregate/NG36 收据，随后追加同一报告。

本次只读检查本地实际附件，没有运行远端、修改 tracked 文件、替换原成绩或重做旧数学/工具审查。审查范围是可访问归档、原始槽、固定源码和分析快照，不声称完整会话、远端文件系统或执行环境独立重建已审。

## 固定身份与逐字节检查

- 实际源版本 `519d5e2805c40f2534a781e7dce4b78fbfde01b9`。149 个 SOURCE_MANIFEST 文件既逐一验证本地实体 hash，又逐一与该 Git revision 的 blob 比较。manifest SHA `ae10d244f3dbc96b4d788d80a4547b5f76d0af3be2a90e2cc23f62d39334bb39`。
- v2/v3 两个输入 manifest 各 5,117 项，全部实体 hash 验证。文件集合相同；5,116 个文件逐字节相同，唯一变化是 `SOURCE_IDENTITY.json`。这包括 DUT、条件、strobe/观测计划、请求和档位预算，不能解释为放宽新请求。
- 三个 `raw.tar.gz` 的实际 SHA 与 COLLECTION 相同，2,814 个普通 tar 成员逐一与本地已解包 bytes 比较；三个原 FILE_MANIFEST 共 2,793 个成员逐一验证 SHA 和长度。三份 ANALYSIS_MANIFEST 共 537 项逐一验证 SHA 和长度；每条 lane 的 105 个 frozen-repo 文件逐一核对 ANALYSIS_IDENTITY。
- 所有 177 个 label 均在原 213 预选集合中，没有重复；每个 EXECUTION 条目等于同槽 RESULT。六个固定输入、RESULT/tool/artifact hashes、waveform SHA、原执行状态与本地重分析逐一绑定；无 analysis_error。成功原始结果只写 deferred/unknown，没有由原执行直接颁发 P。
- 三条 lane 均记录 kernel SHA `ae8e012c97abc166b33dbb2b0ccd7f9ed4a1d28543d2e1bd1c1f083c47fbf602`。同一 BUILD.json SHA `4317fe70f86d607480fc24a8494ea75184656a00efa91ad0a46daf3121db6c62` 将其绑定到 519 源 manifest、Cargo.lock、controller 和成功的 offline/locked/release 构建；build.log bytes 与收据 hash 相等。
- 限制：上述 binary 身份来自已封存执行/构建收据；本地未取得可重新散列的远端可执行文件。TOOL_IDENTITY 自报 build_revision=null，明确保留“source identity alone does not prove binary provenance”。不能把源码哈希核验写成独立二进制可复现构建证明。
- Foundation 两 lane 的分析 revision 为 `f12598d2d0636ebb5329761afaa865c1cb03650f`，composition-part1 为 `aa7cb13d2c9a08c95aca24d10250060249f5c4fc`；实际 reanalyzer bytes 均为 `280842f911dd46cb769017b73254f6ab1819441f609994222320d1479fc57896`。当前 primary/aggregate 元数据提交不应被写作产生原始波形的 kernel revision。

| lane | 槽 | 原执行有波形 | 原执行失败 | 最终 P | 最终 I | 数值 P | 数值 unknown / insufficient |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| foundation-part1 | 93 | 93 | 0 | 39 | 54 | 42 | 51 / 0 |
| foundation-part2 | 39 | 39 | 0 | 33 | 6 | 33 | 3 / 3 |
| composition-part1 | 45 | 28 | 17 | 22 | 6 | 22 | 23 / 0 |
| 当前小计 | 177 | 160 | 17 | 94 | 66 | 97 | 77 / 3 |

“数值 wrong=0”只说明当前评估没有得到 N，并非 177 槽数值已认证。80 槽数值未知/证据不足（含 17 执行失败），另外 F07 三档数值虽 P，事件仍 I。最终 94 P 的分母是当前已审 177，正式预选仍为 213；不能把剩余 36 删除。

## 关键前后变化

F07 三档：原早期 batch 均 `unsupported_cross`；v2/v3 均成功导出 202 个点。v3 原始 timer 在 2.5e-7，状态 [0,1,0]→[1,12,1]；cross 在 5e-7，[1,12,1]→[11,122,2]。最终 first=11、last=122、y=133、count=2，与已审实际 Spectre 数学状态一致。三档数值上界仍为 3.410605131648481e-13 V，但不是完整对齐：本次独立观测得到 array-cross 包围 [4.999999622641475e-7,5.000000000000034e-7]，早端跨数学根；保留 full-bracket I。原 raw event.time 并不提供独立认证的 callback 时间包围，不能据其名义值截短该区间。

F14 Q3：v2 原拒绝 bound=5.551137327586275e-11、budget=5.001000000005759e-11；v3 在原完整 107 strobes 成功导出。三档最终仍 I，numeric unknown；所缺为独立 DC/transient phase、输入导数/拓扑适配证据与 qualified reference，不能用已审局部数学点值误差零代替这些资格。

F20 Q3：v2 原拒绝 bound=4.6557654612152773e-14、budget=1.0000000000900423e-14；v3 在原完整 172 strobes 成功导出。三档仍 I，数值 evidence_insufficient：真实 wrap 邻点在原时间/出口不确定性下形成约 1 V 的参考包围，上界 1.0000000000000027 V、下界 0，超过 B/10。这既不是已经证明实际点值错 1 V，也不是能据本地精确点值对照删除的不确定性。

组合 Q3 当前已审 15 槽：EC06-v1/v2、EC09-v1、EC11-v1/v2、EC12-v1 共 6 P；EC01/02 的完整 callback brackets 不满足合法窗，均 I；EC03 的输出区间预算、EC04 的 stored internal steps、EC12-v2 的 cumulative candidate-step work limit 仍真实拒绝；EC05 仍 unsupported_operator；EC07/08/10 仍 timeout。拒绝与超时完整保留，没有把 absence of wrong 当成 P，也不能把停止时刻 callback 的额外工程约定不满足直接称为 LRM 语言缺陷。

## 可复核产物与后续

- `astra-v3-audit.py/json/log`：可重复的源、输入、tar、manifest、全部槽绑定与分层计数；本轮 failures=[]。
- `astra-v3-before-after.py/json`：9 个 F07/F14/F20 原始前后条目及 15 个组合 Q3；旧原始重点槽也对其原 FILE_MANIFEST 校验，failures=[]。
- 三个归档 SHA：foundation1=`750c4c40fb31903c4a7379e1e9ef828e017907e0e46d47638c141e16e1544c2d`；foundation2=`e4b6324dc5c4c2bf1a7c0e6514baf8184d7f7239449c28c1a2f7e5fbe5f5c588`；composition1=`612ebfbdce183c1cd67895211ab48a587611cbfe98e5a8cea707176b9073f8da`。

待 composition-part2 封存后检查其同一输入/内核与失败保留，更新到 213。待正式 aggregate 与 NG36 到齐，再核确切 852 收据的选择、全部分母及科学/证据分层。七个真实 open proof drafts 仍未批准；本报告不给其资格，也不对 metadata-only 增量授予数值改善。


## 追加：composition-part2 与完整 213 槽

最后一 lane 的 archive SHA `4a594a8fe704e1304a049e44309a3b58650363440071a11a0a19b08054fd535d` 已对实际压缩包核验；559 个普通 tar 成员逐字节匹配已解包实体，原 FILE_MANIFEST 552 项和 ANALYSIS_MANIFEST 156 项的 SHA/长度全部相符。分析 manifest SHA `bcaa240baf130310e22b598b500d7e3e9f5c603bd10a8965fc5acd9c35280202`；分析 revision 为 aa7cb13d，reanalyzer hash 与前三 lane 相同。36 槽的六输入、RESULT、TOOL、waveform、原 artifacts 和分析绑定逐一核验；仍是同一 519 源、ae8e kernel/build 收据。全 213 预选 label 恰出现一次，无遗漏/重复，脚本 failures=[]。

| 范围 | 原 waveform | 原 execution_failed | 原 timeout | 最终 P | 最终 I | 最终 X | 数值 P | 数值 unknown | 数值 insufficient | N |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| composition-part2（36） | 26 | 9 | 1 | 11 | 15 | 10 | 11 | 19 | 6 | 0 |
| 全部 EVAS（213） | 186 | 17 | 10 | 105 | 81 | 27 | 108 | 96 | 9 | 0 |

这些数由四份实际 REANALYSIS 与每槽原 RESULT 直接解析，未采用人工总计。全量 0 N 同时伴随 105 槽 numeric unknown/insufficient；因此不能宣称 213 槽精度均通过，更不能把 186 个有波形等同于 186 P。

最后一 lane 的 Q3：EC13/14/15 为 P；EC16/17 仍缺 phase/derivative/reference 证据，EC18/19 的 wrap 时间/出口不确定性仍过大，均 I；EC22 为 semantic support probe，same-time OR 合并/计数合同和 callback 证据仍未解决，继续 I。EC20 保留 unsupported_strobe（local-time causal closure）；EC23 保留 z 的 waveform_accuracy 证书拒绝；EC24 保留事件网络不支持 index-one polynomial DAE；EC21 Q3 为实际 timeout。EC13 的 P 按冻结卡额外终点 callback 合同解读，不扩张为所有 LRM 合法实现都必须停止前完成。

全 213 个原执行与 v2 逐槽对比，恰有六处 status 改变：F14/F20/EC17/EC18/EC19 的 Q3 从 execution_failed 变为 waveform_available，最终全部为 I；另 EC21 Q3 从 waveform_available 变为 runtime_timeout，最终 X。EC21 v2 Q3 耗时 89.84979362413287 s，v3 在 90.01653360016644 s timeout、returncode=-15；原上限 90 s 没有放宽。Q1/Q2 均仍完成，原/新 accepted_steps 分别相同（20,048 / 20,272），但耗时也有漂移。它的旧 Q3 已非常接近上限；单次实际记录既不能证明确定的算法性能退化，也不能消除本次实际回退。没有用旧成功替换新超时。最终 P 数保持 105，不能把净少四个 X 写成五个新 P 或无回退。

`astra-v3-execution-delta.json` 保存全量比较和 EC21 两版本三档原始阶段记录，EC21 RESULT 实体与各自原 FILE_MANIFEST 相符。`astra-v3-audit.json/log`、`astra-v3-before-after.json` 已扩到 213/36 个重点记录；原阶段产物以 `-177` 后缀保留。本轮未重复运行数学/工具测试，也未扩展远端取证。

下一步只补正式最终 852 aggregate/receipt 与 NG36 的确切选择和分母审计；本报告不授予七个未批准 open proof drafts 任何资格。

### EC21 运行身份补核

`astra-ec21-runtime-identities.json` 保存两版三档完整阶段记录与文件哈希。六个原始槽的全部文件均对各自原 FILE_MANIFEST 验证，不只是抄录耗时字段。两版 Q3 使用相同 Python 3.12 worker、taskset CPU 0、4 GiB memory/32 MiB file caps，argv 只有 batch 路径/绑定内核版本变化；request.json 精确相同。Cargo/rustc 可执行文件 hash、版本、RUSTC env 相同；控制器/build driver SHA 有变化，不能声称整个运行环境已逐位重建。

六份 simulate.log 都是零字节，hash 为标准空文件 SHA，阶段 log_sha256 均匹配。新 Q3 的 sidecar 记录 timeout=true/status=timeout/returncode=-15/cleanup complete；没有部分 raw-response 或内部诊断。因此不能从日志推断新 Q3 已走了多少步、是否发生过一次 lazy retry。

更强的已完成路径对照是：EC21 Q1/Q2 两版 program.json、raw-response.json、waveform.csv 全部逐字节相同。它们的耗时分别从 77.64655→82.92018 s、77.82856→81.76561 s；这与输出/已报告工作计数不变而 wall time 漂移相容，不能证明 Q3 的原因。生产 diff 可达性另交 event-array worker 固定源码审查（拟写 `ec21-q3-runtime-diagnosis.md`，此处追加时尚未落盘）；本审查未把“只有普通 idt、没有 idtmod/sin”过度推成“新 wrapper 绝无开销”，因为其错误重试门并未先检查是否实际存在 IdtMod。若需要区别资源波动与额外重复工作，应由 root 安排固定同环境的有判别力诊断，独立保存，不改本槽既有 X。
