"""Check that calibration cannot silently lower the scientific target."""
import json
from pathlib import Path
import tempfile
import unittest
from sin_profile_probe import freeze
from primitives import assess
from precision_reference import pwl_exact
from primitives_run import verify


class FixedScientificTarget(unittest.TestCase):
    def test_looser_internal_controls_still_reject_external_q3_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs=Path(tmp)/'inputs';freeze(inputs);verify(inputs)
            plan=json.loads((inputs/'PLAN.json').read_text())
            self.assertEqual(len(plan),6)
            sources=set();requests=set()
            for item in plan:
                work=inputs/item['work']
                card=json.loads((work/'condition.json').read_text())
                settings=json.loads((work/'requested_settings.json').read_text())
                self.assertEqual(item['tier'],'Q3')
                self.assertEqual(settings['target_tier'],'Q3')
                sources.add((work/'dut.va').read_text())
                requests.add((work/'requested_times.json').read_text())
                # A trace biased by 1uV must fail even at the largest internal
                # absolute tolerance; the Q3 101nV gate stays independent.
                import math
                rows=[]
                for t in json.loads((work/'requested_times.json').read_text()):
                    u=float(pwl_exact(card['inputs']['u'],t))
                    rows.append({'time':t,'u':u,'y':math.sin(u)+1e-6})
                self.assertEqual(assess(card,rows,'Q3')['status'],'numerical_error')
            self.assertEqual(len(sources),1);self.assertEqual(len(requests),1)


if __name__=='__main__':unittest.main()
