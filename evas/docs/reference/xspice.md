# 将 VA 模型编译成 ngspice XSPICE 模型

`evas-rebuild xspice` 把限定的电压模型编译成 XSPICE 源文件，再用匹配的 ngspice SDK 构建动态库。网表、器件、负载、Newton 迭代和时间步由 ngspice 求解；事件状态与输出过渡由生成模型实现。编译不调用 EVAS Rust 内核。当前本地后端版本为2，固定依赖 EVAS `c8dc2a7b`、IR28；尚未提交或发布。

## 运行采样保持与反馈网表

需要 Python 3.10+，已安装 EVAS，及与目标 ngspice47 匹配的 C 编译工具链。示例源和网表在 [examples/xspice](../../examples/xspice/)。以下从该目录运行；源码开发时先设置 `PYTHONPATH` 指向仓库的 `evas/src`。

1. 按下一节配置本机 `sdk.json`。
2. 编译模型。源文件中的参数在此时固定。

   ```sh
   evas-rebuild xspice compile sample_hold.va -o generated \
     --model-name sample_hold_cm --parameter timer_start=1.08e-6
   ```

3. 构建动态库并执行隔离的 DC/瞬态加载探针。

   ```sh
   evas-rebuild xspice build generated --sdk sdk.json
   ```

4. 在生成的原生目录运行网表，让 ngspice 在解析网表前加载动态库。

   ```sh
   cd generated/native
   ngspice -b ../../feedback.cir
   ```

成功后生成 `wave.raw`。`V(out)` 是有限边沿的输出，`V(held)` 是瞬时保持值；计数、timer 次数、事件顺序和时刻也保存在示例中。该网表把 `out+0.2 V` 经 1 kΩ/1 nF 接回输入，后续采样依赖电路实际解。

编译和构建目录必须不存在；命令不覆盖已有产物。CLI 成功时输出 JSON，输入、准入或工具错误时返回2并在 stderr 输出诊断。编译不需要 Rust 或 ngspice 进程；构建需要显式 SDK。用 `python -m evas xspice` 或 `python -m evas.xspice` 可以执行相同操作。

## 提供匹配的 SDK

复制并填写 [sdk.example.json](../../examples/xspice/sdk.example.json)：

```json
{
  "sdk_version": 1,
  "source_tree": "/absolute/path/to/configured/ngspice-47",
  "ngspice": "/absolute/path/to/matching/ngspice",
  "cc": "cc",
  "defines": []
}
```

`source_tree` 必须包含已配置的 `src/include/ngspice/config.h`、其余头文件、可执行的 `src/xspice/cmpp/cmpp` 和 `src/xspice/icm/dlmain.c`。工具链不得混用其他版本；当前入口只接受47。SDK 不随 EVAS 分发，入口不会下载或安装工具。

`defines` 补充目标二进制实际使用的 ABI 宏。若库与头文件来自同一次匹配构建，按该构建配置填写。已测 macOS Homebrew ngspice47 使用 `CIDER` 和 `WITH_PSS`；配合本轮配置的 SDK 需要 `"defines": ["CIDER", "WITH_PSS"]`。这不是其他安装的通用默认值。C 宏配置错误可能导致加载进程崩溃，因此构建先在有超时的子进程中执行探针，成功才发布最终库名。

当前原生执行证据是 macOS arm64 / ngspice47。Linux 构建命令已实现，尚须匹配 SDK 的平台实测；不声明 Windows 或其他 ngspice 版本已通过。

## 在自己的网表使用产物

编译产物包含 `ifspec.ifs`、`cfunc.mod`、`ir.json`、原始输入映射、参数及端口元数据、文件哈希清单和网表片段。`instance.cir` 按 VA 声明顺序给出位置连接示例。可以在网表中改接这些节点；不支持的 VA 写法会在生成前拒绝。

原生目录包含动态库、`model.inc`、`.spiceinit` 和 `build.json`。从该目录启动 ngspice，网表用 `.include model.inc` 声明模型。`.spiceinit` 使用相对库名，因此整个目录可以移动，也支持父路径含空格。不要把 `codemodel` 放在普通网表的 `.control` 中再期待它参与前面的模型解析。

