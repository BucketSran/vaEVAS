"""Batch answers/order/errors must be independent of worker count."""
GUARDS = ["LIN", "NONLINEAR", "PERFORMANCE"]

import json
import os
import subprocess
import unittest

from evas import compile_sources
from test_affine import KERNEL, instance, model


def invoke(request, workers):
    return subprocess.run([str(KERNEL)], input=json.dumps(request), text=True,
                          capture_output=True, check=False,
                          env={**os.environ, 'EVAS_STATIC_THREADS': str(workers)})


class ParallelContracts(unittest.TestCase):
    def request(self, body='V(y,r)<+V(u,r)/2+0.125;'):
        program=compile_sources({'batch.va':model(body)},[instance()])
        return dict(program=program.to_dict(),driven=['u'],samples=[[i/16] for i in range(-64,65)])

    def test_invalid_thread_count_is_a_structured_configuration_error(self):
        for workers in [0,65,'bad','-1']:
            with self.subTest(workers=workers):
                result=invoke(self.request(),workers)
                self.assertEqual(result.returncode,2)
                self.assertEqual(json.loads(result.stderr)['kind'],'invalid_config')

    def test_affine_and_nonlinear_results_keep_order_and_bits(self):
        for body in ['V(y,r)<+V(u,r)/2+0.125;', 'V(y,r)<+V(u,r)-pow(V(y,r),3);']:
            request=self.request(body)
            serial=invoke(request,1)
            self.assertEqual(serial.returncode,0,serial.stderr)
            for workers in [2,4,64]:
                parallel=invoke(request,workers)
                self.assertEqual(parallel.returncode,0,parallel.stderr)
                self.assertEqual(parallel.stdout,serial.stdout)

    def test_multiple_failures_report_lowest_input_index(self):
        request=self.request()
        request['samples'][7]=[]
        request['samples'][80]=[]
        serial=invoke(request,1)
        self.assertEqual(json.loads(serial.stderr)['sample'],7)
        for workers in [2,4,64]:
            result=invoke(request,workers)
            self.assertEqual(result.returncode,2)
            self.assertEqual(result.stderr,serial.stderr)

    def test_transient_remains_serial(self):
        request=self.request()
        request['samples']=[]
        request['transient']=dict(pwl=[[[0,0],[1,1]]],output_times=[0,.5,1],stop=1,max_step=.125)
        one=invoke(request,1)
        many=invoke(request,4)
        self.assertEqual(one.returncode,0,one.stderr)
        self.assertEqual(many.stdout,one.stdout)


if __name__=='__main__': unittest.main()
