# 真实 open proof draft 4137 的独立审批裁决

**最终建议：目前七份 draft 均不批准 exact proof SHA，不进行机器资格升级。** 可以确认固定安装与静态受限路径的证据子链；历史 run 的启动前提、完整原生导出链和实际动态器件方法仍未闭合。这个结论是证据不足，不是后端能力缺陷，也不否定已有数值观测。

## 身份与审查覆盖

包 `open-evidence-proof-draft/REVIEW_PACKAGE_MANIFEST.json` SHA256 `4137f4a482c1c6a1a48a0ac4333a820be1cf671e0cf6410e4b873a80b0b5cfa8`。独立核 79 个包成员的 hash/bytes 全匹配；七 draft 合并的 534 个唯一附件 hash 全匹配。每 draft 抽首末两 scope，共14：原冻结六输入 digest、实际对应字节、原 raw manifest 的 compiled digest 以及完整实际 argv digest 全匹配。261 个 eligible scope 是附件完整候选，390 原 RESULT 中其余129留在 inventory，不是从科学分母删除；本次没有重复逐项验证全部261 scope，复用 integrator 的原始集合核验。

独立记录 `astra-open-claims-4137-audit.json`。阅读 CLAIMS.md、七 draft claims/reviews、NG 已安装反汇编关键分支、NG/GN STARTUP_METADATA、GN main/config/STORAGE/IDT/s_tr_swp 相关源码。没有远端、没有重跑科学槽，没有递归证明全部内部代码。这里的安装源码归因依赖已有可信构建证据，不称位级重建。

## 可以认可的证据，仍不能批准的轴

| 范围 | 当前可认可事实 | 历史 run 资格结论 |
| --- | --- | --- |
| 安装与 artifact identity | 固定镜像/二进制取证相连；本次附件、抽样原输入/argv/compiled hash 可核 | 只闭合这些文件身份，不闭合动态加载、startup 或数学正确性 |
| NG runtime | 同 pinned binary 的显式正 TMAX/TSTOP 参数传递及 min 路径已有受限静态链；旧误读 +0x258 没被采用 | 无 startup aliases/覆盖等前提未证；不能为这些历史 scope 标 qualified |
| NG native/export | OUTpData 与 AddRealValueToVector 的直接存储、writesimple 非 lpr 绕过重采样、直写数组分别有证据 | 实际 interpolated 状态及 v(node)→向量/scale 链未闭，unknown |
| GN runtime | 固定源码的 effective dtmin=max(option,cap/dtratio)、TIME_t round-to-tick 有证据 | 实际 startup/loader 前提未闭；即使闭合，mapped cap 不严格相等仍 unknown |
| GN native | 正常收敛 accepted/alltime 路径有源码支撑，initfail/quitconvfail/rejected 是明确例外 | 节点 probe、startup/加载与逐槽正常诊断未闭，unknown |
| GN actual integrator | 具体 DEV_IDT 非初始历史缺失步、选中 mTRAP 时用梯形；time[1]==0 明确强制Euler | loaded plugin/生成器到compiled/method覆盖未闭，且不可称每一步都是梯形；unknown |

既有逐槽 legacy 配置 readback、数学数值与执行状态可以原样保留；不能由这张静态事实表提升 machine runtime/native/integrator。diagnostic_contract=per_run_validation_required 也不是 closed。完整日志内 absence、exit0 或形状吻合不能替代方法与来源链。

## 关键边界核查

NG AddRealValueToVector 的 f15b0 确实将 xmm0 原样写入 real array；扩容分支 f163d 调 dvec_extend 后恢复 xmm0，支持当前输入值的保留。OUTpData f16aa 确实读取全局 interpolated；它存在 false 分支不能证明原运行选择了 false。ft_evaluate 的函数节点路径 c867d 调 apply_func，故只读此函数不能认定所有 v(node) 已映射成原向量。四节点 quoted F03 实际186行可支持该次 exporter 修复，不补旧36未导出槽、更不证明临近 binary64 输入。

