"""Use the public protocol validator before interpreting returned observations."""
from evas.protocol import validate_response

def observations(response, requested_times, program):
 validate_response(response,program,len(requested_times),list(requested_times))
 return [dict(time=t,voltages=dict(zip(response['nodes'],row['voltages'],strict=True)))
         for t,row in zip(response['transient']['times'],response['solutions'],strict=True)]
