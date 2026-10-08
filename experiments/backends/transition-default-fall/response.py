"""Validate response observation identity before interpreting voltage columns."""
import math

def observations(response, requested_times, expected_nodes):
 times=response.get('transient',{}).get('times')
 if not isinstance(times,list) or len(times)!=len(requested_times):
  raise ValueError('response time shape differs from request')
 if any(type(t) not in (int,float) or not math.isfinite(t) for t in times):
  raise ValueError('nonfinite or nonnumeric response time')
 if times!=list(requested_times):raise ValueError('response times differ from request')
 nodes=response.get('nodes')
 if nodes!=list(expected_nodes):raise ValueError('response node columns differ from frozen model')
 solutions=response.get('solutions')
 if not isinstance(solutions,list) or len(solutions)!=len(times):
  raise ValueError('response solution shape differs from times')
 rows=[]
 for t,solution in zip(times,solutions,strict=True):
  values=solution.get('voltages') if isinstance(solution,dict) else None
  if not isinstance(values,list) or len(values)!=len(nodes):
   raise ValueError('response voltage row shape differs from node columns')
  if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
   raise ValueError('nonfinite or nonnumeric response voltage')
  rows.append(dict(time=t,voltages=dict(zip(nodes,values,strict=True))))
 return rows
