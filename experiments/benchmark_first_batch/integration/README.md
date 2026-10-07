# 扩展与集成首批工程

这五题是根据公开电路工程需求原创的研究工程。旧 v4 对应家族只提供选题方向，
没有复制未明确分发许可的代码，也没有继承旧成绩。所有题目使用电压域VA接口。

| 任务 | 新增工程行为 | 上下文 | 来源组 |
| --- | --- | --- | --- |
| integrate-tdc-measurement-chain | 时间测量、量化、状态与超时的端到端集成 | 完整原创小仓库 | original-tdc-chain |
| integrate-pipeline-adc-alignment | 两级数据与valid对齐、复位后重新填充 | 有边界的小工程 | original-pipeline-adc |
| integrate-iq-baseband-calibration | 锁存前向失配系数、逆矩阵校准、bypass与双路限幅 | 有边界的小工程 | original-iq-baseband |
| integrate-pll-hop-reacquisition | 连续相位跳频、打断重捕获、针对最新目标的锁定资格 | 有边界的小工程 | original-hopping-pll |
| integrate-agc-attack-release | 上一拍包络控制、不同attack/release常数、连续输出路径 | 有边界的小工程 | original-receiver-agc |

每题有3个隐藏实验与4个语义负例。原始未完成工程在题目的environment/public中，
参考工程在solution中，负例在本目录mutants中。TDC还提供目录化的接口文档、
Makefile、公开回归和可执行自测入口，明确标为原创工程，没有工业历史暗示。

## 独立判据

`benchmark/checkers/first_batch_integration.py` 检查波形完整性、每个稳态窗口内全部采样、
独立预测点及精确状态边沿。它不读取参考VA，也不使用参考波形定义真值。
任务cases由公开合同的事件账本或闭式公式产生，生成器不执行参考解。

- TDC按输入事件配对推导量化码、忙期重触发、超时、饱和及复位状态。
- Pipeline按上升沿采样码与输出延迟推导每周期结果；valid单独检查边沿数及时间。
- I/Q实验用前向失配矩阵注入已知I/Q点；输出预期是原始点，另检查bypass及限幅。
- PLL依据分段一阶响应的闭式频率和相位积分检查每个实际输出采样点，锁定按误差阈值和连续dwell定义。
- AGC依据明确的两寄存级延迟和attack/release递推推导增益，输入变更后、clk之前检查连续信号路径。

隐藏实验没有扩展公开合同。输入、参数范围、端口和容差均在题面公开。各题不同
参数是同一道题的条件，不增加题数。参考提交通过也不证明实际Agent能完成。

## 本地检查与实际校准

```sh
python3 -B -m unittest discover -s experiments/benchmark_first_batch/integration -p test_checker.py -v
```

本次14项checker/合同测试通过。它们使用合成行数据，未执行VA，不能记作Spectre校准。

实际仿真使用协调者维护的 `circuit_task` 共享入口与现有circuit harness，
全任务Spectre并发由协调者统一限制为4。任务tests/verify.py导入本checker，
共享runtime及checker副本由协调者冻结打包，单case入口例如：

```sh
python3 benchmark/tasks/integrate-tdc-measurement-chain/tests/verify.py \
  --candidate benchmark/tasks/integrate-tdc-measurement-chain/solution/dut.va \
  --output runs/integration-tdc-reference --case pairing-timeout-reset
```

每题应运行参考解、未完成起点及每个语义负例，并保存源码、checker、配置、Spectre身份。
当前SOURCE和integration.json保持pending；实际校准后应维护这些状态，并保存精简校准摘要。
Harbor oracle、Agentic主评和公开后端重评是另外的验收阶段，当前没有完成声明。

生成器 `build.py` 可以从原创定义重建全部五题。它初始化状态为pending，已经追加真实
证据后不得直接运行并覆盖SOURCE或校准状态；需先维护生成器对应记录或保留已校准元数据。
完整波形、原始工具轨迹与大日志属于ignored runs，不进入本目录。
