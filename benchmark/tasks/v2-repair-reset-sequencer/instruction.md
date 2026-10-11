# 修复v2-repair-reset-sequencer

仅在clk上升沿更新。rst高或supply_ok/bias_ok不高时stage=0；否则stage递增并在final_stage饱和。stage1在stage>=1为0.9V，stage2在stage>=2为0.9V，ready在stage>=final_stage为0.9V，progress=0.9*stage/final_stage。其余输出0。初态stage=0。停钟期间rst变化不更新状态。final_stage只允许整数3..5。

final_stage将覆盖整数3..5；其他参数固定为源码默认值。最终测试使用不同资格、复位轨迹。

clk阈值交点前后0.2ns内，rst和资格输入保持稳定；输入阈值跳变恰与clk重合不纳入评分。若有效复位与阶段推进在同一采样拍发生，清零优先，不输出ready。

输入源码位于 `/work/`。可整体重写指定模块；保持公开端口和行为。验收激励与checker固定。逻辑阈值0.45V，禁止条件也须满足按时启动要求。提交指定文件，不依靠运行外部程序或隐藏终评材料。Spectre是本题固定后端；公开自测执行 `/tests/test.sh`，可自行建立诊断激励。
