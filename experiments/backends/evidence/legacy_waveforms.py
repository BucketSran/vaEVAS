"""Legacy floating-point projections of CSV, PSF and text waveform exports.

Parsing order, duplicate times, units and errors retain the original contract.
This API returns binary64 values and does not grant observation qualification.
Use psf.normalize with frozen voltage nodes for token-preserving PSF analysis.
"""
import csv
import re


def number(s):
    try:
        return float(s)
    except ValueError:
        match=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([A-Za-z]+)',s)
        factors={'T':1e12,'G':1e9,'Meg':1e6,'K':1e3,'k':1e3,'m':1e-3,'u':1e-6,'n':1e-9,'p':1e-12,'f':1e-15,'a':1e-18}
        if not match or match[2] not in factors:
            raise ValueError('unrecognized numeric token: '+s)
        return float(match[1])*factors[match[2]]


def read_waveform(path, backend):
    if backend=='evas':
        with path.open() as stream:
            reader=csv.DictReader(stream)
            if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)):
                raise ValueError('missing or duplicate CSV columns')
            return [{k:float(v) for k,v in row.items()} for row in reader]
    if backend=='spectre':
        lines=[line.strip() for line in path.read_text().splitlines()]
        start=lines.index('VALUE')+1
        if lines[-1]!='END':
            raise ValueError('truncated PSF')
        rows=[];row=None
        for line in lines[start:-1]:
            m=re.fullmatch(r'"([^"]+)"\s+(\S+)',line)
            if not m:
                raise ValueError('unexpected PSF value: '+line)
            if m[1]=='time':
                if row is not None: rows.append(row)
                row={'time':float(m[2])}
            elif row is None or m[1] in row:
                raise ValueError('PSF time missing or repeated signal')
            else:
                row[m[1]]=float(m[2])
        if row is not None: rows.append(row)
        return rows
    lines=[line.split() for line in path.read_text().splitlines() if line.strip()]
    header=lines.pop(0)
    if header[0].lower() not in ['#time','time']:
        raise ValueError('unexpected text waveform header')
    names=['time']+[re.sub(r'^v\((.*)\)$',r'\1',name) for name in header[1:]]
    if len(names)!=len(set(names)) or any(len(row)!=len(names) for row in lines):
        raise ValueError('duplicate or ragged waveform columns')
    return [dict(zip(names,map(number,row))) for row in lines]