可将库复制或链接到已有仿真工作目录，并在该目录的启动文件中加载相对文件名。原生构建不修改用户已有的 `.spiceinit`。实际网表执行、任务排队与结果收集仍由调用方或电路 harness 管理。

默认模型类型由模块名、IR、源码、生成器及配置身份派生，不同特化可共存。显式 `--model-name` 便于固定网表连接；此时调用方须避免在同一进程加载不同内容的同名类型。模型可实例化多次，每个实例独立保存状态和历史。

VA 参数只在 `compile --parameter NAME=VALUE` 时绑定。在网表中重复同值允许浮点解析末位舍入，实质改变参数会明确拒绝；要改变参数应重新编译。编译期元数据和构建收据分别记录源码/IR/模板以及 SDK/二进制/命令/探针身份。构建前核对产物清单，源文件被改动后不能直接构建。

## 连接带参考端的输出

对于 `V(clk0,vss) <+ level`，生成器把输出声明为 XSPICE 差分电压端口 `vd`。例如四相时钟的生成片段为：

```spice
a_dut vss %vd(clk0 vss) %vd(clk90 vss) %vd(clk180 vss) %vd(clk270 vss) clock_cm
```

VA 的端口声明顺序仍保存在 `ports`，展开后的连接保存在 `instance_connections`。每个差分端口的第二个节点须连接原 VA 参考端。这样 ngspice 同时满足 `V(clk0)-V(vss)=level` 和输出电流的回流关系。当前仅允许 ground 或一个输入端口作为参考；输出之间的隐式电压网络仍会拒绝。原 grounded 示例继续使用单节点 `v` 端口。

