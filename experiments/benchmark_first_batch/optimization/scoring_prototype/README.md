# 未准入评分入口草案

这是连接guard与重复评分的原型，不是Harbor正式题，也没有已实施的性能计分证据。
performance.json 明确 admitted=false，所有性能门槛保持null。实际三条件功能、诊断及
五对稳定取证前不能填入门槛。此目录不具备任务完整材料，不提交远程执行。

正式任务tests可采用verify.py的入口，带同目录evaluate.py、circuit_task.py、
adc_linearity.py、first_batch_optimization.py、固定baseline.va和cases.json。入口先拒绝
未准入配置、坏trusted baseline及候选的active日志/控制系统任务，再调用公共runtime
验证全部功能。唯一performance case在首次功能通过后，在同job保存各侧warmup和
五对AB真实求解；一次只有一个子Spectre。每次保留完整源码、网表、native log、真实
merged stdout/stderr及PSF，不删除失败，不降低分母。baseline失败为infrastructure，
候选失败为0；未变更源码必须功能过但性能不过。

公共runtime负责初始各case记录；pair record另外绑定候选/基线角色、哈希、native
版本/计时/accepted、独立波形与process耗时和机器负载。正式verify不允许只选非性能
case形成计分子集。source guard还在每次pair启动前再检查，避免helper未接评分路径。
原型的25项本地测试中6项验证顺序/角色/失败/guard，使用合成时间，完全不是测速。

VCO实际单次低频baseline PSF45,571,517B、reference910,872B。五对净波形约232.4MB，
加两侧warmup约278.9MB，超过现有256MiB轮询上限。建议协调者另部署性能profile，
保存1GiB、900s；每次子Spectre仍90s。不要改已有harness或通过丢原始波形规避限额。
UART/SAR实际尺寸未知，收到actual后复核。外层全部功能及其它case输出也需计入容量。
