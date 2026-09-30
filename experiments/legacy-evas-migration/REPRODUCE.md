# 核对材料与重新运行

本目录整理的是 `legacy-evas-migration-20260929` 的已有运行。源码为旧 EVAS
[`v0.8.7` / `6cb6fa7`](https://github.com/Arcadia-1/EVAS/tree/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b)，
不是本仓库的新 `evas/`。发布时未重跑仿真；三份 `probes/` 运行器与原执行文件逐字节相同。
完整身份、原资产哈希和整理操作见 [provenance.json](evidence/provenance.json)。

## 只核对已发布证据

在本仓库根目录运行，无需 numpy、Rust 或仿真器：

```sh
python3 -B experiments/legacy-evas-migration/verify_evidence.py
```

这会核对发布资产哈希、35 + 8 + 4 个唯一 ID、16 次完整 Rust 模型请求的
12 次返回/4 次拒绝，以及 11 组解析误差。返回成功仅说明整理材料内部一致，
**不表示 47 次仿真通过，也不表示新 EVAS 已实现这些能力**。
`summary.json` 中源码/参考快照未改动的记录属于原审查；这里没有访问原工作树。

## 在新目录重跑旧源码探针

原执行环境是 macOS、Python 3.14.4、numpy 2.5.1、matplotlib 3.11.1、
Rust/Cargo 1.95.0。Python 包版本在发布时从同一环境补录，原运行未单独冻结环境锁文件；
不据此承诺跨环境逐字节复现。下面假定 `python3` 已具备 numpy 和 matplotlib，
Git、Cargo、rustc 可用。原执行未安装新依赖，没有使用 pytest。
运行器保留 macOS `.dylib` 名称；其他平台需要适配并记录新的执行身份。

从本仓库根目录创建全新的运行目录，保留本目录发布结果：

```sh
audit_dir="$PWD/experiments/legacy-evas-migration"
mkdir -p runs
run_dir="$(mktemp -d "$PWD/runs/legacy-evas-audit.XXXXXX")"
git clone --no-checkout https://github.com/Arcadia-1/EVAS.git "$run_dir/upstream"
mkdir "$run_dir/source-v0.8.7" "$run_dir/evidence"
git -C "$run_dir/upstream" archive 6cb6fa7a7dac70fc0d4120126d8cf74258e6637b | tar -x -C "$run_dir/source-v0.8.7"
cp "$audit_dir/probes/probe_legacy.py" "$audit_dir/probes/probe_frontend_waveforms.py" "$audit_dir/probes/probe_kernels.rs" "$run_dir/"
CARGO_TARGET_DIR="$run_dir/rust-target" cargo build --locked --offline --manifest-path "$run_dir/source-v0.8.7/evas/rust_core/Cargo.toml"
python3 -B "$run_dir/probe_legacy.py" > "$run_dir/evidence/python-probes.log"
python3 -B "$run_dir/probe_frontend_waveforms.py" > "$run_dir/evidence/frontend-waveform-probes.log"
rustc --edition=2021 "$run_dir/probe_kernels.rs" --extern "evas_rust_core=$run_dir/rust-target/debug/libevas_rust_core.rlib" -L "dependency=$run_dir/rust-target/debug/deps" -o "$run_dir/probe-kernels"
"$run_dir/probe-kernels" > "$run_dir/evidence/rust-probes.jsonl"
```

新目录中的 JSON 才是这次重跑的输出，不要覆盖发布收据或沿用旧二进制哈希。
原内核 `build_revision` 为未知；编译环境、目录或二进制改变后，记录自己的工具链和
SHA-256。检查器只读取发布证据，重跑结果需作为新执行单独分析。

积分参考是常量/线性输入的解析积分；低通参考为
`y(t)=t−1+exp(−t)`；贡献和隐式关系直接由原方程求解。
解析指标计算在 [verify_evidence.py](verify_evidence.py) 中，未用旧 Python 实现作为 Rust oracle。
原探针是诊断素材，未冻结完整资格阈值，也未运行旧 pytest 全集、新 EVAS、Spectre 或远程矩阵。

K01/K02 直接调用原 Rust 库的公开 API，展示试算/回查契约缺口，不声称完整生产电路曾走过
该顺序。E01 调用检测器 FFI；后续方向拒绝由源码核对，不是完整电路插桩。
宏、波形和解析器探针同样不能计作完整模型执行。

## 资产边界

运行器、本报告、精简 JSON 与清单在仓库内；固定旧源码可从公开提交取得。
历史镜像提取包、历史部署二进制、本地 debug 库、工作树快照和完整日志仅本地保留。
公开哈希可用于比对取得的同一文件，不能代替下载地址。
原源码的 [MIT 声明](https://github.com/Arcadia-1/EVAS/blob/6cb6fa7a7dac70fc0d4120126d8cf74258e6637b/LICENSE)
保留在上游；本 PR 没有 vendoring 旧运行时或旧测试文件。后续迁入素材须保存来源与许可。