新 NG STARTUP_METADATA 明确在新容器 cwd=/work、HOME=/root 下取样。固定只读镜像内部的 /root 和系统 spinit 可以在路径/条件身份闭合后复用；宿主挂载 /work 的新 absence 无法逆推历史 absence。原 frozen manifest 非完整读前文件系统快照，运行后库存也不能自动证明启动时未有可变文件。/compiler 只读挂载亦只说明访问模式，不证明历史内容。没有额外要求穷举 libc/分配器；关键是可影响控制与向量来源的实际入口前提。

GN main:70–85 有系统 startup 优先 include、否则默认 plugins，然后 user startup 的分支。config.h 定义的 ./.gnucap/etc 搜索与 HOME 文件并非此次已采文件；metadata.files={} 明确是未采，不是不存在。installed mgsim library hash 证明文件存在，不证明科学 run load mgsim 实际选中该注册集或未被覆盖。

DEV_IDT::do_tr:629 将 _method_a 传入 integrate；STORAGE::precalc_last:61 来自 select_method，后者允许 HS_PARAM override。integrate:41–42 首历史时间为0时覆盖成Euler；:69–73才是mTRAP分支。这个启动例外应进入最终方法说明，不能以 method=trap 回显抹去，也不能擅自改卡片合同来容纳。ddt/laplace等不能由此一并认证。即使后续证据证明这就是合法实现策略，仍需区分“已确定实际方法”与“满足本卡方法合同”。

## d844 / f125 的部分批准表达风险

当前 draft reviews={} 且没有外部 approved hash，f125 caller 在执行 adapter 前就拒，实际不会升级，这是正确状态。静态 CLAIMS.md 也没有把 runtime 字符串说成现成批准。

但 **不能只补两份 review 并批准现有这些 runtime 字符串**：d844 的 runtime 门只比较 claims.runtime 的 mapping 和 cap，未合取 claims.startup。用固定 d844 合成校准明确验证：startup=not_closed、integrator=not_closed 但具体 runtime mapping 有效时，runtime=qualified，而 native/integrator=unknown。f125 仍以 integrator 等合取挡住完整 pass，但 runtime 轴已会夸大当前实际证据。

这不是当下未批准 draft 的已发生评分 bug，而是必须在最终批准时守住的前提。该 API 可用非 matching runtime 值表达 unknown，但不能表达“路径成立，历史前提未知”的 conditional qualified。此次采用最简单安全处理：**不提供任何七draft approved_proof_sha256，保留静态子链报告**。未来若只需批准部分轴，创建新 immutable proof 身份，把尚未闭合的 runtime/native/integrator 都明确 not_closed，并另审它的实际输出；不要批准旧 draft 后依赖最终 pass gate 掩盖轴级错误。

## 已排定补件的裁决范围

最后一轮既定静态补件足够针对当前问题：NG beginPlot 的 interp 设置、v(node)函数映射/直接向量与scale、必要扩容路径；GN startup查找与固定镜像文件、load mgsim/注册绑定、节点probe和实际method覆盖。无需为了本报告另开远端或递归追完所有内部函数。补件只按它实际覆盖范围追加结论。

历史可变 /work 若依然无法由原生成/复制/执行的读前闭环复原，应永久保留该历史 axis unknown；新容器和新负控最多支持新身份运行。新实际 initfail/quitconvfail/rejected 或 interp/linearize 负控是独立机制证据，不得回填不存在的历史记录。真实失败、未知和所有原始分母继续保留。

README 中“等待旧 helper/source 到达”的若干句已被更新的 CLAIMS.md 超越，宜后续一并刷新，避免人工误认新增材料尚未取得；这不改变本次不批准结论。最终审批对象必须是新包精确 SHA，并经实际双审重新确定，而非引用本报告作为闭合证明。
