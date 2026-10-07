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
版本/计时/accepted、独立波形与process耗时和机器负载。正式verify禁止公共--case选择器。policy必须声明完整case inventory（名字、canonical
case hash、performance角色），全Harbor包须全部case且唯一performance过。受信准备器
生成的单条件private packet可分别校准，但报告verification_scope=condition_packet、
full_task_success=null；该包的一分只是本条件成功，不能当整题完成。source guard还在每次pair启动前再检查，避免helper未接评分路径。
原型的25项本地测试中6项验证顺序/角色/失败/guard，使用合成时间，完全不是测速。

VCO实际单次低频baseline PSF45,571,517B、reference910,872B。所有paired PSF在
完整解析/功能判读及solver计时结束后按gzip level6无损压缩；逐字节解压SHA和长度
相同后才删除原文件，保留raw/gzip长度、哈希、相对路径、版本和压缩时间。源文件、
原生日志及merged流不压缩，主功能PSF保持原格式，不删点、不截断失败。

已实际核查harness收集硬上限256MiB，1GiB profile不可用。执行采用256MiB、900s，
每次子Spectre90s；完整输出按lossless保存，而不是扩大harness上限。四份历史原PSF
本地无损往返验证见lossless_psf_calibration.json，不是新仿真或新solver性能测量。
VCO baseline45.57MB→7.21MB、reference0.91MB→0.154MB；UART baseline43.70MB→
1.194MB、reference0.663MB→0.0297MB。正式远端归档仍需逐条解压复核及总容量检查。
