# PR273 第 3 轮源码集成报告

标注：**[已执行]** 实际运行并留有原始输出；**[静态]** 阅读代码；**[推断]** 未直接验证。机器可读数据见 `result.json`，原始输出在 `logs/`，矩阵账本在 `replay/`、`results/`，脚本在 `scripts/`。

## 0. 交付与结论

| 文件 | sha256 | 内容 |
| --- | --- | --- |
| `merge-resolution.patch` | `8530011802bda5deb7d4c0ad415b0139e4d9938529e05122d33d57f93601d49b` | 只解决合并冲突，相对 bf2ec410，6 个 PR273 路径 |
| `fixes.patch` | `0f517b450e12cb2c53744e5517bae036994b50f1466a17076477951085d89709` | 在合并结果之上的第 1–4 项修正，5 个文件 |
| `source.patch` | `246d7e1baa105e87afe1fd41a8a83f7d5859e5ae5195f1450284fd7dab54c426` | 两者累计，相对 bf2ec410，9 个文件 |

- 三份补丁在 bf2ec410 的导出副本上 `git apply` 无冲突；`source.patch` 单独应用、以及先 `merge-resolution` 再 `fixes` 依次应用，结果都与最终树逐字节一致。[已执行]
- 导出核对：bf2ec410 的 49,608 个 blob、9ea5de9f 的 49,573 个 blob，逐个重算 SHA-1，缺失 0、不符 0（`logs/verify-export-*.txt`）。[已执行]
- 全部 9 项必跑测试/检查通过（§6）；STD-01 的 30 个用例在合并树上 0 误放 0 误拒；nightly 新控制 6,329 项 0 误判；PR6 各矩阵重放无回退，只有 8 个因 nightly 拼写而必须调整的期望（§3）。[已执行]
- 没有改动 criteria、DUT、collector、language-profile、可信门禁、admission 作业步骤、`generate_catalog.py`，也没有重生成 catalog；以上 9 个受限文件与 bf2ec410 逐字节相同。[已执行：cmp]
- 主控待办：重生成 catalog 派生数据（`catalog-sources`、各 index、TRACEABILITY；`numerical-assurance.yml`、`test_discover_rust.py`、`test_regression_admission.py` 与新文件 `test_regression_shard_selection.py` 都是 catalog 登记的文件）；发布、CI、审核派发。

## 1. 合并冲突（`merge-resolution.patch`）

PR273 独有的 `benchmark-evidence.yml`、`collect_ci_inventory.py`、`test_ci_inventory.py`、`test_ci_pins.py` 取 9ea5de9f 原字节（cmp 确认）。`git merge-file`（三方：02dee32b / bf2ec410 / 9ea5de9f）在 `numerical-assurance.yml` 产生 3 个冲突块，`package-install.yml` 文本上自动合并。[已执行]

| 块 | main (PR6) | PR273 | 解决 |
| --- | --- | --- | --- |
| rust-regression 作业（约 268 行） | `python-version: '3.12'` + `rustup toolchain install "$RUSTUP_TOOLCHAIN" … clippy rustfmt` | `3.12.15` + `install stable …` | `3.12.15` + PR6 的 rustup 行 |
| regression 分片作业（约 338 行） | 同上 | 同上 | 同上 |
| properties-and-ngspice（约 656 行） | `3.12` + `apt-get install -y ngspice` + `rustup toolchain install "$RUSTUP_TOOLCHAIN"` | `3.12.15` + `ngspice=42+ds-3build1` + `rustup update stable --no-self-update` | `3.12.15` + `ngspice=42+ds-3build1` + PR6 的 rustup 行 |

两边的意图都保留：PR273 的 python/ngspice/runner 固定，PR6 的 Rust 选择。`package-install.yml`：自动合并会把 PR273 的顶层 `env: RUSTUP_TOOLCHAIN: '1.99.1'` 字面值带进来，与 PR6 的 `workflow_call` 输入（`inputs.rust_toolchain` → job env）并存——这是语义冲突。已删除该顶层 env 与注释，保留 PR273 的 `3.10.22`/`3.12.10` 与 `build==1.6.1`，其余取 PR6。合并后 `package-install.yml` 相对 main 只有 3 处改动（两个 python 补丁版本、`build==1.6.1`）。[已执行：diff]

此时 PR273 自带的 `test_ci_pins.py` 在合并树上失败（断言顶层 `RUSTUP_TOOLCHAIN` 字面值）；`test_discover_rust.py` 因 fuzz-smoke 的带日期 nightly 失败 8 项。这两处正是第 2、3 项的由来，所以 `merge-resolution.patch` 本身并不全绿，这是预期的。[已执行：`logs/merged-ci-pins.out`、`logs/merged-discover-rust.out`]

