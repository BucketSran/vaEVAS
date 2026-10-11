# Benchmark v2 规格交付证据

#133–137 批准范围的材料、作者校准、正式参考入口、双模式试做及质量分析已有固定证据。37 题各权重 1，32 个 P1 来源唯一归口，另有 5 个必做代表；系统及同源关联组是重叠子集，不增加分母。

交付关联 [PR145](https://github.com/BucketSran/vaEVAS/pull/145)。本文以相对证据文件与 SHA256 绑定；最终 Git revision、CI 和合入/关闭决定由外部审查记录，不在本文自指绑定。

作者校准覆盖 179 个登记变体、584 个条件位置；当前私有覆盖增量及历史结果分别保留。正式 stock Harbor Oracle 参考验收覆盖 37 题、111 个条件，全部 graded PASS。参考链路包含原 source solve、公开会话提交桥接、候选精确冻结及独立 FrozenCandidateVerifier；不声称 source test.sh 逐字执行。

最终试做为 37 题 × 2 模型 × 2 模式，共 148 个终态格、74 组相同规范公开字节的跨模式配对。保留 one-shot 106 次和 Agentic 82 次独立实际尝试，不以尝试次数替换格分母。

|模式/模型|PASS / 固定格|已评分|
|---|---:|---:|
|agentic / glm-5.3|25 / 37|25|
|agentic / glm-5.3-flash|23 / 37|23|
|one-shot / glm-5.3|17 / 37|17|
|one-shot / glm-5.3-flash|21 / 37|23|

合计 86 PASS、2 个有效 FAIL、60 个未评分 null；Agentic 48/74 PASS，one-shot 38/74 PASS。失败、预算耗尽、提交错误和未知原因均保留，未评分不转成电气 reward 0。

公开字节相同不表示呈现、模型使用、工具访问或预算相同，不能据此断言工具收益的因果关系。真实数据与两道集成题均没有可评分模型候选，其泛化/实现能力未知；这些事实是试做结果，不能改写为成功解题。质量报告 41 条，原 40 条保留，并补充 308 Flash Agentic 实际 6/6 PASS 与末期公开接口不可用限制。

|批准 Issue / 义务|精确任务范围|验收证据|Agentic PASS/格|one-shot PASS/格|
|---|---|---|---:|---:|
|#133 M1|024 时钟采样保持|理想采样保持合同、独立采样/保持/初态/过渡验收|2/2|1/2|
|#133 M2|375 非重叠时钟|tick非重叠、取消/重启及双相实际输出|0/2|0/2|
|#133 M3+P1|19 个规格建模任务|19唯一P1归口；架构规定系统、SAR工程内补模块与跨类复用|24/38|19/38|
|#134 D1+D2|真实采样级数据辨识|真实JKU SKY130源、完整序列、初态/误差/可辨识性与固定训练/公开/留出划分|0/2|0/2|
|#134 D3|真实采样级数据辨识|独立真值与合理替代/语义负例校准|0/2|0/2|
|#134 D4|真实采样级数据辨识|真实数据题双模式试做与质量判断|0/2|0/2|
|#135 E1+E2|ADPLL fine TDC 接入|ADPLL健康coarse/fine执行器、TDC控制路径及关闭fine兼容/开启因果|0/2|0/2|
|#135 349|349 多通道采样读出|唯一P1归口349复用健康024四部件，公开诊断替身与读出/保持兼容|0/2|0/2|
|#135 E3|ADPLL 与多通道读出两题|两系统共同验收、小规模试做和质量结论|0/4|0/4|
|#136 R1|去抖、PFD、复位释放、UVLO 四题|005/046/272/249四单模块真实starter、健康、局部修复及合法整体重写|8/8|7/8|
|#136 R2+R3|UVLO 多VA复位控制链|原创多VA资格/复位/使能/下游因果、危险禁止与正常启动|2/2|1/2|
|#136 R4+P1|全部五个修复任务|四P1来源+原创链，共5题|10/10|8/10|
|#137 T1|111 滞回表征|111滞回测量完整窗口、误报漏报校准|2/2|2/2|
|#137 T2|放大器增益与有限建立测量|gain-settling实际静态038/动态370的增益与有限建立测量代表|1/2|0/2|
|#137 T3|POR 完整电源流程|真实Ajacci POR源/数字翻译provenance、闭环供电刺激与独立性质验收|0/2|0/2|
|#137 T4+P1|全部十个测试与表征任务|8P1唯一归口+放大器/POR两个额外代表，共10题|14/20|11/20|

16 项义务按各自真实任务范围连接作者、参考、试做和质量证据；349 仅计其本题，024 是部件依赖；T2 仅计 gain-settling，093/038/370 是关联材料。每项的完整证据链接、格键和固定 SHA 在配套 JSON 中。批准 Issue 的 SHA 指整个保留的批准快照，不能解释为正文 hash。

本次证据审查没有发现尚缺的批准范围交付证据。实现与模型试做验收证据完整。最终发布 revision、CI、两轴复核及协调者合入/关闭决定由 PR145 的精确 revision 审查治理；本文不持久化为未完成状态。父 #107、#72 与 circuit-harness #5 保持原范围，不据本报告关闭。

证据入口：

- [construction_index](README.md)
- [task_source_map](task-source-map.json)
- [author_fixed](author-calibration-final.md)
- [author_current_overlays](author-calibration-private-overlays.md)
- [formal_harbor_reference](harbor_reference/harbor-reference-acceptance.md)
- [one_shot](model_pilots/one-shot-final.json)
- [representative_quality](model_pilots/model-quality.md)
- [最终模型统计](model_pilots/model-pilot-summary.json)
- [最终 Agentic 输入](model_pilots/agentic-final.json)
- [配套逐义务身份与统计](spec-delivery.json)

原始 archive SHA 表示留存身份，不承诺公开下载。本文复用已独立审过的实际参考/作者/质量证据；本轮仅重跑本地 curator、核对原始投影与独立统计，未运行模型 API 或仿真。
