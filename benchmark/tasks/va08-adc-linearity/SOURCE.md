# 原创来源与验证边界

本题是仓库原创资产，基于 [ADC 测量设计稿](../../examples/adc-linearity-measurement.md)
确定工程用途及有限扫描定义。没有复制、改写或分发 Cadence 安装库源码。
参考测量器、合成 ADC、开发网表和 checker 均在本次实现中独立编写。

状态是首题本地原型，实际 Spectre 校准、Harbor 容器运行和强模型试跑尚未完成。
因此不计入原六题初筛分母，不宣称公开主集、开源复现或 EVAS 支持。
完整验收目前依赖 Spectre，应按 Spectre 扩展集候选处理。

`samples.csv` 是经用户批准的合同补充。旧合同只输出内部254码时，少计首末端码
不能改变 CSV。立即读旧码也可能只改变两个端码的次数。实际输入/clk/ADC 波形正常
不能证明测量器在规定时刻读取。新增逐次记录用于核对样本数、读取时间和原始码。
`test_original_csv_contract_cannot_observe_endpoint_loss` 保留旧合同的实际可执行反例。
读取记录仍是候选输出，必须与 ADC 原始总线和规定扫描的独立真值共同检查。
本题不提供对恶意伪造程序执行过程的证明。

## 本地检查与远程准备

```sh
python3 -B -m unittest discover -s experiments/adc_linearity -p test_checker.py -v
python3 -B experiments/adc_linearity/prepare.py --output runs/adc-linearity/prepared
```

前者检查人工构造的完整输入、clk、done、dout 波形及结果文件，fixture 从整数码宽
直接展开码流。checker 用阈值二分查找计算独立真值。参考解本身没有在本地模拟器执行。
后者只生成固定输入、参考解、六个错版和 SHA256 manifest，不启动仿真。
六个错版覆盖五类错误，端码漏计分别生成 first/last 两版。

远端需复制任务 tests、生成的 candidate 与 `/work/output`，分别运行：

```sh
SPECTRE=/absolute/path/to/spectre CANDIDATE=/path/to/reference.va VERIFY_OUTPUT=/path/to/fresh/logs sh tests/test.sh
```

对每个错版用同一命令另建输出目录。首批校准是参考解通过所有4场景，六个错版各用一个指定场景拒绝，见 [远程计划](../../../experiments/adc_linearity/REMOTE_PLAN.md)。
每场景4096转换、停止时间4.102ms、maxstep20ns、conservative、reltol1e-6、vabstol1e-9。
单场景 timeout90秒，单线程，verifier timeout600秒。首批共10次仿真，
仿真墙钟上限900秒另加7次版本查询各30秒。调度方另设1 CPU、1 GiB内存、2 GiB磁盘预算，单文件上限256 MiB。
runner记录实际 `spectre -W`，命令、返回码、输入/波形身份和逐场景判分。
版本尚未运行核验，不能把准备文件当执行证据。缺许可证、原始总线不符合同或checker错误
均不给有效reward；编译、仿真timeout及结果不符则判候选失败。

私有 `tests/cases.json`、checker、reference 不复制进候选 Docker 镜像。
候选仅获得 `environment/public` 开发器件。Spectre执行时使用受控写文件合同，
checker拒绝其他文件打开与非标准include。运行器必须按Harbor的agent/verifier阶段隔离，
不要把整个任务目录挂载给candidate。该隔离仍需实际Harbor运行验证。