## 2. 第 1、2 项：STD-01 与 Rust 断言分工

**做法**：先用 `patch -p1` 应用已验收补丁（`source.patch` sha256 `a95c6d34…e30be4b2`，应用后文件与主控 `patched/` 副本逐字节一致，sha256 `3df79a73…`）。然后把 `test_ci_pins.py` 的 Rust 部分整体移出：

- `test_ci_pins.py` 现在只管：runner 标签、`setup-python` 的补丁版本、ngspice 包版本、`build==1.6.1`。模块文档字符串写明分工。删除了 `commands()`、`nightly_tokens()`、解析器里的 `toolchain` 捕获，以及对 `package-install.yml` 顶层 `env`、`$RUSTUP_TOOLCHAIN`、`stable`/`+` 的全部断言。
- Rust 工具链的一切（固定值、白名单、reusable 输入接线、fuzz-smoke 的 nightly）归 `test_discover_rust.py`（PR6 守卫）。没有重复实现，也没有留下互相矛盾的断言。[已执行：`logs/final-test_ci_pins.*` 4 项 OK]

**STD-01 的 30 个审核用例**（`results/pin-redgreen-merged.json`，脚本 `scripts/pin_redgreen_merged.py`）[已执行]：

| 设置 | 误放 | 误拒 |
| --- | --- | --- |
| 9ea5de9f 工作流 + PR273 原测试 | 8（`quoted-matrix-python-key`、`quoted-matrix-runner-key`、`quoted-runs-on-key`、`flow-matrix-row`、`quoted-ngspice-run-with-decoy`、`quoted-build-run-with-decoy`、`rust-job-env-override`、`rust-build-step-env-override`） | 0 |
| 9ea5de9f + 已验收 STD-01 补丁 | 2（两个 Rust env 覆盖） | 0 |
| 合并树 + PR273 原测试（Rust 断言矛盾） | 0 | 4（`original` 与 3 个固定写法：原测试对 PR6 接线整体误拒） |
| **合并树 + 最终 `test_ci_pins.py` + PR6 守卫** | **0** | **0** |

最终 `test_ci_pins.py` 单独仍放过 5 个 Rust 编辑（`nightly-floating`、`rustup-stable`、`rust-env-global-floating`、两个 env 覆盖），它们全部被 PR6 守卫拒绝——这是分工的预期结果，不是缺口。其中 3 个编辑针对合并后的接线重定向（顶层字面值在 package-install 里已不存在：全局 floating 改为改 `numerical-assurance.yml` 的顶层 pin；job env 覆盖改为替换 `inputs.rust_toolchain`）。[已执行]

## 3. 第 3 项：nightly 固定与 PR6 守卫

**边界**：`test_discover_rust.py` 新增一处常量 `FUZZ_NIGHTLY = 'nightly-2026-10-27'`。例外仍然只在主 workflow 的 `jobs.fuzz-smoke`、只在 `rustup toolchain install`（单一参数）、`cargo +…`、rust-cache 的 `toolchain:` 三种命令/输入、每个选择单独判断（守卫机制未改，只把允许值从 `nightly` 换为常量）。不带日期的 `nightly` 与其他日期一律拒绝。真实 workflow 检查新增：fuzz-smoke 里常量恰好出现 4 次（install 1、`cargo +` 2、cache 输入 1），其余 CI 行（注释除外）不得出现 `nightly`。`numerical-assurance.yml` 顶层注释写明常量与测试的对应关系，改日期须两处同改。[静态+已执行]

**按类补正反控制**（`scripts/nightly_class_controls.py`，`results/nightly-class-controls.json`）。选择矩阵由 3,248 项增到 6,329 项（6,144 必拒、185 必收，新守卫 0 误判）。按类修正前（bf2ec410 守卫）后：

