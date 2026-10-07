# 规格建模与修复首批资产

规范生成入口是 `build.py`，独立评分是 `benchmark/checkers/first_batch_model_repair.py`。
本目录建设五个规格任务、四个新修复任务，并登记复用现有 va07 三角波原型，共十个任务。
生成器没有复制历史 Verilog-A，SOURCE 逐题说明架构需求参考和原创合同；旧题的许可和成绩不继承。

```sh
python3 -B experiments/benchmark_first_batch/model_repair/build.py
python3 -B -m unittest discover -s experiments/benchmark_first_batch/model_repair -p test_contracts.py -v
```

生成器会覆盖本工作流拥有的九个 task 包，不触碰 va07。运行前保留正在人工修改的任务。
规范 checker 副本和 `circuit_task.py` 由协调者按共享执行协议打包，并记录 SHA256，生成器不伪造接入完成。

每题有一个公开场景、两个私有场景、原创参考 VA 及至少三个语义负例；锁存比较器另有异步复位遗漏负例。修复题另有公开 starter。
行级测试用独立事件日历、电荷递推、资格计时队列和解析指数轨迹检验评分，不能当作 VA 仿真。
实际 Spectre 校准须记录参考两场景通过、所有负例各自完整编译/仿真后被拒绝，环境失败保留且不评分。
Harbor oracle 和 Agentic 模型试跑分别记录，参考通过不证明整个过程接入或任务有区分度。

## 独立判据

- 锁存比较器按锁存差分输入与公开再生延迟式产生事件，按独立复位事件检查决策前取消、正负决策后异步清空、短时钟取消及完整保持段。
- CDR 判相器根据 data/clk/retimed 的输入关系产生方向请求，检查两个方向及全部结束边沿。
- ΣΔ 用有理数累积电荷重算每个决定，不以参考输出为正确性来源。
- 采样保持按恒定输入窗口的指数响应检查采集、保持和复位；候选可使用等价动态实现。
- UVLO 从 PWL 阈值实际交点建立可取消的资格计时，检查短毛刺不累积与复位后的重新确认。
- SAR 从外部输入真值独立决定逐位试探码，检查中止、待发布结果取消、零码及再次转换。
- ZOOM 用相位日历核验九路时钟、全部脉冲数及相位关系；计时量化容差公开，不以累计RMSE掩盖漏脉冲。

所有新题是电压域行为工程任务，未声称晶体管级测量真实性、噪声/负载/电流能力或开源复现。
`benchmark/first_batch/model_repair.json` 保存任务清单与当前状态，实际校准收据由协调者维护。
