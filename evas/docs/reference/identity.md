# 包与内核身份

不提供 manifest 即可查询 Python 包元数据：

```sh
PYTHONPATH=evas/src python3 -m evas version --json
```

显式查询某个内核及其兼容性信息：

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas version --json --kernel evas/rust_core/target/debug/evas-kernel
evas/rust_core/target/debug/evas-kernel --version --json
```

两种查询均不编译模型、不执行数值求解。内核命令不读取 stdin，也不启动仿真诊断采集。

Python 响应采用 `identity_version=1`。`package` 给出发行名称、版本、
`metadata_source` 和 `build_revision`。源码调用读取所属包的 `pyproject.toml`；
该文件不存在时，安装态调用读取发行元数据。发行元数据缺失时返回退出码 2 和结构化错误。
当前构建没有记录源码 revision，因此 `build_revision` 为 null。
`platform` 描述运行 Python 的主机。

不传内核选择选项时，`kernel.status=not_requested`。
新增 `--bundled-kernel` 明确校验并查询安装包内核，与 `--kernel` 互斥；包内核缺失或身份校验失败时，返回退出码 2 和结构化诊断。
显式指定后记录解析后的
`path`、文件 `sha256`、内核 `reported` 身份。查询成功时状态为 `queried`，失败为 `error`。
SHA256 来自所选文件，不根据名称或当前 checkout 推断。
内核报告 `identity_version=1`、`name`、Cargo 包 `version`、`build_revision`、
`ir_schema_version`、`request_protocol_version` 及构建平台 `os`/`arch`。
当前内核构建未嵌入源码 revision，null 不能解释为当前 HEAD。

`compatibility.ir_schema_version` 是 Python 编译器的 IR 契约版本。
`compatibility.status` 为 `not_checked`、`ir_matched` 或 `ir_mismatch`。
匹配只证明内核报告了相同 IR schema，不能证明任意模型或数值结果正确。
请求格式没有独立版本元数据，因此两端 `request_protocol_version` 都为 null；
独立 `evas-ir` crate 的包版本不充当请求协议版本。

所选内核缺失、不可执行、响应损坏、不兼容或超时，均返回退出码 2。
stdout 保留可取得的身份及 `kernel.status=error`，stderr 输出已有的版本化机器诊断。
设备、命名管道和其他非普通文件在哈希前拒绝，避免读取无 EOF 的对象。
普通文件哈希完成后，身份子进程查询有五秒超时；失败不会另选二进制。
直接内核查询不含工件哈希，选择文件和计算哈希由 Python 调用者负责。
配套 wheel、默认内核选择和安装验证边界见[安装合同](install.md)。

实现见 [identity.py](../../src/evas/identity.py)、
[Python CLI](../../src/evas/__main__.py) 和 [Rust CLI](../../rust_core/src/main.rs)。
公共入口回归见 [test_identity.py](../../tests/test_identity.py)。
真实编译和瞬态 smoke 的运行身份以对应收据为准。
