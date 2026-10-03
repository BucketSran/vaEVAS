# 真实来源 Verilog-A 能力初筛

目的：在扩建 vaBench 之前，先检验明确的真实工程行为规格是否仍能区分模型能力。
这 6 题是内部 pilot，不能代表全部 Verilog-A 任务，也不是已经发布的 benchmark。
首轮已完成：Codex `gpt-6.1-sol` 6/6，GLM `glm-5.3` 3/6。
失败诊断、解释边界和执行证据见[结果报告](RESULTS.md)。

| Harbor 任务 | 原始来源 | 首轮要检验的能力 |
|---|---|---|
| [va01-and2](../../benchmark/tasks/va01-and2/instruction.md) | 课题组 tangxy AND2 | 简单对照：阈值、电平和延迟 |
| [va02-sar-handshake](../../benchmark/tasks/va02-sar-handshake/instruction.md) | 课题组七位 SAR 控制 | 握手、逐位写入、CDAC 极性、复位 |
| [va03-zoom-timing](../../benchmark/tasks/va03-zoom-timing/instruction.md) | 课题组 ZOOM ADC 时序 | 九路输出、三级嵌套脉冲、参数变化 |
| [va04-gain-calibration](../../benchmark/tasks/va04-gain-calibration/instruction.md) | 课题组流水线 ADC 校准 | 两相采样、带符号差、步进方向和上下限 |
| [va05-dynamic-vco](../../benchmark/tasks/va05-dynamic-vco/instruction.md) | Cadence 安装库 dig_vco | 变频过程中的连续相位与边沿定位 |
| [va06-loaded-opamp](../../benchmark/tasks/va06-loaded-opamp/instruction.md) | Cadence 安装库 opamp | 电流贡献、内部储能、压摆/软限幅、外部 R/C 负载 |

每题的 `SOURCE.md` 记录原始文件和改编。原文件保存在
[reference/veriloga](../../benchmark/reference/veriloga/README.md)，没有覆盖修改。
未把原文件中未初始化状态或明显笔误作为隐含考点；必要改编已写入题面。
模型仅收到 `instruction.md`，不接触原始资产、参考解、测试输入和判据。

## 本轮协议

- GLM：已有 Claude Code 兼容渠道调用 `glm-5.3`；Codex：已登录 CLI 调用 `gpt-6.1-sol`。
- 两者请求 `xhigh` effort。记录 CLI 版本、实际返回的模型用量字段和完整输出；
  不将相同 effort 名称解释为相同推理预算。
- 每题每模型一次独立生成，共 12 个计划提交；无工具、无仿真反馈、无答案修补、无模型重试。
- 独立临时工作目录；Codex 临时 home 只复制认证，不加载个人/项目指令。
  GLM 使用 safe mode、空工具集和空 MCP 配置。两种 CLI 的底层系统提示不同，
  因此这是两个现有调用渠道的初筛，不是完全控制所有推理栈变量的裸模型比较。
- 只允许移除包住整个答案的一层 Markdown 代码围栏；其他内容原样提交。
- Harbor 0.23.0 管理隔离环境、trial、agent、verifier 和 reward。
  Docker 基础镜像固定 digest；模型调用在宿主机无工具 CLI 中执行，产物上传到容器。
- 已配置的 Spectre 主机负责评分。运行器尝试探测版本；历史机器报告的版本字段为空，
  本次整理未独立恢复版本记录，不能把探测动作写成版本已核验。
- 全部条件通过才得 1，否则 0；基础设施/判据异常不发模型分数，单独报告。
- 初始校准：6 个参考解、13 个仿真条件通过；6 个针对性语义变异均编译成功且被拒绝。
  变异覆盖不构成 checker 完备性证明。

数字输出用独立状态机/脉冲日历、稳定段电平及完整边沿计数/时间评分；
VCO 对分段线性频率解析积分并求半周期交点；运放使用独立 RK4 的电压轨迹和解析输入电流。
运放电压容差 4mV；其他阈值见各题 `tests/cases.json`。校准通过后冻结文件身份。

<a id="身份与再校准"></a>

## 身份与再校准

[FROZEN_INPUTS.json](FROZEN_INPUTS.json)保留首轮 60 文件 manifest 的原字节。
[CALIBRATION.json](CALIBRATION.json)保存六题参考解与错误版本的紧凑记录。
它们指向固定 Git 来源快照，首轮未提交源码也能从该提交取回；
本次补记共享 checker 与执行副本一致的身份，不声称它在运行前被单独冻结。

从仓库根目录可复核身份，无需 SSH、模型渠道或 Spectre：

```sh
python3 -B -m experiments.va_screen.identity --historical
python3 -B -m unittest experiments.va_screen.test_identity -v
```

