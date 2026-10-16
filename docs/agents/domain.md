# Domain documentation

Use one shared vocabulary for benchmark and EVAS, with contracts owned by each
component. Read the relevant existing documents rather than creating another tree
to match a shared skill's default layout.

- [GLOSSARY.md](../../GLOSSARY.md) defines common terms.
- [Project goals](../../README.md#研究验收与论文实验) define research acceptance.
- [Benchmark](../../benchmark/README.md) owns task scope, grading and reproduction requirements.
- [EVAS](../../evas/README.md) and its [handbook](../../evas/docs/README.md) own simulator behavior and mathematics.
- [EVAS architecture decisions](../../evas/docs/development/DECISIONS.md) explain existing product and compatibility choices.
- [CONTRIBUTING](../../CONTRIBUTING.md#find-the-relevant-rules) owns scope, review and delivery rules and routes to the relevant test, workspace and evidence procedures.

Use glossary terms in task descriptions, technical explanations and tests. When
`domain-modeling` resolves a new term, update the existing glossary. Keep behavior
requirements in component contracts and execution history in the existing Issue/PR.

Flag conflicts with an existing decision and identify the evidence for reopening
it. Record a new decision only when the trade-off warrants it, in the owning
component's maintained document. A missing `docs/adr/` directory is not a setup gap;
do not copy the EVAS decision register there.

## Prior art

Before an EVAS fix, use the bounded search in [evas-develop](../../.agents/skills/evas-develop/SKILL.md#select-and-research-the-next-fix).
The following are candidate routes, not approved dependencies or proof of EVAS compatibility.
Inspect only the mechanism relevant to the current blocker. Record the exact version, section or
commit used and whether it supplies code, an algorithm, a state-management rule or a test case.
Check related papers from the project references or a targeted primary-source search; record
no useful result or lack of relevance explicitly instead of producing an unrelated literature survey.

| Question | Starting point |
| --- | --- |
| Language semantics | [Accellera Verilog-AMS standards](https://www.accellera.org/downloads/standards/v-ams); name the contract's LRM version and section. Standard upgrades are separate decisions. |
| Earlier EVAS behavior | Local `vaEVAS/legacy/EVAS`, fixed v0.8.7 commit `6cb6fa7a7dac70fc0d4120126d8cf74258e6637b`; use `git show`, not the dirty legacy checkout. This is historical implementation evidence, not the standard. |
| Compiler, binding and expressions | [OpenVAF Reloaded](https://github.com/OpenVAF/OpenVAF-Reloaded); inspect relevant compiler code and tests. |
| cross, timer, transition and fixes | [Gnucap modelgen-verilog NEWS](https://github.com/gnucap/gnucap-modelgen-verilog/blob/develop/NEWS); follow the relevant change to code and regression tests. |
| Shared expressions and repeated computation | [heyoka computational graphs](https://bluescarni.github.io/heyoka.py/notebooks/ex_system_internals.html). |
| Discontinuities and integration-history restart | [SUNDIALS usage notes](https://computing.llnl.gov/projects/sundials/usage-notes), then the relevant solver's current manual. |
| Error envelopes and reachability | [Flow*](https://github.com/chenxin415/flowstar), [JuliaReach Taylor methods](https://juliareach.github.io/ReachabilityAnalysis.jl/stable/tutorials/taylor_methods/introduction/). |
| Circuit sparse solving | [SuiteSparse KLU](https://github.com/DrTimothyAldenDavis/SuiteSparse/tree/dev/KLU) and its cited Algorithm 907 paper. |

For integration, check license, build/FFI cost, maintained API, state ownership and numerical/error
semantics. Otherwise reuse the algorithm or tests under their applicable terms. A mature point
solver is not by itself an interval enclosure; backend agreement is not a substitute for the
independent acceptance contract. New relevant sources can extend the search without enlarging
its time budget or this table into a mandatory reading list.
