# 非线性滤波直接通路对照

原 C4 模型 `laplace_nd(u², '{1,1}, '{2,1})` 在基线 `72cc9362` 被拒绝。
本候选保留原 VA 模型，在现有隐式求解路径中支持外部源的多项式直接项。
实际 Spectre 对照覆盖三模型、六配置，EVAS 六请求通过，Spectre 五配置通过。
按预定顺序选取首个达标设置后，三模型都具备合格参考和同刻配对。

## 固定判据

[检查器](../../../evas/validation/filter_direct/compare.py)固定模型、刺激、两档设置和 **1 µV**
外部电压误差上限。它用 60 位 Decimal 计算独立卷积闭式，分别检查两个后端，
再比较相同时刻的电压。所有原生点、精确初末点和 PWL 转折点都保留。
另有 3 个通过控制和 16 个错误控制，覆盖错误输出、错误输入、缺失点、非有限值和时间顺序。

对 `H=(1+s)/(2+d1*s)`，令 `a=2/d1`，`D=1/d1`，`C=1/d1-D*a`。
每段输入 `u=u0+m*t` 满足 `x'=u²-a*x`、`y=D*u²+C*x`，初始 `x=u0²/a`。
卷积的特解为 `u²/a-2*m*u/a²+2*m²/a³`，加上匹配上段终值的指数项。
这给出独立答案，不从任何后端波形生成。

原始模型为 `d1=1`，新增 `d1=3` 检查非整数系数。
反向输入经过 `[0,1]、[0.5,2]、[1,-1]、[2,1]`，检查非零 DC 和历史延续。
所有模型 stop=2 s。有限观察通过不等于全时域证明，也不增加原 31 条件或新精度表分母。

## 实际结果

| 模型 | Spectre 基础档最大误差 | 收紧档最大误差 | EVAS 两档最大误差 | 选中参考 |
| --- | ---: | ---: | ---: | --- |
| 原 C4 斜坡 | 0.0274 µV | 0.0149 µV | 0.786 fV | 基础档 |
| 非零初态与反向输入 | 5.96 µV，失败 | 0.305 µV | 0.896 fV | 收紧档 |
| 非整数系数 | 0.0168 µV | 0.00845 µV | 0.397 fV | 基础档 |

共 14,014 个共同原生时刻。所有 EVAS 请求通过；跨后端配置为 5 通过、1 失败。
最大已达标同刻差为 0.305 µV。失败档位不从分母删除。

Spectre 版本为 21.1.0.509.isr12，使用 conservative、traponly、无 strobe。
基础档请求 reltol=1e-7、vabstol=1e-9、maxstep=0.01 s；收紧档为 1e-9、1e-11、0.001 s。
日志与 PSF 的实际 reltol 分别为 1e-8、1e-10，其他所查控制一致。
请求与生效设置的差异保留为元数据 I，不能声称请求参数全部原样生效。
波形验收按实际输出独立判断。

EVAS 固定 vabstol=1e-9、reltol=0、max_step=0.125 s，在各 Spectre 原生网格上查询。
上述误差是这批模型的实测值，不是 EVAS 的普遍精度保证。

## 复核与范围

[收据](receipt.json)绑定源码清单、内核、检查器、各输入和输出哈希、实际设置及失败。
构建对应包含本收据的提交，基线为 `72cc9362`。模型和检查器公开保留，原始 PSF、日志、
EVAS 响应及核验归档在本地 `runs/evas-backlog-20261011/c4-collected/` 与 `c4-analysis/`。
远端原始目录也保留。这些 raw 尚未公开下载，哈希不等于公开可获取。

在仓库根目录可以重新冻结输入和校准检查器：

```sh
python3 -B evas/validation/filter_direct/compare.py calibrate
python3 -B evas/validation/filter_direct/compare.py freeze --output runs/c4-new-inputs
```

有已配置且获授权的 Spectre profile 时，使用维护中的执行器；目录须为新目录：

```sh
python3 -B experiments/backends/sample-edge-filter/callback_probe.py run runs/c4-new-inputs runs/c4-new-raw --profile /path/to/profile.json
python3 -B evas/validation/filter_direct/compare.py analyze --inputs runs/c4-new-inputs --raw runs/c4-new-raw --output runs/c4-new-analysis --kernel evas/rust_core/target/debug/evas-kernel
```

本轮远端串行，主进程单次 90 秒、许可证等待 30 秒、4 GiB 内存和单文件 32 MiB 上限。
运行身份和清理回执均在收据中。没有测量性能。
本实现仍拒绝非线性直接输入中的内部节点、算子、事件状态与事件组合，
没有完成 #66 的动态参数、深层历史反馈或一般非线性反馈。
