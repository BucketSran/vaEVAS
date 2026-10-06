# 新纸面批次的后端准备

本目录准备 [core-v1 cards](../../../evas/validation/paper/core-v1.json) 的
12 个条件与 48 个四后端配置，不改变旧比较器的固定 32 配置计划。
数学判据与评分由 `evas/validation/paper/` 拥有。输入冻结与资格适配本身不运行后端；有限执行器也不判定条件通过。

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
Spectre 有效设置 readback 检查请求值。EVAS 当前响应没有应用设置读回，
只保留 request_echo 与真正 observed_response 的 engine/accepted_steps，实际
容差/maxstep/stop 标为 unknown，状态 I。ngspice/Gnucap 尚无最大步长与
stop readback 资格，会保存 available 实际读数及未知项、状态 I。
收尾 `DIRECTORY_BUDGETS.json` 与最终 `EXECUTION.json` 保存实际每条件文件字节数，
超过 256 MiB 标记 condition_directory_limit_exceeded 并保留此前执行状态。
RESULT/record 是收尾前执行快照，最终目录预算以 EXECUTION 和 DIRECTORY_BUDGETS 为准。
这只是终态检查，不是运行期间硬磁盘配额；单文件仍由 FSIZE 限制。
所有输出行来源初始为 unknown，独立误差/native_initial/native_phase/计数
证书必须由后续实际资格证据补齐。普通 t=0 插值不能冒充 initial_step 已 settled
的原生初始值。历史失败与新结果分别保留；具体远程分配由协调者管理。
