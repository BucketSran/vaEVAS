# VA07 原八例 EVAS 保存候选重评

`triangle_evas_replay.py` 是 benchmark 自有的完整八例适配器。它消费冻结候选并产生 Harness final report，保留原 `triangle_evas.py` 单例开发 API。它不重建内核，也不调用模型、SSH 或 Spectre。

## 合同与限制

输入固定为原 [cases.json](../tasks/va07-triangle-repair/tests/cases.json) 字节，SHA256 为 `df84f3123a91a8ef6e70818d5437db8e101c871aba8d5da85c7e8302653417e1`。原八例、参数、PWL、stop、maxstep、ttol/vtol 和行为误差阈值保留。每例分别执行原基础网格与由解析根±time_atol/2预定的补充网格。时间证据来自 sampled count 的前后区间，不使用内核自报事件。

两轮都用 canonical `evaluate`，保留原判定及指标。完整样本上的波形或计数错误是 graded fail。通过还要求整个换向区间都在原 time_atol 内，共同网格波形差不超过原 wave_atol。无法建立上下界是 inconclusive，不记零分。采样不足、执行错误、源码/内核漂移同样没有分数。所有路径保留八条条件记录；只有全部可评时，reward 才是原 `int(all(passed))`，不是通过数/8。

求解映射沿用已有 oscillator compatibility 实验，固定 `vabstol=1e-8`、`reltol=0`。原 tight/tighter 两档都映射到这组 EVAS 设置，但仍保留八例。`iabstol` 和 `traponly` 在 EVAS 没有对应选项，映射逐例明确保存，不宣称等价执行。`CHIPS_SOLVER_OPTIONS` 必须恰好等于上述固定对象，未知或未映射选项拒绝评分。原条件本身的 PWL 瞬态可以表达，不因此将整个分析标成不支持。

这是保守的独立采样判分接口。合法的近边界候选也可能因采样无法区分而未决；它不保证任意候选可重评，不证明连续时间资格。原 wrong-speed 在 stop=3s 的已知 EVAS 端点拒绝仍是引擎缺口，不能更改原 stop 来计入验收。本适配不修改 EVAS 算法或原 canonical oracle。

## 冻结包

从 vaEVAS 仓库根目录运行：

```sh
python3 -B benchmark/checkers/build_triangle_evas_replay.py \
  --output runs/NEW-replay-package
```

