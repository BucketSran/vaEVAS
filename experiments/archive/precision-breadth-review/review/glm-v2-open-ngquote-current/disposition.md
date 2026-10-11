# Actual NG quoted-node review

实际 glm-5.3 canonical 完整 1 turn，70.457s，USD0.318745，response b1f3d7e6ee5504dababfbfb7defec131ff1801755644fea492d48e3cde40db9f。所有原文件保存于本目录；准确路径 glm-v2-open-ngquote-current/review.md，未创建历史伪链接。

完整 inputs.py/test_inputs.py/observations.py、parser-source parse.c/parse-bison.y、实际 probe deck/change/log/compile/simulate receipts+manifest+rawheader供审。提交 d6ac5ae3 两个变更 blob SHA256 精确等于供审 snapshot，见 commit-identity-check.json，不需重审相同代码。

允许新 36 F03 出口实验：端口只涉及四个实际 probe 的 lt/le/gt/ge；仅变 wrdata 引用，原 DUT/OSDI/设置/observer/旧RESULT 不修改，新 deck hash 独立保留。逐槽检查真实 header/完整向量，导出可写不等于比较/逻辑/三元完整波形科学通过。F03 邻近 0.5 的 actual-input 边界、native/runtime 仍待证。

原模型 medium 是另五个名称仅源码预测、固定安装尚未实测的证据限制，不是已证明错误代码/恶化出口/当前36任务阻塞。已明确区分 source-based 与 actual-four，无人宣称九名均安装实测；不能从此要求额外五个模型必须全部实测才能执行授权的36槽。GN出口/未来版本header两个 low 也是未来范围限制，当前其他backend保持生成不变不是其科学通过证明。

模型 spec/finding 把 ca1037be... compiler SHA 错称 ngspice binary SHA，需纠正：它是 OpenVAF-reloaded compiler，安装 ngspice actual binary SHA 见其他已保存 tool identity（e9b0e776...）；“安装公开commit未知”不改变四名实际 probe 的直接机制事实。报告文本不覆盖、不冒称模型自行执行hash核验。
