# 安装 Python 包与配套内核

平台 wheel 包含 Python 前端和独立 `evas-kernel` 程序。安装 wheel 不需要 Rust。
发行名称仍为 `evas-rebuild`，命令仍为 `evas-rebuild`；没有公共 PyPI 发布或版本 tag。
从本地构建产物或具名 CI artifact 取得 wheel 后，在匹配平台安装：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install /path/to/evas_rebuild-0.13.0-py3-none-PLATFORM.whl
.venv/bin/evas-rebuild version --json --bundled-kernel
.venv/bin/evas-rebuild solve /path/to/sim.json
.venv/bin/evas-rebuild transient /path/to/transient.json
.venv/bin/python -m evas.results run /path/to/transient.json --out /path/to/new-output
```

`solve`、`transient`、`simulate` 及 results 的 `run` 默认使用当前安装包内核。
Python API 的 `solve(..., kernel=None)`、`transient(..., kernel=None)`、
`simulate_scs(..., kernel=None)` 与 `results.run(..., kernel=None, out=...)` 同样使用它。
默认选择检查构建记录、文件 SHA256、内核实际报告、IR17、包版本和 OS/架构。
macOS 的 arm64 映射到 Rust 的 aarch64，darwin 映射到 macos。

显式 `--kernel PATH` 或 API `kernel=PATH` 始终选择该文件。缺失、不可执行或运行失败
不会切换至包内核。显式路径保留已有请求/响应协议验证，不要求旧内核新增身份元数据；
results 仍需已有身份查询合同。请求协议没有独立版本，字段继续为 null，不能解释为已确认
全部协议兼容。IR 不匹配需用配套前端/内核重新编译原模型。

只查询包可继续使用 `evas-rebuild version --json`，不查找内核。
`--bundled-kernel` 明确查询安装包内核，`--kernel PATH` 查询指定文件，二者不能同时提供。
`compile` 和 `lint` 不需要内核；`lint` 仍拒绝执行选项。
缺少或损坏的包内核给出选中路径与修复方法，可重新安装匹配平台 wheel，
也可源码构建后显式指定内核。错误架构可能由平台记录检查或操作系统执行错误识别。
没有自动改用其他数值实现的路径。

## 平台与验证边界

新增 [安装 CI](../../.github/workflows/package-install.yml) 的目标是 Ubuntu 24.04 x86_64 / Python 3.10
及 macOS 14 arm64 / Python 3.12。实际通过情况以对应工作流 revision、runner 和 artifact 为准；
配置任务不等于已获得执行证据。本地首次安装验收在 macOS 26 arm64 / Python 3.14 执行。

Linux 构建生成本机 `linux_x86_64` 标签，没有声明 manylinux、musllinux 或任意 Linux 发行版兼容。
Ubuntu 24.04 的 glibc/链接环境是本批 CI 边界；在不同 libc 或旧系统上需独立构建和验收。
macOS wheel 保留构建环境产生的系统版本/架构标签，不声明 universal2、Intel 或更旧系统支持。
其他平台可以采用下面的源码路径，源码能构建也不代表已通过该平台安装验证。

## 从源码构建

需要 Python 3.10+、原生 Rust/Cargo 及系统链接工具。
构建 Python 环境需能取得 setuptools 和 build；Cargo 需取得 Cargo.lock 中锁定的依赖，
或已有相应缓存。构建不借用开发目录中已有的内核：

```sh
python3 -m pip install build
python3 -m build --sdist --outdir runs/package-dist evas
python3 -m pip wheel --no-cache-dir --no-deps --wheel-dir runs/package-dist runs/package-dist/*.tar.gz
python3 scripts/check_installed_evas.py --wheel runs/package-dist/*.whl \
  --sdist runs/package-dist/*.tar.gz --out runs/package-install
```

从 sdist 解包后的项目也可运行 `python3 -m build --wheel`。
sdist 包含 Cargo.toml、Cargo.lock、内核及独立 IR crate 的 Rust 源码和构建配置；
不包含 target、包内二进制或旧构建目录。构建钩子执行 `cargo build --locked --release`，
显式选择 rustc 的原生 host target，再把新内核和真实身份/哈希记录写入 wheel。
不支持用这个钩子交叉编译或手工伪造 wheel 平台标签。

已有源码使用方法保持可用：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas solve evas/examples/01-static-gain/sim.json \
  --kernel evas/rust_core/target/debug/evas-kernel
```

editable 安装保留这条显式内核路径，不在源码目录生成二进制。

## 安装验收

[check_installed_evas.py](../../scripts/check_installed_evas.py) 检查 wheel 标签与 sdist 构建输入，
在仓库外创建新 venv、移除 PYTHONPATH/PYTHONHOME，然后从真实安装路径执行 API 和 CLI。
静态独立答案为 `2*u+0.25` 在 `u=-0.5,0,0.75 V` 的 `-0.75,0.25,1.75 V`。
瞬态独立答案为 `idt(1,0.25)` 在 `t=0,0.25,0.5 s` 的 `0.25,0.5,0.75 V`，外部绝对误差限 `1e-9 V`。
验收还覆盖 SCS、CSV 列/单位/时间/行数/数值、文件哈希、完成标记、卸载后无残留及重装。

负向验收覆盖缺包内核、损坏二进制/构建记录、不可执行、错误平台记录、错误 IR 身份、
失败产物和显式路径失败不回退。错误平台记录和假内核是独立边界测试，
不能替代真实异架构二进制的执行证据。验收另用损坏但可执行的文件观察实际 OS 拒绝执行。
不把安装通过算为新增数值能力或 Spectre 对齐证据。

构建扩展依据 [setuptools 命令扩展合同](https://setuptools.pypa.io/en/latest/userguide/extension.html)，
wheel 标签依据 [Python 包平台标签规范](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/)。
