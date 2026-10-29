"""EVAS precision worker with forced strobe evidence and original raw records.

Research planning, budgets and backend process ownership stay in experiments.
This worker shares serialization and actual-control records with the paper adapter;
its strobe sampling and result/error contract remain specific to precision.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_evas_worker import load, save, save_raw_response, evas_effective_record


def worker(work,kernel):
    sys.path.insert(0,str(ROOT/'evas/src'))
    from evas import compile_sources, transient, Instance, CompileError, KernelError
    request=load(work/'request.json');times=load(work/'requested_times.json')
    try:
        instances=[Instance(i['name'],i['module'],i['ports'],i['parameters']) for i in request['instances']]
        program=compile_sources({'dut.va':(work/'dut.va').read_text()},instances)
        save(work/'program.json',program.to_dict())
        response=transient(program,request['inputs'],times,stop=request['stop'],max_step=request['max_step'],
                           strobetimes=times,kernel=kernel,vabstol=request['vabstol'],reltol=request['reltol'],timeout=None)
        save_raw_response(work/'raw-response.json',response)
        strobe=response['strobe_evidence']
        if strobe['times']!=times:raise ValueError('strobe time mismatch')
        with (work/'waveform.csv').open('x') as stream:
            writer=csv.writer(stream);writer.writerow(['time',*response['nodes']])
            writer.writerows([t,*v] for t,v in zip(strobe['times'],strobe['voltages_V'],strict=True))
        save(work/'effective.json',evas_effective_record(request,response))
        result={'status':'waveform_available','origins':sorted(set(strobe['sample_origins']))}
    except CompileError as exc:result={'status':'compile_failed','reason':str(exc)}
    except KernelError as exc:result={'status':'execution_failed','reason':str(exc),'detail':exc.detail}
    except Exception as exc:result={'status':'execution_failed','reason':repr(exc)}
    save(work/'worker-result.json',result)
