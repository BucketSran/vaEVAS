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
python3 -B -m unittest discover -s experiments/adc_linearity -p 'test_*.py' -v
python3 -B experiments/adc_linearity/prepare.py --output runs/adc-linearity/prepared
```

前者检查人工构造的完整输入、clk、done、dout 波形及结果文件，fixture 从整数码宽
直接展开码流。checker 用阈值二分查找计算独立真值。参考解本身没有在本地模拟器执行。
后者只生成固定输入、参考解、六个错版和 SHA256 manifest，不启动仿真。
六个错版覆盖五类错误，端码漏计分别生成 first/last 两版。

实际接入使用已有 circuit harness 的 `RemoteBenchmarkSpectre`，不使用旧初筛的SSH bootstrap。
[接入说明](../../../experiments/adc_linearity/REMOTE_PLAN.md)记录冻结包、私有profile及Harbor入口。
`harness_adapter.py`生成每场景一个私有task manifest，并用harness实际API核验候选与包身份；
`harbor_adapter.ADCHarnessVerifier`下载原始候选，调用既有持久job协议并回收校验过的归档。
这些本地接口已做package/transfer校验，实际SSH和Harbor Trial仍未运行。

候选写文件的两处固定 `$fopen` 路径，由受信checker重定位到各场景私有 `output/`。
原始候选完整字节及SHA保持不变，实际执行源另存完整文件和SHA，记录 `adc-output-paths-v2`
及两个路径映射，并对执行件反向替换后的完整字节作相等检查，包含CRLF。
词法识别只检查活动调用，注释和字符串内容不视为调用；宏指令不受支持。
除两个路径token外不改变模拟或测量逻辑。不能称实际执行源逐字等同原候选。
不会在服务器创建全局 `/work`、清空共享输出或另建执行控制器。

首批校准是参考解通过所有4场景，六个错版各用一个指定场景拒绝，合计10个独立job。
每场景4096转换、停止时间4.102ms、maxstep20ns、conservative、reltol1e-6、vabstol1e-9。
单场景仿真timeout90秒、版本探测30秒、单线程。每job的preflight与checker共用harness profile期限。
调度方明确1 CPU、1 GiB内存、2 GiB累计磁盘及单job256 MiB目录输出配额。
runner记录 `spectre -W` 实际输出与返回码，非零或空版本输出停止该候选；保留命令、返回码、
两份源码身份、输入/波形身份和逐场景判分。PSF逐行解析并复用signal key，不驻留全文及splitlines副本。
缺许可证、原始总线不符合同、checker错误、编译或超时导致未完成仿真均保持未评分。
完整仿真后格式、激励及统计不符产生有结构化证据的candidate失败。
版本尚未实际运行核验，不能把准备文件当执行证据。

私有 `tests/cases.json`、checker、reference 不复制进候选 Docker 镜像。
候选仅获得 `environment/public` 开发器件。Spectre执行时使用受控写文件合同，
checker拒绝其他文件打开与非标准include。运行器还必须保证task目录不挂载给candidate。
Harbor默认verifier日志目录仍对活着的agent可见，不能用它保存私有资产。adapter要求
配置指定task/trial及所有绑定挂载之外的0700持久 `private_root`，包括symlink解析校验；
仅最终status/reward投射到日志目录。该隔离仍需实际Harbor运行验证。
四个计分阈值数组均与public开发器件不同，task版本为 `adc-linearity-v2-local-candidate`。
