# ADC 首题实际校准（2026-10-07）

修正后的参考解在四个冻结场景全部通过，完整 Harbor0.23 oracle Trial reward=1、
exception=null，约147秒完成。六个原错版均完成真实 Spectre transient并得到有效拒绝。
原old-code同时提前推进n，破坏最后时钟下降沿及done时刻，只证明整体不合格；不能当作
提前读取专项检出。随后独立负例仅移动读取与sample记录，保持n/clock/done，实际仅因
`sample time mismatch`拒绝；其波形、原始总线和线性度CSV先通过。因此新增专项证据不覆盖、
替换或删除原10个结果。离线重组old-code分析另存，不能当作实际同候选仿真。

修复只给Spectre options添加实例名；reltol、vabstol、扫描、阈值及评分合同不变。
原未命名options导致的SFE-709首个失败完整保留，未评分。
修复前回归为red，修复后cached Harbor环境28项回归通过；本地process fixture只证明接入。
真实执行源是原候选两处输出路径的受控重定位，记录原件/执行件SHA及inverse_verified。

| 阶段 | 主求解尝试 / 完成transient | 预检求解尝试 / 完成 | 版本查询 |
| --- | --- | --- | --- |
| 原SFE-709失败 | 1 / 0 | 1 / 1 | 1 |
| 修正后原10项 | 10 / 10 | 10 / 10 | 10 |
| 隔离提前读取 | 1 / 1 | 1 / 1 | 1 |

全部实际版本为Spectre21.1.0.509.isr12，固定外部harness c80ac7af。
数值源码revision c826fd17；完整输入、逐job候选/包/criteria与归档SHA及拒绝原因见
[compact receipts](calibration-20261007.json)。每job归档verified并取回，harness主/预检
cleanup均确认；对已知worker、owned进程组与jobpath的uid608原始/proc审计无live匹配。
两次校准通道均显式释放，无盲重试。

主求解90秒、预检15秒、版本30秒，共享job180秒；输出268435456字节是regular-file
大小轮询阈值，约50ms，并非硬磁盘配额。Spectre +mt=1不证明宿主CPU/RSS限制。
Harbor读回NanoCpus=1e9、Memory=1073741824（1GiB）、MemorySwap=2147483648
（配置的memory+swap共2GiB）；没有据此测得实际swap使用或2GiB总RSS。StorageOpt为空，
2GiB磁盘只是task请求。oracle容器仅trial/log绑定，隐藏checker/cases及宿主private/config
无挂载或路径可见；oracle按协议上传reference，模型隔离须另验，不能混称。

原始日志和archive保留在ignored `runs/adc-linearity/night-20261007/` 的原失败、
`netlist-fix/`及`isolated-early-read/`，未入git。此证据为本地PR94候选校准，
不是已合并支持、公开复现、模型难度或新论文benchmark范围。

## 本地模型原型尝试

仅冻结题面instruction SHA10302ee9，分别向gpt-6.1-sol与glm-5.3发起一次
instruction-only生成；零工具、零反馈、零重试。模型工作目录与仓库分离，不传入reference、
checker、隐藏cases、前次失败或评审。Codex隔离home仅认证，忽略用户配置/规则并关闭工具与技能；
GLM safe-mode关闭自定义上下文，tools为空、strict空MCP，无续会话。两次均完成CLI调用。
这不是真实工具交互Agentic评测，也不证明难度。

Codex0.160.0请求gpt-6.1-sol，约140秒、rc0、1 turn、0工具事件，usage完整保留；
实际事件和stderr无served-model身份，不能将请求名当实际模型。原候选保存，未评分。
GLM使用Claude CLI2.1.284，请求名及modelUsage/canonicalModel为glm-5.3，约250秒、
1 turn、success/end_turn/completed，费用$0.480949；这是CLI报告身份，不是独立服务证明。
可见result为188字节探索环境叙述而非VA，既有提取器补换行后候选为189字节；
原文和冻结身份保持不变，没有修复或重新生成。CLI报告output_tokens=19002、
thinking_tokens=0，与可见result长度不同；其余output token去向未知，不推断隐藏思考、
中间消息或计费原因。modelUsage/canonicalModel一致仍是CLI报告事实，不是独立服务身份保证。

此前作者辅助Python脚本直接向`source_contract`传入`read_text()`的str，出现
`TypeError: a bytes-like object is required, not str`；这不是完整verify CLI失败。
原异常保留在ignored qualification/MODEL-STAGE-RESULT及对话tool结果；当次完整argv、
异常栈和checker SHA未单独采集，不补造。已知导入路径为本题tests/verify.py，之后仅将
辅助调用参数改为`read_bytes()`；checker源码无变化。成功CLI的checker SHA ba6cc241
单独记录，不能冒充当次已采集的失败身份。

对该189字节原件实际运行现有checker CLI，rc0，status=`submission_contract_violation`、
reward=0、cases为空，原因是叙述中的反引号不符合允许的include合同。source_contract分支
发生在查找Spectre、版本子进程和场景求解之前：新增主求解、许可证探针、版本查询、remote
调用均为0。该分数是本地提交合同0分，不是Spectre数值0分或成功Harbor模型端到端试跑。
完整CLI、输入/输出SHA与usage见compact receipts；本地structural使用完整四场景cases文件，
其SHA与数值执行的一场景过滤包不同，候选字节与checker保持固定身份。

参考与负例已验证任务的数值评分链路，实际oracle已验证Harbor接入。模型层仍没有两个成功
Harbor端到端Trial；Codex缺少实际named-model身份，GLM是有效的本地提交合同失败。
[设计Issue72](https://github.com/BucketSran/vaEVAS/issues/72)将评分接入、真实Agent流程与任务效果
分开验收，长期主评测为Agentic、one-shot作对照；本轮受限原型不替代该长期验收。
[ADC设计稿](../../benchmark/examples/adc-linearity-measurement.md)要求模型试跑且不宣称强模型
调试后持续失败。上述两次attempt满足已授权的本地生成尝试，不能因此宣称完成长期主评测、
确定任务区分度或PR已ready。任务数值功能验收与named-model身份缺口分别报告。

## 实际输出大小与审查处理

从已取回的tar逐regular member读取未压缩逻辑长度，并对压缩文件做本地stat/hash。
11个完成数值校准job的主PSF各约85.6MB，全归档payload各约86.5MB，而gzip归档各约1.56MB；
压缩大小不表示原波形缺失。原10项未压缩全部payload共865045878字节，压缩归档共15590840字节。
逐job精确主波形/主PSF/预检PSF/run及全归档payload和compressed大小在compact receipts。
原SFE-709失败也另记大小，只有预检PSF，不能当完整主波形。
REMOTE_PLAN的60–150MB/场景、0.6–1.5GB合计仍为计划估算，实测为另一组数据。
这些是取回时的归档逻辑大小，不是实时峰值或磁盘allocated bytes；原始events未观察到输出超限，
本轮未实测超限取消路径。268435456字节约50ms轮询阈值仍是实际限制，不能改称硬quota。

实际GLM审查F-01采用真实失败位置澄清，缺失采集项明确unknown；F-02披露token差额未知、
保留CLI模型元数据；F-03补全部raw归档大小并区分压缩及估算；F-04补Memory/MemorySwap一起读回。
以上仅修正文档和精简证据，没有新模型、remote、Spectre或生产源码变更。
