# ADC 首题 Spectre 首批校准计划

状态已由实际校准更新，结果与限制见[校准证据](CALIBRATION-20261007.md)。以下保留调度合同。输入已冻结；
部署计划中的资源请求与有效限制须分别记录，实际运行前由协调者核对版本、授权和资源。
它不记录第二份任务进度。

输入是 `benchmark/tasks/va08-adc-linearity/tests/cases.json`、原创reference与
`prepare.py`产生的六个错版。`prepare.py`生成各ADC、网表和candidate的 SHA256 manifest，
执行时保存同一输入身份，不在运行中改阈值、容差或求解设置。
四个计分阈值数组均不同于public器件：均匀平移、四周期码宽、重复阈值与端区扩展。
场景名保留原名用于固定调度；不同输入需要新task version与身份，不能复用旧包。

| candidate | 场景 | 独立预期 |
| --- | --- | --- |
| reference | ideal-fast / alternating-slow / missing-code / endpoint-shift | 四项全部通过 |
| old-code | ideal-fast | samples.csv读取时间不符；转换尚未更新 |
| missing-first | ideal-fast | 缺少index0，样本记录少于4096 |
| missing-last | ideal-fast | 缺少index4095，样本记录少于4096 |
| all-samples | endpoint-shift | 内码DNL分母错误，原始bus重算不符 |
| reversed-bits | alternating-slow | 逐次code与原始bus/阈值真值不符 |
| ideal-only | alternating-slow | 非均匀码宽的DNL/INL不应全为0 |

共10次场景仿真，这是定向校准分母，未计划28次全交叉。参考解正常后才归因错版失败；
若真实ADC不符独立真值，停止判候选并保留环境错误。非目标编译错误也不能证明该错误类别
被checker拒绝，需要修复校准资产后重跑受影响病例。

每场景固定 stop=4.102ms、maxstep=20ns、conservative、reltol=1e-6、vabstol=1e-9。
[task.toml](../../benchmark/tasks/va08-adc-linearity/task.toml) 请求的1 CPU、1 GiB内存、2 GiB磁盘
属于Harbor容器环境；远端Spectre在宿主运行，是另一层。requested字段不能证明宿主硬限制，
当前计划不宣称宿主CPU quota、总RSS上限或cgroup隔离。

远端按既有harness串行提交，每个job终止且取回收据后才提交下一个。Spectre的 `+mt=1`
是线程请求；[checker](../../benchmark/checkers/adc_linearity.py) 对单次主求解设置90秒timeout，
每job的实际license/标准include preflight探针等待上限15秒，版本查询上限30秒。
部署profile的180秒单调时钟deadline由preflight与checker共享，不提高主求解90秒上限。
本题计划10次主求解加10次preflight求解；10次版本查询另计时间，不算求解。
原900秒只是10次主求解的名义上限，不包括preflight、版本查询、解析及cleanup开销。

固定c80 harness的 `max_output_bytes=268435456` 检查job目录内regular files的大小总和，
约每50毫秒轮询，发现超限后清理它拥有的进程组。它不是硬磁盘quota或单文件256 MiB限制，
可能暂时超限，也不限制目录外文件。PSF ASCII保存13个字段，约205k基础时间点另加边沿点，
预计单场景60至150 MB，10场景约0.6至1.5 GB；这是估算，不是实际大小或宿主quota证据。
修正后实测取回主PSF约85.6MB/场景、全部payload约86.5MB/场景，gzip归档约1.56MB；
逐job精确stat/tar logical bytes见校准JSON，不等于运行中峰值，本轮未触发或实测输出超限取消。
正式profile需显式配置该256 MiB轮询阈值，不能使用32 MiB默认值后在运行中悄悄调整。

Harbor verifier保持600秒预算；实际四场景oracle Trial约147秒完成。这仅证明本次参考
可在预算内完成，不能用该结果推断后续所有候选均足够。

参考解执行 `tests/test.sh` 全四场景；各错版执行 `tests/test.sh --case <表中场景>`。
每次设置独立 `VERIFY_OUTPUT`，设置 `CANDIDATE` 与 `SPECTRE`绝对路径。checker仅重定位两个固定文件输出路径到场景私有目录，保留原件/执行件及映射。
每job使用场景私有输出目录，首批调度仍串行。记录 `spectre -W` 实际输出、输入身份、完整日志、
退出码与波形身份。目录中有旧产物时换新目录，不能据此复用reward。

本地 Python 语法、渲染身份和24项checker/接入行为回归（另有3项安装Harbor依赖后执行）可执行；本机没有 Spectre/openvaf。
Icarus Verilog 不接受 Verilog-A，不能充当VA语法验收。
VA真实编译、浮动电压输出节点、总线端口展开、timer及文件I/O须由首个reference病例检查，
仅静态阅读网表和原创VA不能证明框架可执行。