这沿用 [ngspice 的差分端口定义](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf)，没有把参考电压加到一个对地源上替代差分支路。带有限参考电阻及不同负载的本地检查见[验收合同](../../validation/xspice/README.md#r53-bounded-pilot)。

## 已实现的子集

- 零个或一个 rising `cross`，输入电压的仿射守卫，正有限时间及表达式容差。
- 前置的输入仿射局部量可用于守卫和事件采样；有限条件采样别名已验收true叶。动态供电阈值、差分采样及两实例共同平移有专项同源证据；输出或历史依赖、重赋值等不据此扩为一般过程支持。
- 启用的固定周期 `timer`，日程和容差为实例常数。纯时钟允许非负起点、正周期，最多64个调用点；已实测默认32路及42路参数变体，未宣称64路满载通过。带cross的路径仍要求timer正起点且事件合计最多八个。
- 标量状态的顺序赋值、有限条件与选择表达式、常数初值。整数赋值须保持有符号32位整数，越界或非整数值会拒绝。
- `transition(held,delay,rise[,fall])` 的事件保持输入，固定非负 delay 与正 rise/fall；每调用点最多64个待生效目标。纯延迟保留短脉冲，中断边沿从当前值连续前进。
- 无事件的连续 `tanh` 表达式。每个输入的链式导数交给 ngspice 的 Newton 求解；`tanh(x)` 的导数为 `1-tanh(x)^2`。
- DC 初始化和瞬态；网表内负载和反馈由 ngspice 联立求解。输出是理想电压源，实际输出阻抗或限流须由外围网络明确表达。

纯时钟允许独立事件同批执行，所有状态与transition更新在整批完成后发布。准入检查固定周期日程的潜在窗口重叠、写写及跨块写读依赖；异刻置高、置低可以写同一状态，可能同批冲突则拒绝。有限独立浮点近邻可共用宿主点，但各自身份、非提前窗口和输出误差须分别达标。它不建立一般共享状态闭包或事件OR语义。

动态或单次 timer、下降 cross、一般事件 OR、连续电压 transition 输入、一般电流或电荷贡献、内部隐式网络、跳过DC初始化的 `.tran uic`、AC 和显示任务没有由此入口建立支持。除 `tanh` 外的数学算子及未实现的 IR 表达式明确拒绝。前端接受范围不等于该后端接受范围，也不沿用 Rust 内核的区间误差认证结论。

## 状态、边沿与拒步

每次 Newton 调用与时间回退都从 ngspice 的上一已接受帧复制候选。VA 状态、cross 负号侧 arming、timer 游标、延迟目标队列与活动边沿一起交由 host 接受或回退。普通执行不从静态诊断对象恢复物理状态。

纯时钟的DC候选每次从常量初始化重建，只执行起点精确为0的独立timer，然后用最终状态建立transition种子。零周期游标随首个接受帧交给瞬态，不能再次消费。正起点即使只有1fs也不归入零批次；正延迟才产生启动边沿。没有静态物理started标志。

`cross` 同时检查时间和表达式容差，不能满足时请求回退；host 分辨率不足则明确拒绝。固定 timer 预先请求日程断点，在指定时刻或稍后触发，超过原容差仍回退。数学依据和有限验证边界见[事件手册](../math/events.md#xspice-的有限事件出口)。

`transition` 使用线性完整边沿时间 D，10% 到90% 是 `0.8D`。中断时保留旧起点 o、旧目标 p 和当前值 yc；同向保留 o，反向用 p，斜率为 `(新目标-所选起点)/D`，从 yc 连续变化。输入相同不重启边沿。数学来源沿用 [LRM 2.4 §4.5.8](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf) 和 [历史算子说明](../math/operators.md#transition)。本适配器使用标量历史，未移植 Rust 区间证明器。

## 诊断与开发验收

默认不生成逐步追踪。需要调试单个实例时，可在该实例所用的 `.model` 上设 `evas_trace="trace-a.csv"`；多个实例应分别使用模型声明和不同路径。已有追踪文件会拒绝打开，避免混合记录。`evas_` 参数前缀保留给后端。

追踪还包含 `inputN`、`outputN` 和 `partialN_M`，依次对应元数据的输入、输出顺序。差分输出记录的是支路电压。验证工具在评分后无损压缩大追踪，并保存原始字节的 SHA256；分析器同时接受 CSV 和压缩副本。

`--test-hooks` 仅供回归，允许 `evas_inject=true`、`evas_inject_time=...`、强制DC重试的`evas_inject_dc=true`和故意错误的 `evas_bad_state=true`。没有显式编译开关时，这些故障请求会拒绝；注入还要求独立 trace 路径。`evas_trace_dc=true`追加DC候选，默认追踪仍仅含瞬态；timer另记录各自名义期限和宿主请求点。

固定的 [XSPICE 验收入口](../../validation/xspice/README.md)保留实际 Spectre 参考输入校验、独立 RC/折线答案、全部已接受波形评分、三类同进程拒步及三个泄漏负控。负控的最终波形可能仍达标，因此还检查状态和已接受历史继承。执行来源、两档设置差异、校准与本轮限制见[实验入口](../../../experiments/backends/xspice-entry/README.md)。

新增 r53 检查使用[六份具名样本](../../examples/xspice/r53/sources.json)，覆盖单路及四路采样、整数回绕、带参考端四相时钟、时钟采样链路，以及连续 tanh 与导数。它们是 benchmark 整理样本。115与068修复后，固定七例同源 Spectre 对照7/7通过；原配对超差、收敛失败及各次重试仍保留。这是上述有限电路的结果，不扩大为完整兼容。

[P0专项](../../validation/xspice/README.md#p0-input-aliases)复用已有别名能力，固定六例ngspice/Spectre同源验收6/6通过，含动态阈值、事件保持、RC全轨迹及原近零边界。微例沿用0.1ps/0.1mV/边沿5mV独立预算，近零保留原50ps/20µV；各自分母不并入r53七例。两份别名VA保持前次探针身份，失败校准及重分析均保留，未提交发布。

[P1专项](../../validation/xspice/README.md#p1-parameterized-clock)使用已确认的[1800ns标准整理版](../../examples/xspice/clock1800/README.md)，固定15例ngspice/Spectre同源对照15/15通过。零起点最终初态、32/42路、跨周期六输出、独立同刻及近邻、两实例、1000周期和stop边界分别验收。原件原样、11通道采样器、一般共享状态及动态timer仍未取得资格。

Python API：

```python
from evas.xspice import compile_model, build_model

compile_model({"sample_hold.va": va_text}, "generated", parameters={"rise": 2e-7})
receipt = build_model("generated", sdk_config)
```

包含自定义头文件时，把所有源文本作为同一个路径到文本映射提供；CLI 将头文件作为额外 source 参数传入。沿用 EVAS 的显式 include 图，不自动扫描文件系统。
