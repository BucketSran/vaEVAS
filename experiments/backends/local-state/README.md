# 局部 analog 量与事件状态的实际配对

一个实际 Spectre 配置运行同一冻结 VA 中的三个实例。
候选 EVAS `f0ed848d8c0a6ceb7e55407013788b1b95103cba` 与原生 67 行、
737 个电压值的同阶段数值比较通过，三个 q 观察量始终共享同一阶段，未见阶段差。
这是有限数值观测，不代表 #65 或原 VCO 全部完成。
[精简证据](evidence.json)保留设置重读、原 RESULT、身份、所有失败和资格缺口。

判据来自[冻结合同](../../../evas/validation/LOCAL_STATE_CONTRACT.md)及
[手写 manifest](../../../evas/validation/cases/local_state/manifest.json)。
电压预算固定为 `1e-7 + 1e-5*|独立期望|`。
普通贡献结果是 `y=g*u+q`、`z=3*g*u+q`；两个独立积分调用点使
`h=3*t+0.25+q`。第一个 q 从 1 到 2，第二个从 3 到 4，输入采样实例从 1 到 1.5。
两后端分别用这些公式检查，Spectre 输出不是 EVAS 的 oracle。
检查器保留 raw 十进制 token，用 Fraction 求期望，不跨跳变插值，也不外推要求点。

Spectre 原生公式最大绝对差 `1.09e-15 V`，最大预算比 `2.33e-11` 以下；
与 EVAS 的最大配对预算比 `3.63e-11` 以下。
所有 q 同时在 token `0.5` 的记录进入后态；前记录为 `0.499237060546875`。
该原生括定与冻结 `[0.5,0.500000000001]` 相交，不是严格 callback 时刻证书。
候选 canonical 请求的 9 点独立答案全部通过。
3/9/71 点查询的共同电压逐 bit 相等，事件记录相同；accepted steps 为 40/41/70，
discarded trials 均为 0。观测网格会改变步数，此检查不声称内部网格或所有历史逐 bit 相同。

严格观察资格仍为 I。9 个要求点只有 0、0.125、0.5、0.625 的原生时间 token 精确相等。
其余要求点的相邻记录、十进制偏移和阶段均保留；没有用浮点近似覆盖来改判精确命中。
初态 token 0 与三个初值通过，末记录 token 为 `1.0000000000000002`，
比 deck stop 1 大一个 binary64 ULP。原请求没有精确 stop token。
canonical EVAS 仍使用 stop=1；单独 supplemental 请求将 stop 延长到该 raw 末时刻，
输入在额外区间保持原终值，以实际查询全部 67 个原生时刻。
该最后一行仅作数值诊断，不赋予 canonical 请求精确终点资格。

实际 Spectre 为 `21.1.0.509.isr12`，模拟成功退出，限制为单线程、4 GiB 内存、
32 MiB 输出文件，命令、超时/清理及版本探针收据保留于 evidence。
deck global reltol=1e-5；conservative transient 的有效 reltol=1e-6，
vabstol=1e-7、iabstol=1e-12、maxstep=0.025 s、stop=1 s、traponly。
部署 deck 在冻结原 deck 上只加 `precision="%24.17g"`，两者 SHA 均记录。
收集器旧 readback 不识别 `25 ms`，原 RESULT 设置状态 I 原样保存。
新分析使用已合并 PR109 的 `settings_readback.py`，固定于 `5e795852`，
重新从原 log 与 PSF 读取并核对设置，没有改写原 RESULT 或伪造执行。

psfascii 执行命令、11 个 save 节点、strobeoutput=all、skipdc=no 及 qobs 记录支持
本案例的原生保存来源；67 行等于 66 accepted steps 加初始行。
这些记录不单独证明任意隐藏 callback 顺序、精确实数时间序列化或严格终点。
raw 归档 SHA 为 `e91d97bc7089cda266cea9996bd6e66f2e8e34b70cb89ac792747592b541e8fa`，
37 个清单文件均逐项验证。raw、完整请求/响应和执行环境为 local-only，
工作区相对入口为 `current/runs/issue-closure-20261008/local-state-reference-v1/collected/spectre`。
精简 evidence 位于仓库内，但这些 local-only 材料不是公开下载链接，不能声明完整公开复现。

## 校准与重分析

```sh
python3 -B -m unittest discover -s experiments/backends/local-state -v
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
git show 5e795852:experiments/backends/paper/settings_readback.py > runs/frontend-local-state/spectre-analysis/settings_readback-pr109.py
PYTHONPATH=evas/src python3 -B experiments/backends/local-state/analyze.py --collection /absolute/path/to/collected/spectre --readback runs/frontend-local-state/spectre-analysis/settings_readback-pr109.py --output runs/frontend-local-state/spectre-analysis/full --evidence experiments/backends/local-state/evidence.json
```

[维护检查器](check.py)的[校准](test_check.py)覆盖独立正例、错误增益/积分/采样值、
不一致 q 阶段、延迟/多次事件、同刻前后阶段差、缺初态/要求点/终点和末点 overshoot。
[分析入口](analyze.py)仅重新执行本地 EVAS，不启动远端；归档、DUT、清单、
原 deck 和 shared readback 均先绑定固定身份。
原始 VCO 的局部事件快照、方向驱动积分及自换向验收仍未完成。
