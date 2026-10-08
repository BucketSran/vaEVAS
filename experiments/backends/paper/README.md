# 新纸面批次的后端准备

本目录准备 [core-v1 cards](../../../evas/validation/paper/core-v1.json) 的
12 个条件与 48 个四后端配置，不改变旧比较器的固定 32 配置计划。
数学判据与评分由 `evas/validation/paper/` 拥有。输入冻结与资格适配本身不运行后端；有限执行器也不判定条件通过。

[PR #108 固定候选的 12 条件工程重放与实际 Spectre 配对](integration.md)
保留有限数值结果、窗口内阶段差及资格缺口。它不代表 main 支持，也不覆盖原论文表。

```sh
python3 -B -m unittest discover -s experiments/backends/paper -p 'test_*.py' -v
python3 -B experiments/backends/paper/inputs.py runs/paper-a1-inputs-NEW
```

输出目录必须新建。冻结内容包括卡片原字节、每配置的精确 `dut.va`、
后端 deck、真实顶层绑定、请求设置/时间、观测要求、适配器源码及其身份。
`verify(root)` 核对文件集合、哈希、大小和 12×4 计划。
SI-01 原源码中的 `paper_isolation` 顶层包含 A/B 两个真实实例，所有后端
都请求该顶层，不能用外部平铺请求替代该条件。

请求网格包含全局最多 200 ps、规定窗口内最多 20 ps 间隔、所有名义中心和
anchor。Spectre 请求 200 ps 全局步长，加共同网格的 `strobetimes` 和
`strobeoutput=all`。EVAS 请求同一网格和 200 ps 最大步长。ngspice/Gnucap
增加与 DUT 断开的理想 PWL 辅助源：只共享 ground，不连接 DUT 端口或刺激；
在规定窗口点、名义中心和 anchors 请求时间断点。全局 maxstep 保持 200 ps，
Gnucap 额外请求 `trace alltime` 保存内部接受步。辅助源属于新 deck/输入冻结，
不增加条件数量。`breakpoint_requests.json` 保存有 ID 的请求和两倍行数规划估算，
当前全部 12 条件的估算在 32 MiB/文件、256 MiB/条件内；自适应步数可能超过估算。
实际输出大小、安装版断点与保存语义仍须小型 preflight 核验，再由协调者决定矩阵。
`requested_times.json` 是共同观测义务；请求文件不能证明 accepted 或准确中心。
[观察方法与运行前资格路径](OBSERVATION_METHODS.md) 列出 primary 源码依据、
原始证据与未知项，准备状态不代表后端比较完成。
编译器是否接受原源、deck 是否有效、工具版本/二进制/镜像身份及有效设置
在准备阶段均未知。`qualification_requirements.json` 保留这些待办。
准备文件不是实际比较证据，实际执行须先由协调者批准冻结批次并绑定工具身份。

`read_native(path, backend)` 复用已有 CSV、Spectre ASCII PSF 和 SPICE 文本
读取器，完整保留时间与数值。格式解析不证明原生采样或准确性。
`normalize_observation(card, backend, rows, origins, qualification, contract=...)`
保存原行与逐行 `accepted`、`interpolated` 或 `unknown` 来源，并报告缺列、
非有限值、重复时间、截断、实际全局/局部间隔和精确中心行。
它不重采样、不修补缺失输入、不消除 modulo 端点原始值。

资格字段与 checker 的 `assess_observation` 接口对齐。时间、电压和实际输入
不确定度必须独立给出，且 `qualification_evidence` 按 source/time/voltage/inputs
和 native_initial
及适用的 native_counters/native_phase 角色记录 `{method, artifact_path, sha256}`。
适配器只核验可读取证据的哈希及声明，科学误差界仍需审查 method 报告。
哈希是证据绑定；调用方是受信任的资格审查入口，不是任意证书的认证器。
synthetic 测试只校准这个传输合同，不能成为实际后端资格。
缺证据时 `qualified=false`。密集网格、solver tolerance 与相互一致的后端
不能建立误差界。插值误差须单独有界并包含在总导出误差内；插值/未知记录
不会成为原生计数/phase 或精确端点证据。

`runner.py` 保留单后端固定 12 条件分母，只执行 allocation 明确选择的条件，输出目录必须新建，零自动
重试。`--tool-profile` 与 `--allocation` 都是必需的 JSON 文件，并由 allocation
绑定 INPUT_MANIFEST 和 profile 的 SHA256。实际运行要求 Linux、taskset/prlimit。
首轮可选 EV-SH-01/CP-02（各 launch cap=2），后续由协调者新 allocation 选择
此前未 launch 的其余 10 条，在新 output 执行。没有 resume 或自动 repeat；旧失败
不能被新输出替换。每份 EXECUTION 始终 12 项，其余明确 not_selected_in_allocation。
协调者与汇总器核对两份真实身份和累计授权，保持同一输入/tool/checker 分母。
此实现轮次没有调用后端或远程资源；以下接口供批准冻结后的执行阶段使用。

```sh
python3 -B experiments/backends/paper/runner.py INPUTS OUTPUT \
  --backend spectre --tool-profile PROFILE.json --allocation ALLOCATION.json
```

allocation 必需字段为 backend、input_manifest_sha256、tool_profile_sha256、
selected_condition_ids（非空、不重复、卡片中存在）、
max_simulation_launches/max_compilation_launches 均等于选择数且 <=12、stage_timeout_s<=90、
license_timeout_s<=30、memory_limit_bytes<=4294967296、file_limit_bytes<=33554432、
threads=1，所有上限必须正整数。容器后端因固定 factory 需恰好 4 GiB，
拒绝更低的分配，避免将 host client 上限误称为容器内存上限。字段记录既有授权，不新增授权。
profile.backend 必须匹配分配后端。各 profile 的必需工具身份字段：

- EVAS：kernel、kernel_sha256。版本/IR 通过真实有界 version query 核验；
  build_revision 缺失单独保留 unknown，不能凭 source hash 推断二进制 build。
- Spectre：binary、binary_sha256、setup_scripts、setup_sha256(path->hash)。
- 容器后端：environment、environment_sha256、environment_manifest_sha256、
  images(image name->config_id)；OpenVAF-R 另需 compiler_sha256。
  pinned 包清单、实际镜像 id/架构、组件版本在 preflight 验证。

源码/适配器/reader/runtime/checker 身份须与冻结一致。未集成 checker 的冻结
不能执行。工具二进制/setup/外部编译器在每条件前再次核对。
`process.py` 复用 bf06821a L3 的已审阅进程组生命周期：leader 在 TERM/KILL
前不 reap，每个退出路径清理后代；容器额外始终删除自有名称并核验不存在。
清理不完整或取消会终止该 lane，其余未执行条件显式保存 not_run。
逐条件源/工具/冻结输入身份核验异常也通过 finally 写出完整 12 项分母、
既有结果、真实 failure_stage 和 BATCH_ABORTED；容器清单每次先核验冻结 SHA，
不能通过同时更新包文件与清单绕过 preflight 身份。
容器设置实际 OCI fsize 限制，不把 host podman client 上限误称为容器上限。

成功退出但缺编译产物/波形、编译失败、运行超时、解析失败均分别记录。
不从错误文本自动推定 confirmed_unsupported；确认 U 需要后续具体证据。
编译/执行接受记录不替代 LRM 合法性资格。原始结果、命令、哈希与来源保留。
Spectre 使用 [settings_readback.py](settings_readback.py) 按单一具名 transient 的 Important
块与 PSF header 交叉回读；global user 和 tolerance.relative 另存，实际与请求差异
保留为 mismatch、状态 I。ngspice 要求单一 control/analysis、option→tran→wrdata→option
且中途没有可变设置命令，读取后 options；前默认快照另存。stop/maxstep 仅有 deck
调用证据，继续标为 unknown。读取器拒绝缺失、歧义、非法数值/量纲和多分析，
不会使用 requested 值回填。Gnucap 回读出现多个不同 parsed 值时保守拒绝，
不能用最后值替代歧义。解析错误防护只覆盖已校准的 `^ ?` caret 格式；
没有该诊断不能证明其他格式已覆盖。识别到该格式时拒绝设置资格。
这些控制值不证明数学精度或 native provenance。历史 reader 和冻结结果保留原身份。
EVAS 当前响应没有应用设置读回，
只保留 request_echo 与真正 observed_response 的 engine/accepted_steps，实际
容差/maxstep/stop 标为 unknown，状态 I。ngspice/Gnucap 尚无最大步长与
stop readback 资格，会保存 available 实际读数及未知项、状态 I。
收尾 `DIRECTORY_BUDGETS.json` 与最终 `EXECUTION.json` 保存实际每条件文件字节数，
超过 256 MiB 标记 condition_directory_limit_exceeded 并保留此前执行状态。
RESULT/record 是收尾前执行快照。汇总器入口为收尾后不可变的
`final-record-<condition>.json`，完整12项（含 preflight fail 与未选择条件），逐项内容
与最终 EXECUTION slot 完全一致并由 FILE_MANIFEST 绑定 SHA。旧 RESULT/record 保留
原状态，不能代替 final-record；最终目录预算以 EXECUTION 和 DIRECTORY_BUDGETS 为准。
这只是终态检查，不是运行期间硬磁盘配额；单文件仍由 FSIZE 限制。
所有输出行来源初始为 unknown，独立误差/native_initial/native_phase/计数
证书必须由后续实际资格证据补齐。普通 t=0 插值不能冒充 initial_step 已 settled
的原生初始值。历史失败与新结果分别保留；具体远程分配由协调者管理。

## 生成论文和 README 的结果表

`table.py` 只汇总实际 assessment，不执行后端或评分。主组来自 core-v1 的
`primary_group`，每条件仅计一次，固定 N=12、四后端 48 槽。structure 中的
SI-01 和 combination 均保留独立主组。设计卡的状态与本批实际结果分别显示。
每后端完整列出 P/F/U/X/I/T，细项链接保留 checker 原有误差、不确定度和
claim limit，不计算跨性质的最大误差比或计时。

先等待 lane 完成收尾，取得 `final-record-<condition>.json` 与 FILE_MANIFEST，
再调用 `criteria.assess` 或 `assess_observation`，collector 在其返回字典
外层追加 `execution_sha256`，P/F/I 还须追加 `input_observation_sha256`，
分别为此次终态 final-record 和实际读取的 observation.json 原字节哈希，再保存
assessment JSON。不得用新文件哈希给旧 assessment 重新贴身份。criteria 本体
不生成这些执行来源字段，也不需修改。再建立 records.json 数组。每个已评估条目使用以下结构；`path` 相对
records.json，`sha256` 必须是对应实际文件的 SHA256。哈希占位符不能运行。

```json
[
  {
    "condition_id": "VR-01",
    "backend": "evas",
    "assessment": {"path": "assessment/VR-01.json", "sha256": "ACTUAL_SHA256"},
    "execution": {"path": "evas/final-record-VR-01.json", "sha256": "ACTUAL_SHA256"},
    "identity": {
      "source_revision": "ACTUAL_EVAS_SOURCE_HEAD_OR_unknown",
      "tool": {"path": "evas/TOOL_IDENTITY.json", "sha256": "ACTUAL_SHA256"},
      "condition_started": {"path": "evas/runs/VR-01/STARTED.json", "sha256": "ACTUAL_SHA256"},
      "lane_started": {"path": "evas/STARTED.json", "sha256": "ACTUAL_SHA256"},
      "execution_manifest": {"path": "evas/FILE_MANIFEST.json", "sha256": "ACTUAL_SHA256"},
      "input_manifest": {"path": "frozen-inputs/INPUT_MANIFEST.json", "sha256": "ACTUAL_SHA256"},
      "observation": {"path": "evas/runs/VR-01/observation.json", "sha256": "ACTUAL_SHA256"},
      "method": "实际资格方法与报告路径，未知项须明确写出",
      "availability": "local-only"
    }
  }
]
```

```sh
python3 -B experiments/backends/paper/table.py runs/BATCH/records.json \
  --allow-pending > runs/BATCH/table.md
python3 -B -m unittest discover -s experiments/backends/paper -p test_table.py -v
```

默认要求全部 48 槽，缺失、重复或未知条件/后端报错。只有显式
`--allow-pending` 才将缺槽补为 T，可用于全 T 设计表或部分执行批次。
也可显式写 `{"condition_id":"VR-01","backend":"evas","status":"T"}`，
表示尚无执行结果的占位槽。若同时附 execution 引用，其实际状态必须为
not_run，不能将已有执行结果替换为 T。
P/F/I 必须来自 completed assessment 和 waveform_available execution，
且 assessment 的 input_observation_sha256、execution 的 observation 引用
和实际 observation 三方哈希一致，execution_sha256 与实际执行文件一致，
checker 绑定此卡片原字节。同条件的新执行不能套用旧 assessment。
无法从成功退出或波形存在推导 P。

U/X/T 使用 checker 的显式 execution_state，并核验实际 execution 状态。
X 仅接受 runner 的 compile_failed、compile_timeout、runtime_timeout、
execution_failed、execution_error、cancelled、cleanup_incomplete、
missing_compile_artifact、missing_waveform、observation_invalid、deck_parse_error、
condition_directory_limit_exceeded。
T 仅接受 not_run。U 必须为 failure_stage=compile 的 compile_failed，
另在 assessment 外层追加 unsupported_evidence 的 path/sha256 引用，
指向人工审查后的确认 JSON。确认内容为 status=confirmed_unsupported、
failure_stage=compile、execution_sha256、具体 reason 和 diagnostic 的
path/sha256。diagnostic 须为 execution.stages 中非零退出 compile 阶段的
实际 log，哈希必须匹配；嵌套引用路径相对其所在 JSON 文件。一般编译失败
保留 X，不能从错误文本自动推定 U。deck_parse_error 的 X 必须绑定
diagnostic_log_sha256 与实际 simulate stage/log、逐行 diagnostics 的编号/文本，
以及保留的 rejected_waveform 与 lane FILE_MANIFEST/实际 raw 的 SHA。
没有产生 raw 时 rejected_waveform 可为空。成功波形不能配 U/X/T。

同一后端的已执行条件必须具有相同的生产源码 revision、稳定工具身份、
完整 checker identity 和输入冻结 manifest 身份；所有后端使用同一 checker。
2+10 可分批，但不能拼接不同实现/判据/冻结输入的有利结果。
汇总器先按 INPUT_MANIFEST 核验冻结 ADAPTER_IDENTITY.json 和
CHECKER_IDENTITY.json 的原字节；lane.runner_sha256 须匹配冻结的 runner.py，
assessment 的 criteria.py/oracle.py 摘要须匹配该冻结 checker，并按
criteria.identity 的 `json.dumps({files, runtime}, sort_keys=True)` 重算顶层摘要。
此处核验历史冻结快照，不要求 checker 与当前工作区版本相同；不认证 collector
提供字段的真实性，也不防止 collector 全部重造证据。工具身份投影
使用 runner 已保存的 profile_identity、kernel/binary/image 身份、实际版本、
interpreter、环境身份和 compiler flags；版本 probe 的时戳、argv、日志收据
不参与工具相等判断。各次 TOOL_IDENTITY 原字节哈希仍分别保留在表中。

condition STARTED、TOOL_IDENTITY、final-record 和原始 source/deck 必须属于
该 lane 的 FILE_MANIFEST；源码还须与 execution.source_sha256、card.source
原字节及冻结输入清单一致，deck 须与冻结清单和实际执行目录原字节一致。
终态 execution 的 work/deck/condition_identity 使用 inputs/runner 已产生的字段，
汇总器不要求 runner 增加新来源字段。缺真实执行文件不能用自洽的标签代替。
已声明 waveform 的真实字节须与 execution.waveform_sha256 及 FILE_MANIFEST
三方一致；路径必须在 condition 目录内，可为 Spectre 的 psf/tran.tran.tran。
该核验涵盖这些已引用文件，不宣称遍历核验清单的全部 retained artifacts。

每个 condition/backend 只能有一个主结果，重复主槽仍报错。若已有复测，
collector 须在该槽追加 prior_attempts 的执行 artifact path/sha256 数组，
并给出具体 selection_reason；这些路径相对 records.json。例如：

```json
{
  "prior_attempts": [{"path": "previous-evas/final-record-VR-01.json", "sha256": "ACTUAL_SHA256"}],
  "selection_reason": "批准的复测采用此结果，先前超时原记录保留"
}
```

这两个字段追加到主条目，不替代其 assessment/execution。表格核验先前
记录的哈希、condition/backend/status，链接全部已声明 prior attempts，
不自动取最好结果，也不增加 N。collector 仍需在外部实际运行索引保留
全部尝试；此接口不能证明 prior_attempts 已穷尽所有执行，不宣称已解决
复测谱系的完整性审计。未执行占位与真实启动应分别保留。

表格验证 artifact 哈希与条件、源码/deck/tool 绑定，展示工具实际版本、
已声明源码 revision、方法和公开程度。源码 revision 须据真实构建来源填写，
未知则写 unknown；源树 head 不能替代工具 build_revision。表格不独立认证
方法的科学误差界。availability 可为 local-only、restricted 或 public，
public 另需 `public_url`，其含义仅为声明的发布链接。本地 raw 路径不等于
公开可复现证据，发布链接本身也不代表通过可复现性审查。


实际汇总应引用 lane 的 `final-record-<condition>.json`。其 JSON 内容必须
与该 lane 最终 `EXECUTION.json` 中唯一的 condition/backend 行完全相同，
assessment.execution_sha256 也须绑定这一终态文件。表格通过
FILE_MANIFEST 的哈希读取 EXECUTION.json，比较完整行，不只比较状态名。
晚于早期 RESULT 的目录预算裁定可能将 waveform_available 改为
condition_directory_limit_exceeded，必须汇总为 X；即使早期 RESULT 有合法
观测与 assessment，也不能覆盖终态。原 RESULT、record、日志和波形仍保留
为同次执行的早期快照，不增加 attempt 数。真正的先前运行继续通过
prior_attempts 与外部运行索引保留。

裸 T 仍表示明确的未执行占位，不要求不存在的 condition STARTED；
preflight 失败的 not_run 若附 execution_manifest，核验相同的最终行，
无需借工具/源码 STARTED 冒充实际启动。此规则不构造新的执行或复测框架。