| 类 | 项数 | 修正前（bf2ec410 守卫） | 修正后 |
| --- | --- | --- | --- |
| 固定的带日期 nightly，fuzz-smoke 内三种命令/输入（期望：收） | 21 | 新控制（旧守卫会拒） | 21/21 收 |
| 旧的不带日期 `nightly`，fuzz-smoke 内三种命令/输入（期望：拒） | 21 | 0/21（旧守卫收） | 21/21 拒 |
| 别的日期，fuzz-smoke 内三种命令/输入（拒） | 42 | 新控制 | 42/42 拒 |
| 固定日期 / 不带日期 / 别的日期，fuzz-smoke 内其他形态（环境变量、`rustup default`、引号变形等，拒） | 93 / 93 / 186 | 不带日期 93/93 | 372/372 拒 |
| 固定日期 / 不带日期 / 别的日期，fuzz-smoke 外三种命令/输入（其他作业、新 workflow、新 composite，拒） | 144 / 144 / 288 | 不带日期 144/144 | 576/576 拒 |
| 固定日期 / 不带日期 / 别的日期，fuzz-smoke 外其他形态（拒） | 761 / 761 / 1,522 | 不带日期 761/761 | 3,044/3,044 拒 |
| 同一行第二个选择（`"cargo" +1.98.0`、`+stable`、`install … stable`、`install 固定值 nightly`、别的日期等，拒） | 44 | 5/5（其余为新） | 44/44 拒 |
| 作业名相似、带引号的 fuzz-smoke 键、另一文件里的 fuzz-smoke、fuzz-smoke 之后的作业 | 3+3+1+1+1+6 | 旧值对应项全对 | 全对（带引号的同一作业收，其余拒） |

另有单元表 `test_nightly_is_excused_only_for_the_exact_command_of_jobs_fuzz_smoke` 按固定值、不带日期、别的日期重写（接受 8 种写法 × 4 个位置，拒绝列表扩为 ≈ 100 种）。[已执行：`results/nightly-class-controls.json`]

**守卫变异检验**（`scripts/mutants_nightly_guard.py`）：9 个变异（接受不带日期、接受任意带日期、常量扩到所有作业、扩大命令种类、作业名按前缀匹配、任何 workflow 里的 fuzz-smoke、fuzz-smoke 内整体放行通道关键词、`install` 多参数放行、常量与 workflow 日期不符）全部被至少一项 nightly 相关测试抓住，未变异的对照全过。[已执行]

**PR6 第 5、6 轮矩阵重放**（bf2ec410 与最终树各跑一次，同一套脚本，脚本取自 `pr6/r6-p3-fixes-sonnet-20261028`；原始输出在 `logs/replay-main`、`logs/replay-after`）[已执行]：

| 矩阵 | bf2ec410 | 最终树 |
| --- | --- | --- |
| 工具链 2,053 | 2,053/2,053 | 2,045/2,053（8 个必须调整的期望，见下）；调整后矩阵 2,459/2,459 |
| 选择变体（守卫自己的） | 3,248 | 6,329/6,329（含新增控制，0 误判） |
| 16 个最终复现 | 16/16 | 16/16 |
| 8 行 shell 复现 / 3 个 historical 变体 | 8/8；3/3 | 8/8；3/3 |
| Rust 收据 | 251/251 | 251/251 |
| 静态边界 | 11/11 | 11/11 |
| historical 216（`HistoricalGuardTests`，单元测试内） | 通过 | 通过（`test_discover_rust` 42 项 OK） |
| Markdown | 81,370/81,370（175 接受）；33 个前轮拒绝全拒；30 个空白控制 0 误放 | 同左 |

**必须调整的期望（逐项）**：工具链 2,053 中审核方把"`main-fuzz` 位置的 `nightly`"作为允许项，共 8 个形态（`cargo-plus`、`cargo-quoted-selector`、`cargo-quoted-yaml`、`rustup-install`、`rustup-install-alias`、`with-block`、`with-flow`、`with-quoted-key`）；合并后这 8 个因不带日期而被拒，这正是第 3 项要求的行为。把允许值改为 `nightly-2026-10-27` 并新增该值的整套控制（`scripts/reviewer_toolchain_cases.adjusted.txt`，其余逻辑原样）后 2,459/2,459，0 误放 0 误拒。选择变体矩阵的变化：bf2ec410 里 21 个"fuzz-smoke 内 `nightly` 必收"变为必拒（18 个 `FUZZ_NIGHTLY_FORMS` + 3 个 `fuzz-*` 控制），另有若干仅因命令文本中的 `nightly` 改写而改名的混合控制（期望方向不变）。没有其他期望改变。[已执行]

## 4. 第 4 项：coverage 按尝试次数选 artifact

**修法**（只改 `regression` 上传名、`regression-coverage` 作业）：
- 上传名：`python-regression-shard-${{ matrix.shard }}-attempt-${{ github.run_attempt }}`。
- `regression-coverage` 新增步骤"Select the newest attempt of each regression shard"，在下载后、`Verify complete raw coverage` 之前执行：只接受名字完全匹配 `python-regression-shard-[0-3]-attempt-[1-9][0-9]*`（ASCII）的目录；符号链接、普通文件、非法名、大于本次 `run_attempt` 的尝试、一个目录里 `report.json` 不是恰好 1 个、某个分片没有合法目录，一律写入错误并非零退出。每个分片取尝试次数最大（按整数比较，不按文本，不看目录时间）的一份，其余记为 superseded。同一分片同一尝试的重复在下载层不可能（下载按名建目录，重名会被 action 合并或拒绝；若合并出多个 `report.json` 则被"恰好 1 个"拒绝）[静态+已执行]。
- 所选与被取代的名字和尝试次数写入 step summary 和 `runs/regression-shard-selection.json`（含每份 report 的 SHA-256 与错误表，失败时也写）；该收据随 `python-regression-timings` 上传。`Verify complete raw coverage` 只合并收据里选中的 4 份报告，不再 `rglob`。

