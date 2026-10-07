"""Direct output check only at independently proven before/after physical phase probes."""
def direct_phase_y(rows,checker,family,probes):
 records=[]
 for row in rows:
  if row['time'] not in probes.values():continue
  clock=checker.Q(row['time']);expected=checker.formula(family,clock)['y'];budget=checker.Q(1e-7) if family=='mixed_source' else checker.V
  records.append({'time':row['time'],'actual_y':row['y'],'expected_y':float(expected),'status':'P' if abs(checker.Q(row['y'])-expected)<=budget else 'F','exact_numeric_query_rational':str(clock)})
 return {'status':'P' if len(records)==len(set(probes.values())) and all(r['status']=='P' for r in records) else 'F','records':records,'scope':'No blanketjump-window exemption at these separately proved physicalphase probes; original finitechecker unchanged for its originalscope. Exact-clock boundaries are not amongthese probes.'}
