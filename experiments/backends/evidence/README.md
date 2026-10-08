# 共享后端证据读取

这里提供当前 65-L、VCO 和 66-T 分析入口可复用的只读工具。
来源完整性和波形归一化分开调用；它们不计算模拟器是否对齐，也不赋予正式观察资格。

## 归档与解压成员绑定

```python
from experiments.backends.evidence.archive import verify_archive_members

members = verify_archive_members(
    collection,  # 含 raw.tar.gz 和已解压成员的 Path
    expected_sha256,  # 从固定、已审查的执行身份取得，不能取当前 COLLECTION
    ['spectre-output/FILE_MANIFEST.json',
     'spectre-output/runs/local-state/psf/tran.tran.tran'],
)
```

API 先核对固定 archive SHA，再从同一打开的归档读取全部 regular file，
逐项对比解压文件 SHA 和长度，返回 `{member_name: {'sha256': ..., 'bytes': ...}}`。
required 集合须非空，且每项必须是归档中的 regular file。
必需文件由调用者的冻结协议选定，不能从当前 manifest 推导必需集合。
归档中其余 regular file 也全部验证，FILE_MANIFEST 的内容本身因此受归档绑定。
已归档文件改动、空映射替换、同形同长 PSF 改值、缺文件均拒绝。

目录条目仅作为无 payload 的结构验证；拒绝重复路径、绝对路径、穿越、
symlink/hardlink、设备、FIFO 及其他非 regular payload。
归档文件、解压目录和文件路径的每个组件都拒绝 symlink。
Mac 临时目录的系统 `/var` alias 应由调用者先取得真实目录路径；
不要对待验证的解压成员调用 resolve 来隐藏 symlink。
目录条目不满足 required file，零 regular payload 也拒绝。
失败抛 ValueError。工具不解压、不写文件，不信任 mutable COLLECTION 或 manifest。
验证期间 collection 必须保持稳定；未归档的附加文件不属于这份身份。

| 不变量 | 执行入口 |
| --- | --- |
| 固定归档必须绑定每个解压 regular member，不能以提供的 key 取代完整检查 | `verify_archive_members`，`test_archive.py` |
| 空 manifest 与合法形状 PSF 篡改不能绕过来源检查 | 两项实际失败类别的负向校准，进入 numerical-assurance CI |
| 波形 token 与重复时点不得在归一化中丢失 | `psf.normalize`，保留原 PSF 两项校准 |

## PSF token 归一化

```python
from experiments.backends.evidence.psf import normalize

observations = normalize(psf_path, {'voltage_nodes': frozen_voltage_nodes})
```

`psf.py` 逐字节来自已审查提交
`c33a2f672bdbe549f706f8aa8d218e0f800881da` 的
`experiments/backends/event-alignment/normalize_psf.py`，原文件最后修改提交
`e1740c0f520b1b35b7906e0d63be78ec253e44a5`。
SHA256 为 `831bd269678251f61addebbd313d21b3b1a6f312c145be33e169ebb962c24fc8`。
原 `test_normalize_psf.py` SHA 为
`967b3699bed8bef6a728a820e01f14dbfaf9c59f7452ed5f9d0df13d9607ada1`；
`test_psf.py` 只把 import 改成共享模块，校准数据与断言保持不变。
原 #108 路径留给 owner 接入；冻结历史身份没有被改写。

归一化保留十进制 token、原信号、VALUE 行号和重复时点，拒绝缺信号、
非有限值、重复信号与截断文件。调用者须从冻结合同传入非空节点集合，
自行做时间序列、阶段和预算判定。导出 token 不证明 callback 次序或精确物理端点。

```sh
python3 -B -m unittest discover -s experiments/backends/evidence -v
```

此命令已接入 `.github/workflows/numerical-assurance.yml`。
本地校准和真实归档重读只证明该工具的读取边界，不是新的模拟器执行。