**测试先行**：新建 `scripts/tests/test_regression_shard_selection.py`（12 项），用 `run_body` 取出 workflow 里的实际脚本，在合成目录上运行：单分片多次重跑（1/2/3）、尝试 10 vs 9（文本序相反）、目录时间与 ID 顺序相反、缺分片、无合法名（旧名）、13 种非法名、散落文件、符号链接/文件冒充、同一目录两份报告、没有报告、未来尝试，以及"上传名带尝试、全仓只有一个文件提到 `python-regression-shard`、且都是带尝试的写法"。先写测试、后改 workflow：改前 `FAILED (failures=1, errors=22)`（`logs/shard-selection-red.stderr`），改后 12 项 OK。`test_regression_admission.py` 的端到端用例改为：4 份尝试 2 的报告 + 一份被取代的分片 1 尝试 1，先跑选择步骤，再跑原有的覆盖与准入命令，断言选中与被取代名字；同时把新步骤加入 `bash -n` 语法检查。[已执行]

**变异检验**（`scripts/mutants_shard_selection.py`）：17 个变异（上传名去掉尝试、按名字文本选、选最小、选最新目录、忽略非法条目、放过符号链接/文件、允许多份或零份报告、允许未来尝试、允许 4 号分片、允许尝试 0/前导零、不报缺分片、错误仍退出 0、失败时不写收据、摘要省略名字、合并仍用 rglob、收据不上传）全部被抓住。第一次运行 16/17：`symlink-and-file-allowed` 逃逸，据此补了 `test_a_legally_named_symlink_or_plain_file_is_not_an_artifact`，重跑 17/17（首次输出保留为 `results/mutants-shard-selection.attempt1.json`）。[已执行]

**全仓搜索** `python-regression-shard`：除 `numerical-assurance.yml`（上传、下载 pattern、选择步骤的正则）外，只有 `test_regression_admission.py`（fixture）与新测试引用；没有其他作业、脚本、README、baseline 依赖旧名。`evas/validation/baselines/regression-v1.json` 只引用 `python-regression-timings`（未改名）。[已执行：全仓 grep + 测试内的同样搜索]

## 5. context 不变性（逐项）

PR273 r2 在旧池上与可信 context 精确匹配。本次改动不改变：
- `collector_sha256`：由 `run_regression.py`、`ci_evidence.py`、`regression_reason_identity.py`、`regression_observation_policy.json` 的哈希组成，四者与 bf2ec410 逐字节相同。[已执行：cmp]
- `invocation`（modules、pattern）：由 `run_regression.py` 命令行产生，`regression` 作业的 `run:` 没有改动。[已执行：作业块 diff 只有上传名与注释]
- `runtime_profile`（python 版本串、platform、machine、`ENVIRONMENT` 变量）：`regression` 作业的 `env`、`setup-python`（`3.12.15`，由 PR273 固定，与此前 `3.12` 解析结果一致，**[推断]** 其依据为 PR273 r2 的 CI 40516612690 精确匹配记录）、runner（`ubuntu-24.04`，与 `ubuntu-latest` 当前同一镜像，**[推断]**）均与 PR273 r2 相同；artifact 名、coverage 的选取步骤都不进入 `ENVIRONMENT`（`GITHUB_RUN_ATTEMPT` 不在 `ci_evidence.ENVIRONMENT` 里，grep 确认），所以不影响。[已执行 + 推断]
- 注意（风险，非改动引起）：分片重跑在新池上仍会得到不同的 runtime_profile，这是镜像漂移，由第 4 项的选择步骤使"最新一次的分片"而不是"id 最大的旧分片"被合并，从而不再混合旧池分片；混池仍会被 `merge_reports` 的元数据检查拒绝，这是正确行为。

## 6. 测试与检查（最终树，Python 3.12 lint-venv，`logs/final-*`）[已执行]

