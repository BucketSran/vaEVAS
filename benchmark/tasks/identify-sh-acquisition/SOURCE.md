# 来源与验收边界

工程动作是从数据建立模型，同源组是 `original-sh-identification`。
本题是依据采样保持前端工程指标原创的问题，没有使用器件实测或私有电路文件。
所有公开表征轨迹明确为 `behavioral_synthetic`，不声称来自 LF398 器件。

一手参考是 [TI LFx98x datasheet](https://www.ti.com/lit/ds/symlink/lf398-n.pdf)。
该资料给出 acquisition、hold step 和 droop 的电路意义及条件依赖。
本题不继承其数值、PVT、输入阻抗或电容负载特性。
它只要求固定系统、固定温度和负载条件下的电压可观察预测。

作者在 `experiments/benchmark_first_batch/identification/build_sh.py` 中定义原创系统，
解析分段状态方程独立产生目标样点。采集段趋向当前输入，保持段具有切换偏移和漂移，
再次采集承接先前状态。公开数据与隐藏刺激按完整实验划分。
终评分段样点、切换电压变化与保持漂移，单位和容差由题面定义。
checker 不运行参考 VA，不用候选报告产生预期值。

参考解 `solution/fit.py` 只读取公开 CSV 估计参数，`solve.sh` 生成 VA。
校准错版包括忽略漂移、忽略保持阶跃、保持阶跃的极性相关项反向和错误的采集时间常数。
这些是可编译的语义错误候选，须经实际后端验收才能认定拒绝。

当前身份是 Spectre 扩展集候选。纯 Python 行级测试只校准判据，
不是 VA 执行或实际 Spectre 通过证据。后端与 Agentic 校准状态由本批证据记录维护。

## 首次实际 Spectre 校准诊断

`identify-sh-reference-v3` 在 Spectre 21.1.0.509.isr12 中四个实验均执行成功，
四个实验的评分均失败。原网表的 vin 与 track 在恢复采集时同时从声明时刻开始
用 1 ns 斜坡变化，而解析目标在该时刻瞬时切换。这让恢复采集的初段误差
达到 102.9–275.6 uV；延迟造成的状态误差不会因避开控制边沿 5 ns 而消失。
按实际有限斜坡独立解析积分，与归档 PSF 比较的再采集最大残差只有 4.39 uV，
支持实验刺激和目标不一致的诊断。

修正网表让 1 ps 控制边沿以声明时刻为中心，并在保持期提前 10 ns 建立输入，
从而逼近题目声明的理想切换。公开刺激、数据输入列与题面一起更新。
80 uV/100 uV 电压容差、目标输出样点与公开拟合所得参考参数保持原值。
checker 只额外允许 trace 终点和请求时刻相差一个浮点 ULP，
实际缺失区间仍被拒绝。

原始归档诊断可通过
`experiments/benchmark_first_batch/identification/diagnose_sh_archive.py` 重放；
精简诊断见该目录的 `sh-v3-diagnosis.json`。该证据证明原版本失败原因，
不证明修正刺激版本已通过后端；修正后仍需协调者重跑实际 Spectre。