检查器比较当前评分文件、参考解、生成器和评分适配入口与校准身份，
同时检查共享源码与执行副本一致、正/负校准条件齐全。CI 运行同一检查。
历史检查从固定 Git 快照核验全部旧文件；后续汇总/运行包装器的维护不改写旧 manifest。
新运行的 manifest 另外记录共享 checker、身份工具和校准证据。

评分源码、case 期望值、参考解、生成器或实际评分适配入口改变后，
应重做受影响题目的参考解/错误版本校准，并保存新的源码快照、manifest 和校准收据；
不能只把旧记录中的哈希替换成新值。新收据需明确复用哪些历史条件、哪些是新执行。
纯入口文档或结果说明改变不要求新仿真，更新相应说明及身份即可。
当前身份工具针对本次已登记校准；新行为需先更新有效校准记录，再启动新的模型实验。

## 运行

需要：Python 3.10+、uv、Docker + Compose、已登录且支持所选模型的 Codex、已配置 GLM 渠道的 Claude Code，
以及已有 SSH/Spectre 权限。认证由本机配置提供，不能写进任务、命令参数或 Git。
本机采用已有 `thu-sui` 和服务器私有 Spectre profile；可通过以下环境变量覆盖：

```sh
export VA_SCREEN_SSH_HOST=your-existing-host
export VA_SCREEN_SPECTRE_PROFILE=/absolute/private/spectre.profile.json
export VA_SCREEN_REMOTE_ROOT=/absolute/private/va-screen-runs
```

Profile 包含 `spectre` 可执行文件绝对路径、`setup_scripts` 路径列表和 `shell`。
这些部署信息只供运行器读取，不发给被测模型。远端使用 csh 加载已有许可证环境，
每个仿真单线程、许可证等待 5 秒、执行上限 90 秒。

从仓库根目录：

```sh
# 在 Codex 桌面内优先使用它自带的 CLI。旧 Homebrew CLI 可能不支持桌面的模型。
if [ -n "${CODEX_CLI_PATH:-}" ]; then
  export PATH="$(dirname "$CODEX_CLI_PATH"):$PATH"
fi
python3 -m experiments.va_screen.build_tasks
for va_task in benchmark/tasks/va0*; do
  python3 -m experiments.va_screen.remote \
    "$va_task" "$va_task/solution/dut.va" \
    "runs/va-screen/calibration/${va_task##*/}"
done
python3 -m experiments.va_screen.calibrate
python3 -m experiments.va_screen.run_pilot
```

`run_pilot` 要求六题都有与当前源码/判据一致的成功校准收据，然后保存输入 manifest，
调用两个 Harbor job，各自串行运行六题。模型生成失败不会自动改用别的模型。
宿主机须让 `docker compose version` 可用。Harbor 原生单题 oracle 接入检查：

```sh
PYTHONPATH="$PWD" uvx --from harbor==0.23.0 harbor run \
  --path benchmark/tasks/va01-and2 --agent oracle \
  --verifier experiments.va_screen.harbor_adapters:RemoteSpectreVerifier \
  --jobs-dir "$PWD/runs/va-screen/harbor" --job-name oracle-integration -n 1 -r 0
```

每题 `tests/test.sh` 也可在已配置 Spectre 的环境独立运行，默认从 `/work/dut.va` 取提交、
向 `/logs/verifier` 写 `report.json` 和 `reward.txt`；可用 `CANDIDATE`、`VERIFY_OUTPUT` 覆盖路径。
Docker 任务镜像不含商业 Spectre，默认 Harbor verifier 因此不能直接评分；
本轮必须指定上述 `RemoteSpectreVerifier`，或自行提供有许可证的 verifier 环境。

## 证据和解释边界

全部原始输出在 Git 忽略的 `runs/va-screen/`：校准、错误版本测试、Harbor trials、模型输出、
协议和冻结 manifest。每次远端仿真目录在 `report.json.remote_root`，保留波形、编译日志和输入。
本目录保存可从仓库获取的任务、冻结身份、[最终结果](RESULTS.json)与校准摘要。
原始模型输出/报告和远端波形仍是 local-only；保存了本地归档清单，没有公开下载地址。
材料没有上传 Harbor Hub；第三方资料与内部来源的外发规则见
[reference 使用说明](../../benchmark/reference/README.md#公开或外发前)。

全过只能说明这 6 道明确规格、这些参数和这些检查点下的一次生成表现；
不能推出整个任务族已经解决。若难题也普遍通过，优先减少这类模板实现题的开发投入，
再验证闭环系统集成、现有模型诊断/修复、拟合和需求到模型抽象等不同任务类型。
不要仅增加位宽或复制参数变体来制造题量。

已知限制：SAR 当前用预定反馈脉冲而非真实比较器闭环；校准题没有接入完整 ADC 模型；
运放明确给出了方程；一次提交无法估计稳定通过率；真实来源也不能排除模型训练时见过类似官方例子。
