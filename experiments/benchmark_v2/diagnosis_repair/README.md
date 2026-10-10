# 诊断与修复：五个完整工程合同

当前作者校准为33/33个登记变体有效，见[作者校准最终报告](../author-calibration-final.md)。模型 Agentic 与适用 one-shot 试做及完整 spec 验收尚未完成。计划和生成清单中的 pending 保留生成时状态，当前作者结论以该报告为准。

本目录建设 spec #136 的四个P1归口来源005、046、272、249以及case-0009多VA系统。任务、原starter、健康资产、参考修复、整体改写和合理语义错误版本已建立。任务构建、独立checker波形合同检查与实际Spectre作者校准已完成；Harbor oracle和两种模型试做尚未完成，不能据此关闭spec或判断难度。

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

## r2审查修正

PFD的隐藏重入刺激新增5.11ns的REF上升，位于复位释放之后、旧5.1295ns截止之前；新周期UP必须保持，保留旧计时的错版会提前清零。新增`stale-reset-timer`作者VA负例和手算波形回归。272公开final_stage范围及同步清零优先，输入阈值变化与clk采样保持0.2ns间隔；补充复位发生在最后资格拍的手算回归。

以下保留开发时的首轮状态，当前完整作者证据见最终报告。实际首轮参考校准由协调者执行：四个单模块参考两case通过，多VA因作者VA前导小数点语法导致Spectre VACOMP-1795而未评分。r2统一作者VA显式0.x，需重跑多VA所有候选和272替代实现；249新刺激需重新校准所有本题候选。旧结果保留其版本，不转作r2证据。模型试做与Harbor验收仍未完成。
