"""Source RN oracle calibration and the exact-root/source-band distinction."""
GUARDS = ['LANG', 'EVENT-ORDER', 'EVENT-CONDITIONS', 'CROSS', 'COMPOSE']
import copy
import json
import math
import unittest
from fractions import Fraction as Q
from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model
from floor_rn_contract import Expected, check_physical_node, divide_floor, floor_contract, label, mul_floor, rn

UP = [[0,0],[1,1]]
DOWN = [[0,1],[1,0]]
ROOT_BODY = '@(initial_step)begin q=0;p=0;end @(cross(V(u,r)-0.5,1))begin q=floor(2*V(w,r));if(q<1)p=2;else p=3;end V(y,r)<+p;'

def root_source():
    return model(ROOT_BODY,'real q,p;',ports='u,w,y,r',directions='input u,w;output y;inout r;')

def root_program():
    return compile_sources({'root_floor_rn.va':root_source()},[instance(connections=dict(u='u',w='w',y='y',r='0'))])

def root_request():
    return dict(program=root_program().to_dict(),driven=['u','w'],transient=dict(pwl=[UP,DOWN],output_times=[0,.25,.75,1],stop=1,max_step=2))

def synthetic_response(expected):
    """Checker calibration input only; never passed off as a native result."""
    req=expected.request
    events=[]
    for root,index,before,after in expected.trace:
        event=expected.wire['events'][index]
        record=dict(time=float(root),event=index,origin=label(event),kind=event['trigger']['kind'],before=before,after=after)
        rounded=Q(float(root))
        lo=math.nextafter(float(root),-math.inf) if rounded>root else float(root)
        hi=math.nextafter(float(root),math.inf) if rounded<root else float(root)
        if lo!=hi:record['observation_time_bounds']=[lo,hi]
        if record['kind']=='cross':record['guard_value']=0
        events.append(record)
    states=[];solutions=[];bounds=[]
    for time in req['transient']['output_times']:
        held,values=expected.values_at(Q(time))
        states.append([float(held[n]) for n in expected.names])
        row=[float(values[n]) for n in expected.wire['nodes']]
        assert all(Q(v)==values[n] for n,v in zip(expected.wire['nodes'],row)), 'calibration fixture is dyadic'
        solutions.append(dict(voltages=row,max_residual_v=0,max_residual_ratio=0))
        intervals=[]
        for name,value in zip(expected.wire['nodes'],row):
            error=expected.errors.get(name,Q(0));lo=values[name]-error;hi=values[name]+error
            a,b=float(lo),float(hi)
            if Q(a)>lo:a=math.nextafter(a,-math.inf)
            if Q(b)<hi:b=math.nextafter(b,math.inf)
            intervals.append([a,b])
        bounds.append(intervals)
    return dict(engine="INDEPENDENT_SOURCE_ORACLE_NOT_NATIVE",schema_version=33,nodes=expected.wire['nodes'],solutions=solutions,
                transient=dict(times=req['transient']['output_times'],states=states,state_names=[f"{expected.owner}:{n}" for n in expected.names],events=events,accepted_steps=0,discarded_trials=0),
                observation_evidence=dict(schema_version=1,nodes=expected.wire['nodes'],voltage_bounds_V=bounds,sample_origins=['unknown']*len(states),effective_controls=dict(absolute_V=req.get('tolerances',{}).get('absolute',1e-9),relative=req.get('tolerances',{}).get('relative',1e-6),stop_s=req['transient']['stop'],max_step_s=req['transient']['max_step'],max_step_applied=True)))