输出目录必须不存在。builder 复制 oracle、adapter、原 cases，保存全部预定请求与映射，并给每个文件生成实际摘要。协调后的 canonical 报告修复可以用 `--oracle /actual/checkout/benchmark/checkers/triangle_oscillator.py` 明确选择；builder 和实际 wrapper 只接受两份完整 canonical 文件摘要：原 `cc386977` 的 `46a5342f…` 与 [PR #87 报告修复](https://github.com/BucketSran/vaEVAS/pull/87) `862d3fbb` 的 `9e38eb5a…`。完整文件校验拒绝末尾覆盖、依赖或判据变化；未来报告变化也须明确校准并更新 allowlist。由操作者显式指定 oracle，不暗中改变源码依赖。

开发身份沿用已保存终评的 `task_version=dev-df643eaf9fd82a56`、`criteria_sha256=df643eaf9fd82a569e276640d3a673fa0a632c50b7b56dcf009a83ab3ab77f10`、`condition_id=va07-original-eight-cases-df84f3123a91`、`task_set=extension`。这保持原行为判据和条件；后端脚本和映射变化由新的真实包摘要记录。它不是 benchmark 正式发布。包不包含候选，不能把单例开发报告作为原八例成绩。

## 离线固定镜像

[Dockerfile](va07-evas-runtime.Dockerfile) 只复制已保存产物，没有 pip、Cargo 或在线安装。私有 build context 的 `runtime/` 应包含对应源码的 `evas/` Python 包、已有 Linux `evas-kernel`，以及实际来源/构建记录 `source-identity.json`。源记录至少保存源码 revision、Python 逐文件摘要、内核摘要、架构和原构建收据位置。使用获准且身份对应的既有内核，不能把本机 macOS 二进制放入 Linux 镜像。context 排除 `__pycache__` 与 `.pyc`；recipe 还会离线清除继承的 Python bytecode，因为 `-B` 只阻止写入缓存，并不禁止读取旧缓存。

```sh
# BASE_REFERENCE 是已安装 Python 3.10+ Linux 镜像的本地引用。
BASE_IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$BASE_REFERENCE")
docker build --network=none --pull=false \
  --build-arg PYTHON_BASE="$BASE_REFERENCE" \
  -f benchmark/checkers/va07-evas-runtime.Dockerfile \
  -t va07-evas-replay-local /private/recorded-build-context
test "$BASE_IMAGE_ID" = "$(docker image inspect --format '{{.Id}}' "$BASE_REFERENCE")"
```

Dockerfile 路径与 build context 要由操作者按实际文件布局指定。若离线导入镜像只有本地 tag、没有真实 RepoDigest，使用已安装 tag 并在构建前后核对实际 image ID；不能从 image ID 伪造 repo digest。某些 builder 仍尝试解析 registry，先验证所选本地引用可离线解析。保存本次 image ID、base image ID、可用的真实 RepoDigest、Python/内核来源记录。Harness replay 配置使用生成的不可变 image ID，不使用这里的构建 tag。wrapper 拒绝 EVAS 包内任意 `.pyc/.pyo`，为每个子进程指定新的空 Python cache prefix，并让子进程从与身份摘要相同的包根导入，避免 cwd 或旧缓存改选代码。它记录实际执行的 Python、EVAS Python 文件和 kernel 摘要，并在每轮前后拒绝漂移。CLI/runtime 转发固定请求，但内核不独立回显全部生效容差；不能据此宣称两种求解器的误差保证等价。

Harness 的 replay 配置为 schema_version=1，solver_options为上述固定对象，unsupported=[]，timeout_s建议300，max_output_bytes最多16777216，task_package_sha256使用 `package_identity` 的实际返回值。unsupported 列表代表不支持整个分析，不能把逐设置未映射表机械搬入，否则 Harness 不会启动 checker。固定输入/输出挂载和无网络隔离由 Harness 保持。

entrypoint 使用 `CANDIDATE`、`VERIFY_OUTPUT`、`CHIPS_SOLVER_OPTIONS`。每轮最多15s，两网格八例共16个计划执行；外层总预算覆盖它们。波形及stderr分别受16MiB文件上限约束。顶层候选摘要是原 dut.va 字节摘要，Harness 最终比较身份另含冻结 bundle 摘要。

## 验证与交接

```sh
python3 -B -m unittest discover -s benchmark/checkers \
  -p test_triangle_evas_replay.py -v
```

这些测试使用构造 CLI 输出，覆盖完整八例 pass、混合判错、后端失败、未决、超时、来源漂移、坏输出和固定包。另用真实 Python 子进程验证陈旧缓存、cwd 包遮蔽和 oracle 末尾覆盖均被阻断。它们证明协议与独立判分处理，不证明真实 EVAS 或 Spectre 一致。

真实接受条件由协调者完成：对相同冻结参考、校准错误候选和已保存模型候选重评原八例，核对同身份 Spectre archive，保留 match/false_accept/false_reject/unevaluable 分类。已知拒绝继续保留未决，不从参考解的有限通过推断任意提交支持。

2026-10-06 的协调验收已用旧适配器 `b6afdfdf` 完成原三候选八例对照，EVAS 源码为先前冻结的 `d06581f9`、Linux kernel SHA256 前缀 `d8fca02f`。reference 和保存 GLM 候选均 8/8，通过并与保存 Spectre 成绩一致。wrong-speed 的 constant 两档发生原端点拒绝，其余六例可评且失败；全题为空分/unevaluable，八例均保留。该已知问题由 vaEVAS #70 与未获准合入的 PR #79 跟踪，本适配不接入该候选内核。此记录只描述旧固定运行身份，不代表当前 main 的全行为。身份修复后的 adapter 仍须由协调者保留新记录复验，不覆写这批旧结果。
