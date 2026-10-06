# Domain documentation

Use one shared vocabulary for benchmark and EVAS, with contracts owned by each
component. Read the relevant existing documents rather than creating another tree
to match a shared skill's default layout.

- [GLOSSARY.md](../../GLOSSARY.md) defines common terms.
- [Project goals](../../README.md#研究验收与论文实验) define research acceptance.
- [Benchmark](../../benchmark/README.md#目标与边界) owns task scope, grading and reproduction requirements.
- [EVAS](../../evas/README.md) and its [handbook](../../evas/docs/README.md) own simulator behavior and mathematics.
- [EVAS architecture decisions](../../evas/docs/DECISIONS.md) explain existing product and compatibility choices.
- [CONTRIBUTING](../../CONTRIBUTING.md#find-the-relevant-rules) owns scope, review and delivery rules and routes to the relevant test, workspace and evidence procedures.

Use glossary terms in task descriptions, technical explanations and tests. When
`domain-modeling` resolves a new term, update the existing glossary. Keep behavior
requirements in component contracts and execution history in the existing Issue/PR.

Flag conflicts with an existing decision and identify the evidence for reopening
it. Record a new decision only when the trade-off warrants it, in the owning
component's maintained document. A missing `docs/adr/` directory is not a setup gap;
do not copy the EVAS decision register there.
