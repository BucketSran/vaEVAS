import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from registry import load,reference,digest
from test_asset_catalog import make_data,write
from source_reader import historical_row

class HistoryBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.objects=make_data(self.root);self.method=self.objects[3]
        self.row={'id':self.method['runtime_id'],'verdict':'no_defect_found','source_file':'evas/tests/test_demo.py',
                  'source_method_sha256':'b'*64,'source_module_sha256':'a'*64}
        self.doc={'summary':{'scope':{'method_count':2}},'rows':[self.row,dict(self.row,id='test_other.Case.test_other',verdict='test_defect')]}
        self.source=dict(self.objects[0],id='source:audit',locator={'kind':'embedded','value':self.doc},sha256=digest(self.doc))
        self.history={'schema_version':1,'id':'history:one','version':'1','kind':'historical-audit-record','status':'active',
          'source':reference(self.source),'row_pointer':'/rows/0','scope_pointer':'/summary/scope','original_row_sha256':digest(self.row),
          'scope_sha256':digest(self.doc['summary']['scope']),'alignment':{'status':'matched'},'identity_binding':'bound',
          'history_protocol':'evas-method-audit-3257-v1','method':reference(self.method),'original_verdict':'no_defect_found',
          'source_method_sha256':'b'*64,'source_module_sha256':'a'*64,'dependencies':[reference(self.source)]}
        self.data=json.loads((self.root/'registry.json').read_text());self.data['object_parts'].append('history.json')
        self.data['current'].update({self.source['id']:'1',self.history['id']:'1'})

    def catalog(self):
        self.history['dependencies']=[reference(self.source)]
        write(self.root,'sources.json',{'schema_version':1,'kind':'sources','objects':[self.objects[0],self.source]})
        write(self.root,'history.json',{'schema_version':1,'kind':'history','objects':[self.history]})
        write(self.root,'registry.json',self.data)
        return load(self.root,root=self.root).catalog()

    def test_wrong_row_pointer_and_rehashed_row_cannot_borrow_another_method_identity(self):
        self.history.update(row_pointer='/rows/1',original_row_sha256=digest(self.doc['rows'][1]))
        for status in ('matched','pending'):
            self.history['alignment']['status']=status
            with self.assertRaises(ValueError):self.catalog().read_history(self.history)

    def test_copied_verdict_and_hashes_must_equal_actual_raw_fields(self):
        c=self.catalog();self.assertEqual(c.read_history(self.history),self.row)
        for field in ('original_verdict','source_method_sha256','source_module_sha256'):
            h=copy.deepcopy(self.history);h[field]='invented'
            with self.assertRaises(ValueError):c.read_history(h)

    def test_pending_raw_hash_mismatch_is_preserved_but_cannot_be_matched(self):
        self.doc['rows'][0]['source_method_sha256']='c'*64
        self.source.update(locator={'kind':'embedded','value':self.doc},sha256=digest(self.doc))
        self.history.update(source=reference(self.source),original_row_sha256=digest(self.doc['rows'][0]),source_method_sha256='c'*64)
        self.history['alignment']['status']='pending';c=self.catalog();self.assertEqual(c.read_history(self.history)['source_method_sha256'],'c'*64)
        h=copy.deepcopy(self.history);h['alignment']['status']='matched'
        with self.assertRaises(ValueError):c.read_history(h)

    def test_pointer_rejects_negative_aliases_bad_escapes_and_array_bounds(self):
        source=dict(self.source,locator={'kind':'embedded','value':{'rows':[{'id':'A'}],'~1':'literal','/':'slash'}},sha256=digest({'rows':[{'id':'A'}],'~1':'literal','/':'slash'}))
        for pointer in ('/rows/-1','/rows/00','/rows/+0','/rows/1','/rows/-','/rows/0/id/~2','/~2','/~','rows/0','#/rows/0'):
            with self.assertRaises(ValueError):historical_row(source,pointer,digest({'id':'A'}))
        self.assertEqual(historical_row(source,'/~01',digest('literal')),'literal')
        self.assertEqual(historical_row(source,'/~1',digest('slash')),'slash')

    def test_immutable_document_cache_and_returned_row_copy_do_not_hide_source_mutation(self):
        c=self.catalog();self.assertEqual(c.read_history(self.history),self.row)
        # Each returned row is detached from the immutable cached document.
        changed=c.read_history(self.history);changed['id']='polluted'
        self.assertEqual(c.read_history(self.history)['id'],self.row['id'])
        c.bound(self.history['source'])['locator']['value']['rows'][0]['id']='source-mutated'
        with self.assertRaises(ValueError):c.read_history(self.history)

    def test_repository_relative_source_is_rehashed_after_every_read(self):
        path=self.root/'audit.json';path.write_text(json.dumps(self.doc,sort_keys=True,separators=(',',':')))
        self.source.update(locator={'kind':'repository-relative','path':'audit.json'},sha256=__import__('hashlib').sha256(path.read_bytes()).hexdigest())
        self.history['source']=reference(self.source);c=self.catalog();c.read_history(self.history)
        path.write_text('{}')
        with self.assertRaises(ValueError):c.read_history(self.history)

    def finding(self,protocol,row,document):
        self.doc=document;self.source.update(locator={'kind':'embedded','value':document},sha256=digest(document))
        pointer='/confirmed/0' if protocol=='evas-passing-oracles-v1' else '/findings/0'
        scope_pointer='/scope' if protocol=='evas-passing-oracles-v1' else ''
        scope=document['scope'] if scope_pointer else document
        self.history.update(kind='historical-finding',history_protocol=protocol,source=reference(self.source),
            row_pointer=pointer,scope_pointer=scope_pointer,scope_sha256=digest(scope),original_row_sha256=digest(row),alignment={'status':'pending'})
        for field in ('original_verdict','source_method_sha256','source_module_sha256'):self.history.pop(field,None)
        return self.catalog()

    def test_oracle_finding_eligibility_binds_exact_subject_and_preserves_module_mismatch_pending(self):
        row={'id':'PO-F01','test_ids':[self.method['runtime_id']],
            'eligibility':[{'id':self.method['runtime_id'],'source_file':'evas/tests/test_demo.py','current_module_sha256':'c'*64,'previous_audit':'no_defect_found'}]}
        c=self.finding('evas-passing-oracles-v1',row,{'scope':{'selection':'fixture'},'confirmed':[row]})
        h=dict(self.history,source_module_sha256='c'*64,original_verdict='no_defect_found')
        self.assertEqual(c.read_history(h)['id'],'PO-F01')
        with self.assertRaises(ValueError):c.read_history(dict(h,source_module_sha256='a'*64))
        wrong=copy.deepcopy(self.doc);wrong['confirmed'][0]['test_ids']=['other.Case.test_other']
        self.source.update(locator={'kind':'embedded','value':wrong},sha256=digest(wrong));self.history.update(source=reference(self.source),original_row_sha256=digest(wrong['confirmed'][0]))
        with self.assertRaises(ValueError):self.catalog().read_history(self.history)

    def test_negative_finding_never_uses_consumer_strings_as_subject_or_invents_sha(self):
        row={'id':'PN-F01','method_id':self.method['runtime_id'],'file':'evas/tests/test_demo.py','status':'confirmed'}
        c=self.finding('evas-passing-negative-v1',row,{'findings':[row],'executed_methods':[{'id':self.method['runtime_id']}]})
        self.assertEqual(c.read_history(self.history)['id'],'PN-F01')
        with self.assertRaises(ValueError):c.read_history(dict(self.history,source_module_sha256='a'*64))
        other=dict(row,method_id='other.Case.test_other',consumer_check=self.method['runtime_id'])
        c=self.finding('evas-passing-negative-v1',other,{'findings':[other]})
        with self.assertRaises(ValueError):c.read_history(self.history)

    def test_raw_finding_module_match_cannot_be_upgraded_to_method_match(self):
        row={'id':'RAW-PASS-01','methods':[self.method['runtime_id']]}
        doc={'findings':[row],'reviewed_methods':[{'id':self.method['runtime_id'],'file':'evas/tests/test_demo.py'}],
            'source_sha256':{'evas/tests/test_demo.py':'a'*64}}
        c=self.finding('evas-passing-raw-v1',row,doc)
        self.assertEqual(c.read_history(dict(self.history,source_module_sha256='a'*64))['id'],'RAW-PASS-01')
        for h in (dict(self.history,alignment={'status':'matched'}),dict(self.history,source_method_sha256='b'*64)):
            with self.assertRaises(ValueError):c.read_history(h)

    def test_immutable_cache_reads_authenticated_document_once_but_rechecks_references(self):
        c=self.catalog();module=c._history_module('source_reader')
        c._history_reader=module.DocumentReader(root=self.root,repositories={})
        with patch.object(module,'read_source',wraps=module.read_source) as read:
            c.read_history(self.history);c.read_history(self.history)
            self.assertEqual(read.call_count,1)
        c.registry.objects[(self.method['id'],self.method['version'])]['runtime_id']='changed'
        with self.assertRaises(ValueError):c.read_history(self.history)