| 命令 | 结果 |
| --- | --- |
| `unittest discover -s evas/capabilities -p 'test_*.py'` | 101 项 OK |
| `test_ci_pins` | 4 项 OK |
| `test_discover_rust` | 42 项 OK（约 115 s） |
| `test_rust_catalog_reconcile` | 10 项 OK |
| `test_ci_inventory` | 22 项 OK（含 PR273 新增 1 项） |
| `test_ci_selection` | 38 项 OK |
| `test_fast_feedback` | 14 项 OK |
| `test_regression_admission` | 7 项 OK |
| `test_regression_shard_selection`（新） | 12 项 OK |
| `render.py --check` | `checked 84 capability files`，退出 0 |
| `ruff check --select E9,F63,F7,F82`（9 个改动文件中的 Python 文件） | All checks passed（另用 F401、F841 试过四个测试文件，通过） |

未运行：科学回归、DUT、compiler、backend、SSH、Spectre、Harbor；未联网、未推送、未发布、未重生成 catalog。`traceability.py --check` 需要真实 Git archive，导出树没有 `.git`，未跑（主控重生成时会覆盖）。

## 7. 残余风险

- **[静态]** 选择步骤的"同一分片同一尝试有多份"依赖 `download-artifact` 对重名的行为（合并到同一目录，多份 `report.json` 会被"恰好 1 个"拒绝）；真实重名的 Actions 行为未在 CI 上验证。
- **[推断]** 新的 inline Python 步骤在 CI 上第一次运行才能验证 `GITHUB_RUN_ATTEMPT`、`GITHUB_STEP_SUMMARY` 与 `download-artifact` 目录布局（`runs/shards/<artifact名>/regression-evidence/report.json`）；布局取自 40602342818 的 coverage 日志。
- **[静态]** `FUZZ_NIGHTLY` 在测试和 workflow 各有一份，改日期须同改；不一致会让 `test_ci_uses_one_fixed_rust_toolchain` 与选择矩阵失败（变异检验已覆盖）。
- **[静态]** `test_ci_pins.py` 不再看 Rust；若有人给 Rust 另开不在 `.github/workflows` 与 `.github/actions` 的 CI，守卫也不看（与 PR6 原有边界相同）。
- 带来的代价：`test_discover_rust` 约 115 s，选择矩阵 6,329 项（PR6 r6 报告已提示的成本）。

## 8. 过程中的失败与重试（保留原名）

- 首次跑 `test_discover_rust` 时从仓库根而非 `scripts/tests` 启动，`git_fixture` 找不到：保留为 `logs/merged-discover-rust.attempt1-badcwd.out`，改在 `scripts/tests` 下重跑。
- 合并树与 bf2ec410 上的 `test_real_workflow_listing_block_keeps_build_failure_and_raw_artifacts`，在 `env -i PATH=/usr/bin:/bin` 下失败（子进程 `python3` 落到系统 3.9，没有 `tomllib`）；两处同样失败，与本次改动无关，最终测试把 lint-venv 放在 PATH 首位后通过（`logs/merged-discover-rust.out`、`logs/main-discover-rust.out` 保留）。
- 变异检验首跑 `symlink-and-file-allowed` 逃逸（见 §4）；`nightly_class_controls` 首跑只统计了修正后，改为同时统计 bf2ec410 守卫后重跑，首次输出为 `logs/nightly-class-controls.attempt1.stdout`；`pin_redgreen_merged` 首版缺少"PR273 原测试在 9ea5de9f 上"的列，补上后重跑，首次输出为 `results/pin-redgreen-merged.attempt1.json`。
- 导出用 `git archive` 约 3 分钟（超过 120 s 前台超时，转后台完成）。

## 9. 工作者与守卫

- 工作者：tclaude / claude-sonnet-5-5（实际型号），请求 effort=high，options：unknown；开始 2026-10-28T01:54:36Z，完成约 2026-10-28T02:56Z；未委派、未发布、未推送。
- 真实工作区守卫（`guard-before.txt` → `guard-after.txt`、`guard-after2.txt`；脚本 `scripts/guard.sh`）：

| 项目 | 开始 | 结束 |
| --- | --- | --- |
| HEAD | `refs/heads/codex/trusted-context-registration`（`168a9d7a…`） | 同 |
| index SHA256 | `a2e18b66fd9b3e29093343793d45781c11a717c05c35103d4e9b1da8eec87d71` | 同 |
| 共享 `config` SHA256 | `de2b08ef3ba66e96be8b70c87346ff4a96f905e1272934ddd86c218dba501ea8` | 同 |
| 20 个旧候选文件哈希 | 见 `guard-before.txt` | 逐项相同 |

（中途为核对状态在真实工作区执行过一次只读的 `git status --short`，之后重新记录守卫，仍与开始时相同。）
