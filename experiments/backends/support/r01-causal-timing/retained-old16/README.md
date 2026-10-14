# 原 16 项逐例收尾

固定 c5bad 核在原 16 项中保住 **12 项完整执行且原 checker 通过**，4 项 joint-affine 旧缺口仍拒绝。首次 c5-v1 实际是 11/16 完成：extend-hold/c2 的 kernel120s 超时完整保留；仅该例独占复测 c2-v2 在同核、同输入、同命令及原120s下 42.912 s 完成，原 checker 和有限输入/输出对照通过。合格集合是 12/16，首次失败没有改写成成功或从原分母删除。

CASEWISE.json 保留所有16例的首次结果、原输入与回复 hash、原设置警告、checker身份和判据；c2 两次收据单独并列。qualified 是“最新合格执行和原 checker”，不是“任一次失败都不存在”。原 checker 的所有12个成功保住，不能写首次12/16。

附加的 finite pair 也按实际收据保留：12项输出全部通过，但六项输入差未过，因此完整输入/输出有限对照仅6项通过。c1四项 vin 最大差0.084V，spec-acquisition/spec-ideal 的c2 vin差0.154V，均超过保留的0.002V门槛。这里不猜输入差产生原因，不用原checker通过掩掉，且不改原窗口、插值或预算。

本包父目录的新 timing 原请求另外完整通过1项。合并已复核17项为13项完整+原checker通过、新增原完整任务1项；另外53项未当前验收，不是13/70正式总成绩，也不作新Q声明。原70未整体重跑。

工具身份有明确范围：命令均指向保存的 c5bad artifact，提取核对实施 IDENTITY和artifact SHA；此 old16 目录没有每次执行的SOURCE-BEFORE/AFTER，因此不补造这些收据。核身份与 root 已固定执行说明一致，完整源码冻结身份在父目录保留。ORIGINS.json给原完整收据SHA，MANIFEST给规范化后包内字节SHA；机器私有路径仅替换为local-only basename，完整原raw不在这里。

运行 `python3 -B verify.py` 核casewise集合、同请求c2复测、原失败、checker verdict和finite maxima/预算一致性，只复算小收据，不重跑原checker或模拟器。CI/本地Python仍pending；保留未优化全套资源失败，没有“全绿”或已解决所有mesh资源问题的声明。
