# 256MiB收集硬上限下完整保留PSF

主任务正式reference v1遇到server profile校验拒绝：harness私有profile输出上限硬限制
256MiB，之前建议1GiB不能执行。旧3个unknown由主任务保留，不假定它们已远端求解。
本修复不改harness，不删波形点或截取片段，也不将拒绝的任务计入校准。

`run_one_source` 在solver进程计时结束、native/merged流及完整独立功能判读之后，对
每个paired PSF做gzip level6。解压遍历完整字节，长度与SHA相同才移除重复原格式；
record保留raw字节/哈希、gzip字节/哈希、相对路径、gzip-lossless-psf-v1、zlib版本、
往返核验与独立compression_elapsed_s。压缩时间不进入process_elapsed_s或native统计。
主功能PSF仍原格式。两侧warmup和10测量都保留，所有source/native/merged日志不删。

压缩文件必须是新路径；不覆盖已有gzip。写入、损坏、往返身份或删除原件失败时，
原PSF保留，清理自己新建的未成功gzip并判为invalid_solver_evidence，不报告紧凑成功。
失败基线为infrastructure，候选为零；不缩减配对分母。格式迁移后的正式档案必须
重新逐条解压复核身份、完整功能以及总输出字节数，不能仅据本地压缩比宣称校准过。

`lossless_psf_calibration.json` 对四份已有实际档案在本地工作站做真实gzip往返，非新
Spectre执行、非solver性能测试：

| 波形 | 原字节 | gzip字节 |
| --- | --- | --- |
| VCO baseline | 45571517 | 7212703 |
| VCO reference | 910872 | 154429 |
| UART baseline | 43704608 | 1194148 |
| UART reference | 663350 | 29721 |

VCO每侧warmup+五对的12份paired波形按这组大小约44.20MB（参考提交），主功能及其他
输出另计；若candidate仍为baseline，12份paired约86.55MB，主baseline PSF另45.57MB。
这是实际波形的容量校验，不保证任意超密候选输出都在quota内。正式归档仍受256MiB
硬上限，执行900s、每次子Spectre90s；不能删raw点改善容量。

本地tests执行真实gzip完整往返、CRC损坏、已有文件拒覆盖、写入失败、raw unlink失败。
早期performance source guard零分报告现补齐core verify schema：candidate/cases/contract/
checker/runtime/parser真实字节哈希及candidate_files；不需要启动求解才能形成可seal
审计的失败收据。源guard本地CLI测试验证字段身份及零求解调用。
