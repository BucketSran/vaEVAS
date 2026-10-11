"""Public examples cannot silently become the terminal evaluator instances."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).parent
SLUGS=('hysteresis','comparator-delay','duty-cycle','sampled-rms','online-gain','clock-frequency','offset-search','time-protocol','gain-settling')

class PublicTerminalSeparation(unittest.TestCase):
    def test_delivered_agent_assets_exclude_terminal_instances(self):
        for slug in SLUGS:
            with self.subTest(task=slug):
                task=ROOT/'benchmark/tasks'/('v2-test-'+slug)
                public=json.loads((task/'environment/public/cases.json').read_text())
                hidden=json.loads((task/'tests/cases.json').read_text())
                self.assertEqual(len(public),3)
                self.assertEqual(len(hidden),3)
                self.assertTrue(set(c['name'] for c in public).isdisjoint(c['name'] for c in hidden))
                environment='\n'.join(p.read_text(errors='replace') for p in (task/'environment').rglob('*') if p.is_file())
                for case in hidden:
                    self.assertNotIn(case['netlist'],environment)
                    self.assertNotIn(case['name'],environment)
                    # Renaming identical stimuli would retain the leaked experiment.
                    self.assertNotIn(case['netlist'],[c['netlist'] for c in public])
                for case in public+hidden:
                    self.assertIn('ahdl_include "dut.va"',case['netlist'])
                    for name,text in case.get('support',{}).items():
                        self.assertIn('ahdl_include "'+name+'"',case['netlist'])
                        self.assertTrue((task/'environment/public/dut'/name).is_file())
                instruction=(task/'instruction.md').read_text()
                self.assertIn('公开自测与终评范围',instruction)
                self.assertNotIn('正式条件和数值容差公开于 public/cases.json',instruction)
                self.assertIn('COPY public/ /work/public/',(task/'environment/Dockerfile').read_text())
                self.assertNotIn('COPY tests', (task/'environment/Dockerfile').read_text())

    def test_missing_explicit_public_cases_fails_before_writing(self):
        spec=importlib.util.spec_from_file_location('owned_builder',HERE/'build_tasks.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.put=lambda *args: self.fail('missing public_cases must fail before writes')
        for slug in SLUGS+('por-sequence',):
            with self.subTest(task=slug),self.assertRaisesRegex(ValueError,'public_cases'):
                module.package(slug,'source','title','contract','ref','alt',{},[],{})

if __name__=='__main__':unittest.main()
