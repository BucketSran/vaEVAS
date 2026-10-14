"""Build compact extracts from local-only receipts. Requires explicit local run root."""
from pathlib import Path
import argparse,json,hashlib,shutil,re,bisect
P=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
def scrub(v):
 if isinstance(v,dict):return {scrub(k):scrub(x) for k,x in v.items()}
 if isinstance(v,list):return [scrub(x) for x in v]
 if isinstance(v,str):
  return re.sub(r'/(?:Users|home|edamgr|opt)/[^\s"\'\],)]+',lambda m:'local-only/'+Path(m.group()).name,v)
 return v
def dump(n,v):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(scrub(v),ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('run_root',type=Path);args=ap.parse_args();R=args.run_root;draft=R/'reference-preparation/deadline-paired-analysis-v1/curated-package-draft';origins={}
 for f in draft.rglob('*'):
  if not f.is_file() or f.name in ['PACKAGE-MANIFEST.json','VERIFY-RESULT.json','README.md','verify.py','STATUS.json','ORIGINAL-FULL-STATUS.json','ORIGINS.json','SOURCE-IDENTITY.json']:continue
  rel=str(f.relative_to(draft));origins[rel]={'original_sha256':sha(f),'local_receipt':str(f.relative_to(R))}
  if f.suffix=='.json':dump(rel,load(f))
  else:(P/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,P/rel)
 # Preserve portable finite checker, separate latest final N09 status from historical0538.
 s=(draft/'verify.py').read_text();s=s.replace("status['fixed_kernel_sha256']=='0538fee02ce67fb51c3da921f2607a27e64ccdcd1db257040aa118d14d065717'","status['n09_retained_kernel_sha256']=='0538fee02ce67fb51c3da921f2607a27e64ccdcd1db257040aa118d14d065717'").replace("a['kernel_sha256']==status['fixed_kernel_sha256']","a['kernel_sha256']==status['n09_retained_kernel_sha256']").replace("load(P/'ORIGINAL-FULL-STATUS.json')['completed']==0","load(P/'ORIGINAL-FULL-STATUS.json')['completed']==1").replace("len(history)==5","len(history)>=11").replace("'original_full_completed':0","'original_full_completed':1").replace("'historical_failures_preserved':5","'historical_failures_preserved':len(history)").replace("'draft':True","'final_N09_pending':status['n09_final_current_status']=='pending'")
 (P/'finite_verify.py').write_text(s)
 full=R/'original-initial-v10';case=full/'r01/r01-measure-interleaved-time/timing-0';grade=load(case/'regrade.json');before=load(full/'SOURCE-BEFORE.json');after=load(full/'SOURCE-AFTER.json');binding=load(full/'BINDING-RECEIPT.json');assert before==after and binding['source_kernel_checker_unchanged']
 result=load(case/'result.json');dump('ORIGINAL-FULL-STATUS.json',{'completed':1,'status':result['status'],'exit_code':result['exit_code'],'elapsed_seconds':result['elapsed_seconds'],'timeout_seconds':result['timeout_seconds'],'waveform_rows':grade['waveform_rows'],'kernel_sha256':before['kernel_sha256'],'source_before_after_equal':True,'source_before_sha256':sha(full/'SOURCE-BEFORE.json'),'source_after_sha256':sha(full/'SOURCE-AFTER.json'),'response_sha256':sha(case/'stdout.json'),'result_sha256':sha(case/'result.json'),'regrade_sha256':sha(case/'regrade.json'),'original_checker':grade['original_checker'],'checker_sha256':grade['checker_sha256'],'input_sha256':result['input_sha256'],'diagnostic':result['diagnostic'],'paired_observation_receipt':grade['paired_observation'],'sample_time_encoding_seconds_per_V':1e-6,'claim_limit':'Original task completed under120s and frozen checker passed. Paired finite291times outside original5ns edge windows; not full-time/root-side/Q3 proof.'})
 dump('SOURCE-IDENTITY.json',{'kernel_sha256':before['kernel_sha256'],'sources':before['sources'],'original_inputs':before['original_inputs'],'original_task_tests':before['original_task_tests'],'source_before_after_equal':True,'source_receipt_original_sha256':sha(full/'SOURCE-BEFORE.json')})
 hist=[]
 for f in sorted(R.glob('original-*/r01-results.json')):
  for row in load(f):
   if row['status']=='failed':
    stage=f.parent.name;sb=f.parent/'SOURCE-BEFORE.json';hist.append({'stage':stage,'receipt_sha256':sha(f),'kernel_sha256':load(sb).get('kernel_sha256') if sb.exists() else None,'status':'failed','exit_code':row['exit_code'],'seconds':row['elapsed_seconds'],'timeout_s':row['timeout_seconds'],'diagnostic':row['diagnostic'],'input_sha256':row['input_sha256']})
 dump('HISTORICAL-FAILURES.json',hist)
 fresh=load(R/'reference-preparation/fresh-original-analysis/SUMMARY.json');assert fresh['native_VALUE_body_identity']['exact_VALUE_body_bytes_equal'];dump('ORIGINAL-REFERENCE-IDENTITY.json',fresh)
 # Same-source four inputs, native rows near original finite observation candidates only.
 raw=R/'original-spectre-v1/raw/timing-0'
 for n in ['dut.va','core.va','circuit.va','tb.scs']:
  dest=P/'original'/n;dest.parent.mkdir(exist_ok=True);shutil.copyfile(raw/n,dest);assert sha(dest)==fresh['source_identity'][n]
 dut=load(case/'stdout.json');text=(raw/'psf/tran.tran.tran').read_text();rr=[]
 for line in text.split('VALUE\n',1)[1].splitlines():
  m=re.fullmatch(r'"([^"\n]+)"\s+(\S+)',line)
  if not m:continue
  k,t=m.groups()
  if k=='time':rr.append({'time':t,'values':{}})
  else:rr[-1]['values'][k]=t
 rt=[float(row['time']) for row in rr];st=dut['saved']['times'];sn=dut['saved']['nodes'];sv=dut['saved']['values'];needed=grade['paired_observation']['observation_times'];nodes=grade['paired_observation']['output_nodes']+grade['paired_observation']['input_nodes'];ex=[]
 for t in needed:
  ri=bisect.bisect_left(rt,t);di=bisect.bisect_left(st,t)
  rix=[len(rt)-1] if ri==len(rt) else ([ri] if ri==0 or rt[ri]==t else [ri-1,ri]);dix=[len(st)-1] if di==len(st) else ([di] if di==0 or st[di]==t else [di-1,di])
  ex.append({'time':t,'reference_bracket':[{'time':rr[j]['time'],'values':{n:rr[j]['values'][n] for n in nodes}} for j in rix],'dut_bracket':[{'time':st[j],'values':{n:sv[j][sn.index(n)] for n in nodes}} for j in dix]})
 dump('original/FINITE-BRACKETS.json',{'scope':grade['paired_observation']['scope'],'reference_raw_sha256':fresh['psf_sha256'],'historical_reference_sha256':grade['paired_observation']['spectre_waveform_sha256'],'VALUE_identity':fresh['native_VALUE_body_identity'],'response_sha256':sha(case/'stdout.json'),'count':len(ex),'nodes':nodes,'rows':ex,'interpolation_limit':'Original finite observation uses linear interpolation; these brackets reproduce only that bounded comparison, not precise callback side.'})
 dump('original/DISPLAY.json',{'dut_records':dut['transient']['display_records'],'reference_records':load(R/'reference-preparation/fresh-original-analysis/DISPLAY.json')['records'],'original_checker_counts':grade['original_checker']['actual_records'],'reference_time_fields':fresh['display_time_fields'],'reference_fields_without_exact_native_token':fresh['display_time_fields_without_exact_native_token'],'time_budget_s':2.5e-10,'limit':'Original%.12g fields and interpolated waveform; not exact callback native token evidence.'})
 # Passive and initial finite receipts: compact originals plus all actual tokens/settings.
 for group,src in [('passive',R/'passive-reference-preparation'),('initial-v1',R/'initial-reference-preparation'),('initial-v2',R/'initial-reference-v2')]:
  a=load(src/'ANALYSIS.json');dump(group+'/evidence.json',a);origins[group+'/evidence.json']={'original_sha256':sha(src/'ANALYSIS.json'),'local_receipt':str((src/'ANALYSIS.json').relative_to(R))}
  for va in (src/'inputs').glob('*/dut.va'):
   label=va.parent.name;dest=P/group/label;dest.mkdir(parents=True,exist_ok=True)
   for n in ['dut.va','tb.scs','CONTRACT.json']:shutil.copyfile(va.parent/n,dest/n)
  if group=='passive':
   for c in a['cases']:
    label=c['label'];rp=R/'passive-anchor-green-v2'/('nonlinear-plain.json' if label=='nonlinear' else 'autonomous.json');g=load(rp);dump(group+'/'+label+'/DUT.json',{'kernel_sha256':g['kernel_sha256'],'times':g['times'],'program':g['program'],'result':g['result']})
  else:
   dump(group+'/DUT.json',load(R/'initial-horizon-implementation/micro-stdout.json'));shutil.copyfile(R/'initial-passive-horizon-design/initial-observer-request.json',P/group/'REQUEST.json')
 dump('initial-v2/PRECISION-COMPARISON.json',load(R/'initial-reference-v2/PRECISION-COMPARISON.json'))
 dump('STATUS.json',{'draft':False,'fixed_kernel_sha256':before['kernel_sha256'],'original_full_DUT_completed':1,'original_120s_frozen_checker_pass':True,'original_protected_checks':2219,'original_display_records':sum(grade['original_checker']['actual_records'].values()),'original_reference_display_time_fields':fresh['display_time_fields'],'original_finite_pair_times':len(ex),'n09_retained_kernel_sha256':'0538fee02ce67fb51c3da921f2607a27e64ccdcd1db257040aa118d14d065717','n09_retained_historical_finite_controls_pass':6,'n09_final_current_status':'pending','deadline_exact_complete_modes':0,'deadline_denominator_modes':6,'passive_exact_complete_controls':0,'passive_denominator_controls':2,'initial_v1_original_finite_gate':False,'initial_v2_original_finite_gate':True,'original70_all_rerun':False,'old16_final_current_rerun_status':'pending','Q3_claim':False,'availability':'Repository finite extracts only; full raw local-only, not a public replay archive.'})
 dump('ORIGINS.json',origins)
 if (R/'reference-preparation/paired-analysis-final-c5-v5/SUMMARY.json').exists():
  import update_n09
  update_n09.update(R)
 print('extracts written',P,'history',len(hist),'finite full times',len(ex))
if __name__=='__main__':main()
