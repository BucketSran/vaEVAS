# 保持目标中的嵌套条件

`transition(q-2*(q<2?0:1),0,0.25,0.25)` 保留原算式，在固定 timer 的 q=0、1、2、3 下产生目标0、1、0、1。
这个小包验证纯保持量分支嵌在算术内部的准入，不包含历史电压谓词、IR23 或原 MUX 整体恢复。
原 MUX 的 checker 状态为 NOT_RUN，不能从这里推为整题通过。

准入完整展开所有候选后逐个验证仿射形式，沿用8192候选上限。未选分支中的非线性状态乘积和零系数电压反馈仍拒绝。
[公共 API 开发测试](../../../../evas/tests/test_held_transition_targets.py)验证原算式、额外查询不变与隐藏反馈拒绝；Rust 自包含测试覆盖资源上限和候选失败重试。
数值准则是所有保存原生点及16个指定时刻均满足独立分段线性答案，误差不超过100 nV；两后端共有精确时刻再直接配对，不插值。

[`inputs/`](../../../../evas/validation/held_transition_targets/inputs/) 保留原同源 VA 与 SCS。原 SCS 的 `method=traponly` 在 EVAS 明确拒绝，脚本没有删除选项后冒称逐字同一请求。
[`pair.py`](../../../../evas/validation/held_transition_targets/pair.py) 用原 VA 的公共 API 运行 EVAS，并分别记录实际后端设置。参考 raw 为 local-only，不能仅凭摘要哈希公开重现 Spectre。
旧参考 v1 有两个设置被 Spectre 忽略，且精确强制点缺3和3.25；这些失败记录保留，rc=0不等于完整通过。[校准 v3 摘要](summary-v3-owned-path.json)通过此有限检查：两条参考都完整观察16个精确时刻，正卡的 EVAS/Spectre 共有点直接配对均在100 nV内；负卡的 EVAS 仍结构拒绝。
[v1/v2/v3 历史](profile-history.json)保留逐配置结果。v2把容差移到有效 options 并指定 strobeonly，仍只有14/16精确时刻；v3仅把 maxstep 从0.01换为二进制可精确表示的0.0078125，原16时刻和模型不变，才完整保存。
Spectre v3的实际值为 reltol=1e-11、vabstol=1e-12、traponly、conservative；EVAS公共API为absolute=1e-12、relative=1e-10、max_step=0.01。各后端设置单列，均独立满足100 nV，不宣称相同容差名等于相同方法或精度。
PSF十进制打印单元也计入保守误差：值打印半格加4倍时间打印半格，利用此波形全局斜率绝对值至多4；[checker校准](../../../../evas/validation/held_transition_targets/test_pair.py)保留越界、非有限和缺精确时刻控制。
原 MUX 在此 main 基线实际首先被动态数组写下标范围拒绝，后续历史谓词也不在本包范围；本次没有绕过它们。

给出本地 PSF 后可复算，不覆盖已有输出目录：

```sh
python3 -B evas/validation/held_transition_targets/pair.py \
  --kernel evas/rust_core/target/debug/evas-kernel \
  --reference-dir /path/to/local/reference-raw --output-dir /path/to/new-output
```

模型与 checker 已归入 `evas/validation/held_transition_targets/`。原路径的[执行摘要](summary-v3.json)仍保留；新路径只重跑同一有限检查，未改变模型、门槛或旧成绩。