## 已有harness接入

使用 `alphaapollo.common.execution.chips.benchmark_remote.RemoteBenchmarkSpectre`，
由原harness负责SSH、job去重、preflight、进程预算、归档和artifact回收。
本仓adapter只声明任务包及汇总任务分数，不替换或修改harness。
每job单场景，避免四场景PSF在同job内累计超过上述256 MiB regular-file总大小轮询阈值。
该阈值触发后的清理不是硬quota；保留实际输出大小、超限与cleanup收据。

本地准备命令：

```sh
python3 -B experiments/adc_linearity/harness_adapter.py   --harness-checkout /path/to/circuits/harness   --candidate benchmark/tasks/va08-adc-linearity/solution/reference.va   --output runs/adc-linearity/harness-reference
```

错版加 `--case <上表场景>`，输出另用新目录。输出含原始 frozen candidate、
四个或一个私有task包及身份报告。正式部署profile须满足harness
`docs/chips/BENCHMARK_EVALUATION.md` 的license/dependency实际probe要求。
旧rc.profile.json形状不自动满足该协议。现有服务器bundle与私有profile是否就绪待核实，
不能用脚本存在、构造probe或仅版本查询冒充许可验证。

宿主私有配置包含 `harness_checkout`、`remote`、`private_root` 三个字段，配置权限0600。
`private_root` 是预先创建、当前用户拥有且权限0700的持久宿主目录。配置与该目录必须位于
task/trial及所有Harbor绑定挂载之外；adapter对原路径和解析symlink后的路径双向检查交叉。
每次运行在其中创建新的私有子目录，保存候选、任务包、传输归档、完整报告和异常。
本题仅接受本task的Dockerfile入口，拒绝额外Compose overlay、task docker-compose.yaml
及预构建docker_image入口；这些路径可能添加不反写Harbor `_mounts` 的宿主绑定。
Harbor verifier日志目录默认仍挂给agent，只写 `status`、`reward` 的最终投射；不能放隐藏包。
`remote` 显式包含harness既有host/python/bundle/profile/run_root/archive_root/upload_root路径。
配置内容不进入候选镜像，也不把它复制到任务源码。

```sh
PYTHONPATH="$PWD" uvx --from harbor==0.23.0 harbor run   --path benchmark/tasks/va08-adc-linearity --agent oracle   --verifier experiments.adc_linearity.harbor_adapter:ADCHarnessVerifier   --verifier-kwarg config_path=/operator/private/adc-harness.json   --jobs-dir "$PWD/runs/adc-linearity/harbor" --job-name oracle-integration -n 1 -r 0
```

这是既有实际入口。Harbor0.23.0、Docker、SSH、实际preflight、Spectre及artifact取回
已完成参考Trial；固定输入和执行身份见校准证据。
checker每场景失败只有在实际波形完整且完成独立判据后才标为graded。
编译失败或timeout经harness保持未评分，并保留首个失败，不能把该失败视为错版校准通过。

本地进程接入夹具使用明确标为 `PROCESS FIXTURE, NOT SPECTRE` 的独立进程返回人工PSF，
核对私有路径写入与原件/执行件身份；原harness project_report判定另作可选集成检查。它验证文件接入，
不执行VA，也不提供真实Spectre语法或数值证据。

私有目录创建、运行与结果投射共用受控错误边界。目录已存在时拒绝并保留旧证据；
候选造成公开输出写入失败时，仍只返回通用错误且不附原异常链，不自动换job重跑。

## 本轮已观察的边界

原10项实际校准为4参考通过、6错版有效拒绝；原old-code非专项目标另由仅提前读取的
独立负例补证，不替换原结果。完整oracle Trial通过、private路径与挂载审计通过；
oracle预期上传reference，不能当模型reference隔离证明。模型只完成两个本地one-shot
attempt，GLM原189字节提交由现有checker在Spectre之前判提交合同0分，Codex因实际
身份缺失保持未评分。模型阶段无remote、无求解/探针/版本查询，也未运行四次远端探针。
详细身份与证据见校准报告；没有两个模型端到端、Agentic能力或任务难度结论。

Harbor资源读回包括Memory=1GiB与MemorySwap=2GiB（配置memory+swap），不代表实际swap
用量或2GiB总RSS，也不约束远端Spectre宿主。GLM报告token usage与可见result长度不等，
差额去向unknown；作者str传source_contract的早期辅助TypeError与后续真实verify CLI分别记录。
