# 原始保存点的有限边沿检查

新增判据覆盖原始PSF每个输出保存点，不改变VA、负载、现有功能容差或已freeze的远端包。
`raw_point_waveform_replay.json` 是已有实际仿真的本地重新判分，不是新Spectre执行。
45个v2/v3条件回放44通过；唯一失败仍是旧power v2未修正的慢电源计时基线。
其失败保留。当前参考、其余当前基线以及修正后的power v3全部通过。

- Flash/DAC/SC：独立刺激决定固定采样时间及目标值，公开delay/rise决定线性变化，
  逐点核验全部边沿和保持区域；原有25/50/75%探针继续保留。
- Power/SAR/UART：先从公开PWL或独立事件日历计算事件目标、方向、次数和截止时间；
  输出唯一中点必须满足原有公开时间容差。中点只提供该合同允许的事件时间位移，
  不用于拟合宽度、幅度或保持值。由独立old/new值及固定公开rise重建整个轨迹，
  逐点覆盖原来允许轮询量化的边沿附近区域。原有时间/平台/四分点检查继续保留。

纯fixture增加了不跨50%阈值、落在旧四分探针之间的窄保存点毛刺，证明加强后拒绝。
这些fixture不算VA执行证据。正式生成只接受当前evaluate.py及cases.json哈希匹配的
实际波形回放；旧弱checker成功receipt不再可直接证明新题功能校准。
新formal完整包仍需主任务重新执行实际reference与负例校准。

复现（bulk波形临时保留在ignored runs）：

```sh
python3 -B experiments/benchmark_first_batch/optimization/replay_archives.py \
  --calibration-root /path/to/calibration \
  --function-root /path/to/optimization-function-v3 \
  --output /path/to/raw_point_waveform_replay.json \
  --scratch runs/raw-point-waveform-replay
```
