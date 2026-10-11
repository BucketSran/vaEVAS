```json
{
  "scope": "对候选 f12598d2 中 precision_breadth_reanalysis.py 的外部 open-evidence CALLER 集成（seal_open_evidence / verified_execution_inputs / external_open_evidence / integrator_axis / open_gate / worker 集成 / main 新 CLI 选项）及新增测试做独立静态复审；外部适配器 d844b795 仅按已批准摘要作接口/调用方核对；依赖模块（precision_breadth_run.py、precision_run.py、precision_report.py、runner.py、settings_readback.py、observations.py、inputs.py）按需核对调用契约。",
  "standards": "信任边界最小化（外部适配器/proof 仅按协调者批准的精确 SHA 信任）；缺失/失配证据一律 fail-closed 保持 unknown；原始 lane/RESULT/manifest 不可变且分析前后二次校验；legacy 配置 + 官方 profile 绑定 + 实际设备 integrator 三重门不得被外部证据替代；冻结科学快照与外部资格身份分离；输出记录（VARIANTS.tsv/GROUPS.json）保持完整分母不变；symlink/路径逃逸拒绝。",
  "spec": "REANALYSIS.json 保留原始执行/数值/行为/证据/配置/本地观测/运行时控制；源或物理输入变更需重新执行；F03/F04 等 exact-input 缺证保持 unknown；EVAS/Spectre 的 actual_integrator 为 not_applicable 且不改变原方法资格；外部 open 后端额外要求 identity/config/integrator 三轴 qualified；无批准 proof 时保持 unknown 属预期而非缺陷；不执行任何模拟器或远程命令。",
  "findings": [
    {
      "severity": "low",
      "file": "experiments/backends/support/precision_breadth_open_evidence.py (d844b795, 由 f12598d2 的 external_open_evidence 复制到 output/external-open-evidence/adapter.py 后执行)",
      "line": "19-21",
      "trigger": "密封后的适配器文件位于 <output>/external-open-evidence/adapter.py，其 `ROOT = Path(__file__).resolve().parents[3]` 不再指向仓库根，`sys.path.insert(0, str(ROOT/'experiments/backends/paper'))` 插入的是不存在的路径；`from settings_readback import ...` 仅因 worker 进程中 sys.modules 已由 frozen 快照预先加载 settings_readback 才偶然成功。",
      "impact": "适配器导入正确性依赖调用方环境的隐式副作用。若未来调用方未预载 settings_readback，将抛出 ModuleNotFoundError（ImportError，不属于 external_open_evidence 第 293 行捕获的 (ValueError,KeyError,FileNotFoundError,TypeError)），直接传播到 worker 的宽泛 except，使该 slot 全部资格轴 unknown——结果仍 fail-closed，但破坏了 external_open_evidence “返回 unknown 轴字典” 的函数契约，且诊断信息退化为裸异常而非逐轴 issues。",
      "requirement": "外部适配器应以密封副本自身可复现的方式解析依赖，或调用方应在密封时改写/固定 import 路径；external_open_evidence 的异常捕获应覆盖适配器加载期异常（至少 ImportError/OSError）以维持其声明的返回契约。"
    },
    {
      "severity": "low",
      "file": "experiments/backends/support/precision_breadth_reanalysis.py",
      "line": "270-294",
      "trigger": "external_open_evidence 内部 try 块只捕获 (ValueError,KeyError,FileNotFoundError,TypeError)。已批准适配器为任意 Python 代码（第 285-286 行 exec_module 动态执行），其抛出的 OSError（如权限拒绝读取 waveform.txt）、AttributeError、IndexError、ZeroDivisionError 等均不被此层捕获。",
      "impact": "该函数在直接调用场景（如单元测试或未来其它调用方）会以未预期异常崩溃而非返回逐轴 unknown；在当前 worker 中由外层 `except Exception`（第 380-384 行）兜底为全 unknown，最终结果 fail-closed，但 external_open_evidence 的 API 契约与其注释声明的失败语义不一致。",
      "requirement": "声明为“malformed/missing evidence fail closed 返回 unknown 轴”的函数应覆盖适配器执行期全部常规异常类别，或明确记录仅 worker 层兜底。"
    },
    {
      "severity": "info",
      "file": "experiments/backends/support/precision_breadth_reanalysis.py",
      "line": "304-312",
      "trigger": "open_gate 对 open 后端将 config/native/runtime 整体替换为 adapter 的 native/runtime 轴（`return config,adapter['native'],adapter['runtime']`），legacy native/runtime 仅作为 legacy_axes 记录，不进入门条件；门条件只包含 legacy configuration + 官方绑定 + 外部 identity/config/integrator。",
      "impact": "若 legacy native/runtime 为 unknown 而外部 adapter 的 native/runtime 为 qualified，slot_status（第 177 行）将以外部轴放行。这与“外部资格证明覆盖导出/原点/运行时映射，科学分级仍归原 checker”的声明的意图一致（外部 proof 的 run_scopes 绑定精确 argv/冻结输入/编译产物），且绑定不匹配时仍 fail closed；但 native/runtime 的 legacy→外部替换是隐式策略，未在 open_gate 的 claim 文本中显式说明。",
      "requirement": "建议在 open_gate 返回的 claim 或 issues 中显式记录 “native/runtime 由外部轴替代 legacy 轴” 的策略，避免读者误以为 legacy native 仍是门。"
    }
  ],
  "missing_context": [
    "真实的外部批准 proof 摘要（--approved-open-proof-sha256 / --approved-open-adapter-sha256 的协调者授权值）当前不存在，属待补证据：本复审只能确认无摘要时全轴保持 unknown 的 fail-closed 路径，无法核验真实 proof 的 schema/attachments/run_scopes 内容。",
    "未提供 precision_breadth.py（load_contract/assess/observation_plan 的实际实现）、冻结 cards.json、SOURCE_IDENTITY.json、PROFILE_BINDINGS.json 实例及真实 lane 产物；worker 内对这些 API 的调用契约仅按测试桩核对。",
    "未提供 precision_binding_run.py（DEEP_BOUND 来源）与 process.py（execute/preflight 底层），其行为不在本次范围。",
    "外部适配器 d844b795 的内部数学（如 Gnucap TIME_t 量化映射、s_tr_set.cc:176-191 引用）按题设已另行评审，本次仅核对其 qualify_open_backend 签名、七轴返回、fail-closed 语义与 CALLER 的摘要把关接口一致性（一致）。"
  ],
  "limitations": "纯文本静态复审，未执行任何代码、测试或仓库检索；测试文件中的断言视为作者自证而非证明。无法验证 git 提交身份、真实冻结输入哈希、容器镜像/二进制摘要或 Spectre 私有网格；无法检测并发/时序类问题（snapshot 的读-改-读校验仅覆盖其列出的文件集合）。上述 findings 中两条 low 均最终 fail-closed，不影响“缺证据保持 unknown、不升级资格”的核心保证。"
}
```
