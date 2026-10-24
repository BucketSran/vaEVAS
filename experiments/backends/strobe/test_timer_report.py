import math
import json
from pathlib import Path
import tempfile
import unittest
from timer_report import time_coverage, verify_timer_diagnostic


class NativeTimeCoverage(unittest.TestCase):
    def test_old_source_snapshot_without_shared_reader_is_explicit_dependency_drift(self):
        import shutil
        import timer_report as analyzer
        shared = 'experiments/backends/evidence/legacy_waveforms.py'
        paths = set(analyzer.run.source_files()) | {
            analyzer.ROOT/'evas/validation/strobe/timer_composition.py',
            analyzer.ROOT/'evas/validation/sample_edge_filter/contract.py',
        }
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = {}
            for path in paths:
                relative = str(path.relative_to(analyzer.ROOT))
                if relative == shared:
                    continue
                target = base/'repo'/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                source[relative] = analyzer.sha(target)
            (base/'SOURCE_MANIFEST.json').write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError, 'analysis dependency drift: ' + shared):
                analyzer.report(base)

    def test_diagnostic_preserves_every_control_except_timer_tolerance(self):
        from composition_run import freeze
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            freeze(base/'composition-inputs')
            freeze(base/'timer-diagnostic-inputs',True)
            verify_timer_diagnostic(base)
            work=base/'timer-diagnostic-inputs/runs/evas/STROBE-TIMER-IDT--both-TT10ps'
            for filename,mutate in [
                ('requested_settings.json',lambda d:d.update(reltol=1e-3)),
                ('request.json',lambda d:d['instances'][0]['parameters'].update(TT=1e-10)),
                ('condition.json',lambda d:d.update(initial_V=0.)),
            ]:
                with self.subTest(filename=filename):
                    p=work/filename;before=p.read_text();data=json.loads(before)
                    mutate(data);p.write_text(json.dumps(data))
                    with self.assertRaises(ValueError):verify_timer_diagnostic(base)
                    p.write_text(before)

    def test_backend_time_contracts_remain_distinct(self):
        rows=[{'time':math.nextafter(.3,math.inf)}]
        self.assertEqual(time_coverage([.3],rows,'spectre',1)['status'],'covered')
        self.assertEqual(time_coverage([.3],rows,'evas',1)['status'],'evidence_insufficient')
        self.assertEqual(rows,[{'time':math.nextafter(.3,math.inf)}])

    def test_rejects_missing_outside_allowance_and_reused_rows(self):
        for requested,rows in [([.3],[]),([.3],[{'time':.3+17*math.ulp(1.)}]),
                               ([.3,math.nextafter(.3,math.inf)],[{'time':.3}])]:
            with self.subTest(requested=requested,rows=rows):
                report=time_coverage(requested,rows,'spectre',1)
                self.assertEqual(report['status'],'evidence_insufficient')
                if len(requested)==1 and rows:
                    self.assertGreater(report['maximum_nearest_distance_s'],report['allowance_s'])


if __name__=='__main__':unittest.main()
