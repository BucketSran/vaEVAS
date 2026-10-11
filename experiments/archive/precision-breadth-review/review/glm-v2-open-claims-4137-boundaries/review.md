{
  "scope": "fixed4137 新增机制静态审查：NG AddRealValueToVector/ft_evaluate/ft_cpinit/main/read_initialisation_file 完整函数体，GN DEV_IDT/integrate/STORAGE/select_method/HS_PARAM/main.cc/config.h；核对 CLAIMS.md/README.md 中相应主张的准确性与资格边界（首 history 例外、动态 loader、实际方法、startup 历史覆盖）。不批准任何 exactSHA，不复审 runtime/DCtran/export 旧子链，不审 261 逐 run 身份或 scientific grade。",
  "standards": "只以本次提供的反汇编/源码文本为证据；callee 未提供且影响结论时记缺口，不得凭函数名或常见默认补链；runtime 字段仅当前提表述的候选；缺取证记 unknown 而非缺陷；draft 不因 runtime 非空获资格。",
  "spec": "open-backend-proof-v1；per_run_validation_required；七 draft reviews 为空、approval_status=not_requested_or_granted、无外部 approved exactSHA。",
  "findings": [
    {
      "id": "NG-STARTUP-PRECOND",
      "file": "observation-source-audit/collected/ng-startup-02/audit/disassembly-main.log",
      "lines": "af8ea–af904, af76c, af593",
      "claim": "CLAIMS.md NG-5 'main af91b–af93c 用 deck dirname 查 .spiceinit/spice.rc'",
      "trigger": "af8ea 测试 0x3b(%rsp)（默认 1，servermode 分支 af76c 与某选项 af593 清零）为零时直接跳 af980 跳过整个初始化文件搜索；af8f7–af904 中 optind>argc 时 jg af951 跳过 deck-dirname 分支",
      "impact": "startup 搜索链成立的前提还应包括：非 servermode/相关选项、argv[optind] 存在（deck 路径参数）。文档将 deck-dirname 搜索写成无条件主路径，缺少这两条触发前提",
      "requirement": "受限可闭候选必须列出全部触发条件，不能凭主路径表述省略分支前提"
    },
    {
      "id": "NG-RODATA-ASSERTED-NOT-SUPPLIED",
      "file": "CLAIMS.md",
      "lines": "NG 段第5条（'rodata 对应名称位于69a0be/69a0d1/69a0dc/69a0e5/69a0ea'）",
      "trigger": "disassembly-main.log 仅以 lea 引用这些地址（如 af951 引 69a0be、af91b 引 69a0d1），未随附 rodata 字节转储；69a0be（CLAIMS 称 SPICE_USERINIT_DIR）等内容在本包内无原文",
      "impact": "环境变量名与初始化文件名字符串当前是断言而非证据；若 69a0be 实为其他变量名，SPICE_USERINIT_DIR 段（af951–af973）的定性随错",
      "requirement": "影响结论的字符串常量必须以实际字节固定，不能按常见默认或函数名推断"
    },
    {
      "id": "NG-SPINIT-ENTRY-LOCATED-BUT-UNCLAIMED",
      "file": "observation-source-audit/collected/ng-startup-02/audit/disassembly-ft_cpinit.log",
      "lines": "c0bf3–c0c31（写 '/spinit'、fopen、inp_spsource），前置 c09d2–c0a4e（Lib_Path/Inp_Path/cp_getvar 分支）",
      "claim": "CLAIMS.md NG-5 '系统 spinit 选择和条件必须按实际 initialization 路径审'",
      "trigger": "系统 spinit 的实际加载入口已在本次提供的 ft_cpinit 反汇编中可见：仅当 Lib_Path 非空且经 com_set/cp_getvar/tildexpand 分支后才拼 <dir>/spinit 并 inp_spsource；同时 STARTUP_METADATA 中 spinit 文本含 'unset osdi_enabled'，默认使 osdi 块不加载",
      "impact": "CLAIMS 仍把系统 spinit 入口列为完全未定位（'准确系统startup初始化入口'列为后续件），未反映已可见的 ft_cpinit 条件分支；且 osdi 默认 unset 对模型加载主张有边界意义。属主张欠更新/边界应补明，非资格错误",
      "requirement": "新到证据应并入受限主张的边界；条件加载不得按默认推断为已加载或未加载"
    },
    {
      "id": "GN-STARTUP-INCLUDE-EXCLUDES-DEFAULT-PLUGINS",
      "file": "installed-gn-sources/src--gnucap--main--main.cc",
      "lines": "read_startup_files：findfile(SYSTEMSTARTFILE) 命中即 include，未命中才 'load DEFAULT_PLUGINS'",
      "claim": "CLAIMS.md GN-1/GN-6（loader 路径与 startup 候选）",
      "trigger": "SYSTEMSTARTPATH 含 '.'（cwd=/work），若 /work/gnucap.rc 等任一候选在科学 run 当时存在，则不仅 include 该文件，还整体跳过 gnucap-default-plugins.so 的默认加载，插件基线改变",
      "impact": "loader/load mgsim 注册集主张的前提必须显式包含'system startup 未命中否则插件基线不同'这一互斥分支；当前候选列表正确但未写出该后果。与 GN-6 '实际文件尚未取得' 一致，属应补边界非错误",
      "requirement": "动态加载闭合不得用'安装存在'代替'science run 实际加载'，且须覆盖 include/load 互斥分支"
    },
    {
      "id": "GN-EULER-OVERRIDE-CONDITION-DIVERGENCE",
      "file": "installed-gn-sources/src--modelgen--mgsim--d_va_filter.cc 与 src--gnucap--lib--e_storag.cc",
      "lines": "d_va_filter.cc integrate（time[1]==0 强制 Euler）；e_storag.cc differentiate（time[1]==time[2] 强制 Euler）、tr_c_to_g（time[1]==0）",
      "claim": "CLAIMS.md GN-4 '41–42 time[1]==0 强制Euler…有明确启动例外'",
      "trigger": "对 DEV_IDT（d_va_filter 局部 integrate）主张与代码一致，准确；但同一二进制内 DEV_DDT 走 STORAGE::differentiate，其强制 Euler 条件是 time[1]==time[2] 而非 time[1]==0",
      "impact": "不能把 idt 的'time[1]==0 首history例外'表述外推到其它动态器件；CLAIMS 已声明 ddt 需各自路径，本条仅为边界确认，无文本错误",
      "requirement": "启动例外须逐器件按实际函数表述，禁止类推"
    },
    {
      "id": "GN-HSPARAM-METHOD-TABLE-PRECEDENCE-UNSTATED",
      "file": "installed-gn-sources/src--gnucap--lib--e_storag.cc（method_select 表）与 e_hsparam.cc（method_propagate 表）",
      "lines": "method_select 注释 'only wins over non-only, local (_method_u) wins over opt'；HS_PARAM::method() 无硬值时回退 OPT::method",
      "claim": "CLAIMS.md GN-5 '每条件的 actual default METHOD生效，而非options回显'",
      "trigger": "表显示 meTRAPONLY/meGEAR2ONLY 等会覆盖 OPT 层选择；HS_PARAM 无本地 $method 硬值时 precalc_method 返回环境传播值，method() 为 0/unknown 时回退 OPT::method",
      "impact": "除已列的 HS_PARAM 覆盖外，还需在 integrator 闭合前排除 deck/scope 层 'only' 型 method 覆盖（含 $method 硬值与层级传播）；属前提清单应补项",
      "requirement": "实际方法闭合须按 method_select/method_propagate 全表语义验证，不能只验 OPT::method 回显"
    }
  ],
  "missing_context": [
    "NG：dvec_extend(c8140)、apply_func(c88c0)/apply_func_funcall、beginPlot.constprop.0(efb60) 函数体；7c4110 interpolated 实际初始化/覆盖点；69a0be/69a0d1/69a0dc/69a0e5/69a0ea 的 rodata 字节；69e566（afd85 cwd 段 rdi 字符串）内容",
    "GN：findfile(aeae0) 实现；/work/gnucap.rc、/work/.gnucap/gnucap.rc、/opt/gnucap/etc[/gnucap]/gnucap.rc、/root/.gnucaprc 的实际存在性/内容/级联（STARTUP_METADATA 未采）；load mgsim 搜索路径与实际 d_va_filter.so(b782...c231d) 绑定；原 compiled dut.so→生成 dut.cc→编译命令/头/库的 receipt；OPT::method 实际默认值与 u_opt2.cc Get 解析",
    "历史 /work、/root 状态：新容器快照缺失不证历史缺失；原 runner 复制行为、隐藏文件/符号链接保留情况未知（保持 unknown）",
    "852 完整数据、261 逐 run 身份、runtime/DCtran/export 旧子链：按授权不在本次范围"
  ],
  "limitations": "只读静态文本审查，未执行任何工具或 hash 核验（包文件 SHA/bytes 核验为 builder 证据，本审以其为前提不复算）。runtime 字段按受限候选对待，不构成已 qualified 的 runtime；本审不构成对外部 proof exactSHA 的批准，也不回填旧 I。新增结论：所供 AddRealValueToVector（f1598–f168c 含 dvec_extend 保存/恢复/回跳）、ft_evaluate（直接 vector 路同 rbp 返回、函数型 c867d 委派 apply_func）、read_initialisation_file（access R_OK→inp_source）、GN main/config 候选路径、d_va_filter integrate 首 history Euler 例外、STORAGE/HS_PARAM 方法选择均与 CLAIMS 表述相符；文档整体诚实区分可闭子链/partial/gap，七 draft 无一满足审批资格门。"
}