class FloorRNOracle(unittest.TestCase):
    def test_each_operation_rounds_before_floor_and_negative_bins(self):
        self.assertEqual([divide_floor(v) for v in [.03,.09,.15,.87,-.03,-.09]],[1,1,3,15,0,-1])
        self.assertEqual(mul_floor(-10.,.1),-1)
        self.assertEqual(math.floor(Q(.1)*-10),-2)  # Preserved old mathematical tree, a different contract.
        self.assertEqual(mul_floor(-.125,8),-1)
        self.assertEqual(mul_floor(math.nextafter(-.125,-math.inf),8),-2)

    def test_exact_half_cell_and_adjacent_cells(self):
        lower=Q(math.nextafter(.5,-math.inf));center=Q(.5)
        midpoint=(lower+center)/2
        self.assertEqual(rn(midpoint),center)  # ties-even significand
        self.assertEqual(rn(midpoint-Q(1,2**110)),lower)
        self.assertEqual(mul_floor(midpoint,2),1)
        self.assertEqual(mul_floor(midpoint-Q(1,2**110),2),0)
        self.assertEqual(mul_floor(math.nextafter(.5,math.inf),2),1)

    def test_synthetic_checker_rejects_all_record_phase_and_box_mutations(self):
        expected=Expected('right',root_source(),root_request());good=synthetic_response(expected)
        expected.check(good)
        for mutation in ['missing_initial','initial_guard','initial_fired','initial_bounds','initial_query_state','event_phase','broad_wrong_phase','wrong_guard','root_bounds','runtime_state','physical_box','initial_display']:
            bad=copy.deepcopy(good)
            if mutation=='missing_initial':bad['transient']['events'].pop(0)
            elif mutation=='initial_guard':bad['transient']['events'][0]['guard_value']=0
            elif mutation=='initial_fired':bad['transient']['events'][0]['fired_triggers']=[{'kind':'initial_step'}]
            elif mutation=='initial_bounds':bad['transient']['events'][0]['observation_time_bounds']=[0,1e-9]
            elif mutation=='initial_query_state':bad['transient']['states'][0][0]=1
            elif mutation=='event_phase':bad['transient']['events'][1]['time']=.25
            elif mutation=='broad_wrong_phase':
                bad['transient']['events'][1]['time']=.25;bad['transient']['events'][1]['observation_time_bounds']=[0,1]
            elif mutation=='wrong_guard':bad['transient']['events'][1]['guard_value']=1
            elif mutation=='root_bounds':bad['transient']['events'][1]['observation_time_bounds']=[.5,math.nextafter(.5,-math.inf)]
            elif mutation=='runtime_state':bad['transient']['events'][1]['after']=[0,2]
            elif mutation=='physical_box':bad['observation_evidence']['voltage_bounds_V'][-1][good['nodes'].index('y')]=[2,2]
            else:bad['transient']['events'][0]['display_records']=[{'text':'unexpected'}]
            with self.subTest(mutation=mutation),self.assertRaises(AssertionError):expected.check(bad)

    def test_true_band_is_not_a_nominal_root_point(self):
        request=root_request();request['transient']['pwl_errors_v']=[0,2**-54]
        expected=Expected('right',root_source(),request)
        self.assertIn('true input band',expected.fault)
        self.assertEqual(mul_floor(Q(1,2)-Q(1,2**54),2),0)
        self.assertEqual(mul_floor(Q(1,2)+Q(1,2**54),2),1)
        point=Expected('right',root_source(),root_request())
        with self.assertRaises(AssertionError):expected.check(synthetic_response(point))
        # A genuine non-point input band wholly inside one source rounding
        # cell is a positive mathematical control; retain its full physical
        # input enclosure rather than replacing that band by the nominal.
        same_cell=root_request();same_cell['transient']['pwl_errors_v']=[0,2**-56]
        certified=Expected('right',root_source(),same_cell)
        self.assertIsNone(certified.fault)
        response=synthetic_response(certified);certified.check(response)
        bad=copy.deepcopy(response);j=bad['nodes'].index('w')
        bad['observation_evidence']['voltage_bounds_V'][-1][j]=[0,0]
        with self.assertRaises(AssertionError):certified.check(bad)

    def test_first_store_overflow_precedes_clamp_in_oracle(self):
        source=model('@(initial_step)q=0;@(timer(0.25))begin q=floor(8*V(u,r));if(q<0)q=0;if(q>7)q=7;end V(y,r)<+q;','integer q;')
        wire=compile_sources({'floor_store.va':source},[instance()]).to_dict()
        request=dict(program=wire,driven=['u'],transient=dict(pwl=[[[0,268435456.],[1,268435456.]]],output_times=[0,.5,1],stop=1,max_step=.125))
        expected=Expected('native',source,request)
        self.assertIn('first executed typed store',expected.fault)

    def test_dead_arms_keep_name_node_function_and_type_checks(self):
        for expression in ['missing','V(missing)','missingfn(1.0)','floor(V(u,r))&1','0*V(y,r)+V(u,r)']:
            if expression.startswith('0*'):expression='floor('+expression+')'
            text=model('@(initial_step)q=0;@(timer(0.25))begin if(0>1)q='+expression+';else q=1;end V(y,r)<+q;','integer q;')
            with self.subTest(expression=expression),self.assertRaises(CompileError):compile_sources({'dead_floor_static.va':text},[instance()])

    def test_nonrepresentable_source_root_differs_from_ceil_phase(self):
        root=Q(1,3)
        ceil=math.nextafter(float(root),math.inf)
        self.assertTrue(Q(float(root))<root<Q(ceil))
        self.assertEqual(mul_floor(30*root,-.1),-1)
        self.assertEqual(mul_floor(30*Q(ceil),-.1),-2)

    def test_actual_nonrepresentable_root_is_not_its_ceil_phase(self):
        source=model('@(initial_step)q=0;@(cross(3*V(u,r)-1,1))q=floor(-0.1*V(w,r));V(y,r)<+q;','integer q;',ports='u,w,y,r',directions='input u,w;output y;inout r;')
        with floor_contract(self,'phase'):
            program=compile_sources({'floor_root_phase.va':source},[instance(connections=dict(u='u',w='w',y='y',r='0'))])
            result=transient(program,dict(u=UP,w=[[0,0],[1,30]]),[0,.25,.75,1],stop=1,max_step=2,kernel=KERNEL)
            self.assertEqual([e['after'] for e in result['transient']['events']],[[0],[-1]])

    def test_native_points_and_boxes_are_independent_obligations(self):
        expected=Expected('right',root_source(),root_request());good=synthetic_response(expected)
        for mutation in ['output_outside_box','input_outside_box','wide_box_wrong_output','wide_box_wrong_input','nan_output','infinite_input','reversed_box','nan_box','bool_nominal','infinite_box']:
            bad=copy.deepcopy(good);y=bad['nodes'].index('y');w=bad['nodes'].index('w')
            if mutation=='output_outside_box':bad['solutions'][-1]['voltages'][y]=99
            elif mutation=='input_outside_box':bad['solutions'][-1]['voltages'][w]=99
            elif mutation=='wide_box_wrong_output':
                bad['solutions'][-1]['voltages'][y]=4;bad['observation_evidence']['voltage_bounds_V'][-1][y]=[0,100]
            elif mutation=='wide_box_wrong_input':
                bad['solutions'][-1]['voltages'][w]=.25;bad['observation_evidence']['voltage_bounds_V'][-1][w]=[-1,1]
            elif mutation=='nan_output':bad['solutions'][-1]['voltages'][y]=math.nan
            elif mutation=='infinite_input':bad['solutions'][-1]['voltages'][w]=math.inf
            elif mutation=='reversed_box':bad['observation_evidence']['voltage_bounds_V'][-1][w]=[1,-1]
            elif mutation=='nan_box':bad['observation_evidence']['voltage_bounds_V'][-1][y]=[math.nan,math.nan]
            elif mutation=='bool_nominal':bad['solutions'][-1]['voltages'][y]=True
            else:bad['observation_evidence']['voltage_bounds_V'][-1][y]=[-math.inf,math.inf]
            with self.subTest(mutation=mutation),self.assertRaises(AssertionError):expected.check(bad)
        # A continuous rational point need not itself be a binary64. Use only
        # the original declared accuracy for that case; never a DUT-reported
        # wider allowance or a new test tolerance.
        truth=Q(1,3);low=float(truth);high=math.nextafter(low,math.inf)
        check_physical_node(low,[low,high],truth,Q(0),dict(absolute=1e-9,relative=0))
        with self.assertRaises(AssertionError):check_physical_node(low+1e-8,[0,.5],truth,Q(0),dict(absolute=1e-9,relative=0))

    def test_actual_dead_raw_owner_and_reference_rejected_before_admission(self):
        from evas.runtime import _invoke
        wire=root_program().to_dict()
        wire=json.loads(json.dumps(wire))
        event=next(e for e in wire['events'] if e['trigger']['kind']=='cross')
        original=copy.deepcopy(event['body'])
        event['body']=[dict(kind='if',relation='gt',left=dict(op='affine',constant=0,terms=[]),right=dict(op='affine',constant=1,terms=[]),then_body=original,else_body=[],origin=event['origin'])]
        def find(node, op):
            if isinstance(node,dict):
                if node.get('op')==op:return node
                for value in node.values():
                    answer=find(value,op)
                    if answer is not None:return answer
            elif isinstance(node,list):
                for value in node:
                    answer=find(value,op)
                    if answer is not None:return answer
            return None
        for defect in ['foreign_owner','invalid_node']:
            bad=copy.deepcopy(wire);floor=find(bad['events'],'event_math');assert floor['function']=='floor'
            if defect=='foreign_owner':floor['origin']['instance']='foreign'
            else:
                sample=find(floor,'real_boundary');affine=find(sample,'affine');assert affine['terms'];affine['terms'][0]['node']=999
            request=dict(program=bad,driven=['u','w'],samples=[],transient=dict(pwl=[UP,DOWN],output_times=[0,.25,.75,1],stop=1,max_step=2))
            with self.subTest(defect=defect),self.assertRaises(KernelError) as rejected:_invoke(request,KERNEL,20)
            self.assertEqual(rejected.exception.detail['kind'],'invalid_ir')

    def test_actual_exact_root_sample(self):
        # A unique source root is 1/2; w=1-t gives the exact same mathematical
        # value 1/2 there, so q=floor(2*w)=1 at tau. A falling w enters bin 0
        # just after tau, where q<1 holds: the body reads tau+ and refuses rather
        # than guess (events.md cross-right-limit).
        with floor_contract(self,'right'):
            program=root_program()
            with self.assertRaisesRegex(KernelError,'event_condition'):
                transient(program,dict(u=UP,w=DOWN),[0,.25,.75,1],stop=1,max_step=2,kernel=KERNEL)

    def test_actual_true_cross_cell_band_requires_a_numerical_refusal(self):
        with floor_contract(self,'right'):
            program=root_program()
            with self.assertRaises(KernelError) as rejected:
                transient(program,dict(u=UP,w=DOWN),[0,.25,.75,1],stop=1,max_step=2,kernel=KERNEL,source_errors={'w':2**-54})
            # A generic RN admission failure cannot establish this negative
            # numerical duty. v17 retains a genuine RED at this first blocker.
            self.assertIn(rejected.exception.detail['kind'],{'event_condition','event_domain','event_accuracy','unsupported_source_uncertainty'})
