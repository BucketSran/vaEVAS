# ngspice 保留字导出修复独立审查

结论：本次最小改动没有发现 P1/P2，可据此冻结新的 F03 36 槽执行身份并开展授权的实际复验。此意见不是新的 36 槽成绩、其他五个节点的实测证明、原旧失败回填或 native/runtime 资格批准。

审查 revision 是 primary `af2b0e98a7877b953069f79aabb7ef9e371d6feb` 上两个文件的未提交 diff，按实际文件 SHA 固定：inputs.py `aa2f181b2332d04a3c95b3ae9b6920abf653ac8a28f5b94546d7c6c2911d4426`；test_inputs.py `6dedea61ae43e5d24c55bc39a307ad10a71965c3e9e48404d20b3b7c7db17dd6`。范围仅 experiments/backends/paper/ 下这两个文件。

`decks()` 只对 NG wrdata 里的完整小写节点名 lt/le/gt/ge/ne/eq/or/and/not 加双引号。独立读取保留的 parse.c:785–821，恰有这九个小写 operator token 检查，且需要后接分隔符；:866–874 的引号分支返回 TOK_STR 并去掉外层引号。这个 public source 仅支持语法机制推导，不冒充安装 binary 与该公开 revision 完全同源。其他函数名、前后缀或大小写没有被扩散改写。

独立新旧函数对照使用同一完整九节点 physical card：EVAS/Spectre/Gnucap 三份生成内容逐字节相等；NG 只有一行 wrdata 改变。N0 ports、源输入、参数、tran 控制都未变。独立 test_inputs 全 7 项通过，日志 `astra-ng-quoted-inputs-tests.log`。这是本地生成/合同测试，不是九节点实际模拟。

实际 F03-dc-0--Q1 探针 archive SHA `53f052c2d43a69a4f366a959044d2ab3b1f387d581559141781839db6464cb96`（来自 collection receipt）；独立逐 59 个文件核验 FILE_MANIFEST 的 hash/bytes，全部一致。对旧 batch-v2 同槽核验 dut.va、dut.osdi、condition.json、requested_settings.json、requested_times.json 完全相同；tb.cir 逐字节只增加 lt/le/gt/ge 四处引号，旧/新 deck hash 分别 `2ac3fe35…a0aeb` / `a8a153c0…dd921`。本机未重新计算远端 tar 本体 hash；不能将 collection 声明说成本次重新哈希 tar。

实际 waveform header 仍是 v(lt)/v(le)/v(gt)/v(ge)，现有未修改 read_native 读到 186 行，键 time/u/a/b/c/lt/le/gt/ge/logic_out/tern。因此这个实际出口修复不要求读者改名或 reader 修补。独立记录 `astra-ng-quoted-export-probe-audit.json`。probe 未复制 observation_plan.json；最初批量比较该缺失附件的命令报错，已记录限制，后续仅核验真实存在五项输入/编译附件及完整 deck，不称独立证明了 probe observation-plan 文件身份。

实际验证仅覆盖 lt/le/gt/ge 四节点在该精确 0.5 输入、Q1 一槽；另外 ne/eq/or/and/not 只有上述源码/本地测试支持。其余 35 槽，特别相邻 binary64 的 F03 输入仍需真实执行与精确输入/输出证据。新36槽必须保留新的 deck/source/controller 身份，旧36个 missing-output 不可覆盖。

当前 d844 open adapter 的严格 wrdata grammar 只收 bare NAME，故 quoted deck 暂不能沿用其 native/runtime 正向资格。这是保守拒绝；不阻碍新的原始执行。若随后要为 quoted deck 取证，需另审明确范围的 grammar/proof/run-scope 更新，不能凭本报告直接授予资格。主工作区与旧冻结文件均未修改。
