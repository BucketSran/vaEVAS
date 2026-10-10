# 诊断与修复：五个完整工程合同

本目录建设 spec #136 的四个P1归口来源005、046、272、249以及case-0009多VA系统。任务、原starter、健康资产、参考修复、整体改写和合理语义错误版本已建立。当前完成的是任务构建与独立checker波形合同检查；实际Spectre校准、Harbor oracle和两种模型试做尚未完成，不能据此关闭spec或判断难度。

[manifest.json](manifest.json)逐来源记录任务；[run-plan.json](run-plan.json)是实际作者校准请求，每条包含固定task、候选目录、期望结果和行为差异。候选与任务均固定Spectre，尚不声称开源主集可复现。原始来源只在单模块`SOURCE.json`中引用，没有更改reference资料库。

`v2_repair.evaluate(rows, case, work)`只读取实际端口波形，从公开输入的阈值交点和时间合同建立期望。272按外部clk上升沿计阶段，046检查同步迟滞，005检查完整连续高资格和取消，249检查UP/DOWN历史、异步复位及挂起事件取消。多VA系统从vin迟滞区间推导pgood、连续10ns资格、resetb和enable，并核对下游activity计数。既要求危险条件禁止动作，也要求正常供电按时出现真实下游动作。

检查器忽略题面允许的输出平滑窗口，窗口外电压误差最多25mV；每个固定deck声明maxstep，采样稀疏、缺信号、非有限值和不完整区间不形成行为分数。错误版本必须产生完整波形后才能作为错版拒绝证据。编译失败不替代语义校准。

本地合同回归：

```sh
python3 -B -m unittest discover -s experiments/benchmark_v2/diagnosis_repair -p test_repair.py -v
```

这些手工波形检查覆盖同步复位后重新累计、去抖毛刺取消、迟滞恢复、PFD异步取消和多VA短恢复旧事件；明确验证错波形会失败。它们不运行VA，不作为健康版本或后端验收证据。

构建器按源身份建立四个单模块，再建立原创系统。重建会覆盖本类生成资产，已校准后修改源、合同、激励或checker均须重新校准。

```sh
python3 -B experiments/benchmark_v2/diagnosis_repair/build_tasks.py
python3 -B experiments/benchmark_v2/diagnosis_repair/build_chain.py
```

多VA的主故障是在短恢复期间留下旧释放deadline；再次恢复会提前释放，实际下游计数随之过早开始。根因集中在释放模块，但UVLO迟滞、使能与有状态下游各自影响外部结果，题目并非机械拆文件。参考修复取消旧deadline，每次恢复重新等待10ns；替代实现用周期调度，可整体重写而不受实现形状限制。
