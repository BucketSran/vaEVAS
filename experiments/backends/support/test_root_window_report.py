"""Prevent mixed lanes, incomplete denominators and self-attested producers."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import root_window_report as report
from root_window_run import observation_deck


class EvidenceIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.frozen=self.base/'inputs';self.frozen.mkdir()
        self.lane=self.base/'lane';self.lane.mkdir()
        self.plan=[{'backend':'evas','label':'SH-X-RAMP--Q3','work':'runs/evas/SH-X-RAMP--Q3',
                    'tier':'Q3','condition':'SH-X-RAMP','profile':'deep','callback_trace':False}]
        self.write(self.frozen/'PLAN.json',self.plan)
        self.write(self.lane/'EXECUTION.json',self.plan)

    @staticmethod
    def write(path,value):path.write_text(json.dumps(value))

    def test_plan_keeps_failed_and_missing_slots(self):
        records=[{**self.plan[0],'status':'not_run'}]
        self.write(self.lane/'EXECUTION.json',records)
        self.assertEqual(report.fixed_executions(self.frozen,self.lane,'evas'),records)
        self.write(self.lane/'EXECUTION.json',[])
        with self.assertRaises(ValueError):report.fixed_executions(self.frozen,self.lane,'evas')

    def test_mixed_lane_or_profile_rejected(self):
        for key,value in [('callback_trace',True),('work','runs/spectre/SH-X-RAMP--Q3'),('profile','base')]:
            self.write(self.lane/'EXECUTION.json',[{**self.plan[0],key:value}])
            with self.assertRaises(ValueError):report.fixed_executions(self.frozen,self.lane,'evas')

    def test_escape_even_if_both_plan_and_execution_agree(self):
        for key,value in [('label','../../other-lane'),('work','../trace/runs/spectre/card')]:
            rows=[{**self.plan[0],key:value}]
            self.write(self.frozen/'PLAN.json',rows);self.write(self.lane/'EXECUTION.json',rows)
            with self.assertRaises(ValueError):report.fixed_executions(self.frozen,self.lane,'evas')

    def test_output_inventory_must_be_complete(self):
        file=self.lane/'EXECUTION.json'
        manifest={file.name:{'bytes':file.stat().st_size,'sha256':report.sha(file)}}
        self.write(self.lane/'FILE_MANIFEST.json',manifest);report.verify_lane(self.lane)
        (self.lane/'unlisted-waveform.csv').write_text('actual output')
        with self.assertRaises(ValueError):report.verify_lane(self.lane)

    def test_waveform_cannot_borrow_another_lane(self):
        for path in ('../../trace-spectre/psf/tran.tran.tran','/tmp/other/waveform.csv'):
            records=[{**self.plan[0],'status':'waveform_available','waveform':path}]
            self.write(self.lane/'EXECUTION.json',records)
            with self.assertRaises(ValueError):report.fixed_executions(self.frozen,self.lane,'evas')

    def test_execution_snapshot_is_independent_of_analysis_edits(self):
        snapshot=self.base/'snapshot';snapshot.mkdir();source=snapshot/'source.py';source.write_text('old execution')
        identities={'source.py':report.sha(source)}
        self.write(self.frozen/'SOURCE_IDENTITY.json',identities)
        self.write(self.frozen/'MANIFEST.json',{'SOURCE_IDENTITY.json':report.sha(self.frozen/'SOURCE_IDENTITY.json')})
        report.verify_frozen(self.frozen,snapshot)
        source.write_text('changed execution')
        with self.assertRaises(ValueError):report.verify_frozen(self.frozen,snapshot)

    def test_empty_or_incomplete_production_inventory_rejected(self):
        source=self.base/'evas/src/test.py';source.parent.mkdir(parents=True);source.write_text('production')
        manifest=self.base/'previous-manifest.json';self.write(manifest,{'evas/src/test.py':report.sha(source)})
        build=self.base/'BUILD.json';self.write(build,{'returncode':0,'stage':{'status':'completed'},
            'source_revision':'previous','source_manifest_sha256':report.sha(manifest),'kernel_sha256':'kernel'})
        identity={'reuse_verified':True,'kernel_sha256':'kernel','previous_build_record_sha256':report.sha(build),
            'previous_source_manifest_sha256':report.sha(manifest),'previous_scientific_source_revision':'previous',
            'production_source_sha256':{'evas/src/test.py':report.sha(source)}}
        self.write(self.base/'SOURCE_PROVENANCE.json',identity)
        with patch.object(report,'ROOT',self.base),patch.object(report.subprocess,'check_output',return_value='evas/src/test.py\n'):
            self.assertEqual(report.producer(self.base,{'kernel_sha256':'kernel'},build,manifest)['status'],'qualified')
            identity['production_source_sha256']={};self.write(self.base/'SOURCE_PROVENANCE.json',identity)
            with self.assertRaises(ValueError):report.producer(self.base,{'kernel_sha256':'kernel'},build,manifest)
            identity['production_source_sha256']={'evas/src/test.py':report.sha(source)}
            self.write(self.base/'SOURCE_PROVENANCE.json',identity)
            build.write_text('{}')
            with self.assertRaises(ValueError):report.producer(self.base,{'kernel_sha256':'kernel'},build,manifest)

    def test_spectre_preflight_identity_rejected_if_wrong(self):
        log=self.lane/'version.log';log.write_text('observed version')
        tool={'binary_sha256':report.SPECTRE_CALIBRATED_BINARY_SHA256,
              'version':'sub-version  '+report.SPECTRE_CALIBRATED_VERSION,
              'probe':{'returncode':0,'timeout':False,'status':'completed','log':'version.log','log_sha256':report.sha(log)}}
        self.assertEqual(report.spectre_producer(self.lane,tool)['status'],'qualified')
        tool['binary_sha256']='wrong'
        with self.assertRaises(ValueError):report.spectre_producer(self.lane,tool)

    def test_observation_markers_cannot_silently_disappear(self):
        text='simulatorOptions options precision="%.17g"\ntran tran stop=1\n'
        output=observation_deck(text)
        self.assertIn('digits=17 notation=sci',output);self.assertIn('transres=1e-20',output)
        for bad in (text.replace(' precision="%.17g"',''),text+text):
            with self.assertRaises(ValueError):observation_deck(bad)


if __name__=='__main__':unittest.main()
