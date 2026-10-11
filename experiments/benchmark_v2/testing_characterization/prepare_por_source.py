"""Prepare the pinned upstream POR circuit for local ngspice source validation.

No nominal device/model parameters are changed. CACE placeholders, include paths,
short-one-shot test mode and data export are explicit run configuration.
"""
import argparse
from pathlib import Path
import re
import json
import hashlib
import subprocess

def flatten(path):
    path=Path(path).resolve()
    lines=[]
    for line in path.read_text().splitlines():
        m=re.match(r'\s*\.include\s+["\']?([^"\']+)["\']?\s*$',line,re.I)
        if m:
            lines.append(flatten(path.parent/m[1].strip()))
        else:
            lines.append(line)
    return '\n'.join(lines)+'\n'

def cdl_level_shifter(path):
    """Translate official schematic CDL MOS syntax without changing geometry.

    CDL has micron dimensions and device model short names. Preserve supported
    nominal parameters; area/perim/topography are CDL layout metadata.
    """
    text=re.sub(r'\n\+\s*',' ',path.read_text())
    lines=[]
    for line in text.splitlines():
        if line.startswith('M'):
            tokens=line.split()
            tokens[0]='X'+tokens[0][1:]
            tokens[5]='sky130_fd_pr__'+tokens[5]
            line=' '.join(tokens[:6]+[t for t in tokens[6:] if t.split('=')[0] in ['m','w','l','sa','sb','sd','mult']])
        lines.append(line)
    return '\n'.join(lines)+'\n'

def build(source,pdk,hvl,hd,output,cell_view='spice'):
    output.mkdir(parents=True,exist_ok=True)
    text=(source/'cace/transient.spice').read_text()
    params={'Vavss':'0','Vdvss':'0','Vavdd':'3.3','Vdvdd':'1.8','force_pdn':'0','force_dis_rc_osc':'0','force_ena_rc_osc':'0','force_short_oneshot':'1','isrc_sel':'0','temperature':'27','otrip[0]':'0','otrip[1]':'0','otrip[2]':'0','otrip[3]':'0'}
    for name,value in params.items(): text=text.replace('{'+name+'}',value)
    text=re.sub(r'\[([0-9.]+\*[0-9.]+)\]',r'{\1}',text)
    text=re.sub(r'^\.lib .+$','',text,flags=re.M)
    text=re.sub(r'^\.include \{PDK_ROOT\}.+$','',text,flags=re.M)
    text=text.replace('.include por_dig.out.spice',(source/'xspice/por_dig.out.spice').read_text())
    text=re.sub(r'\.control.*?\.endc',''' .control
set wr_singlescale
set wr_vecnames
set numdgt=17
tran 0.1u 4m 0 0.5u
wrdata waveform.dat v(avdd) v(por) v(porb) v(osc_ck) v(pwup_filt) v(startup_timed_out) v(por_timed_out)
quit
.endc''',text,flags=re.S)
    text=text.replace('.option TEMP=27','.option TEMP=27\n.option wnflag=1 scale=1u\n.param dlc_rotweak=0')
    text=text.replace('.save v(porb) v(avdd) v(osc_ck)','.save v(porb) v(avdd) v(osc_ck) v(por) v(pwup_filt) v(startup_timed_out) v(por_timed_out)')
    models=flatten(pdk/'models/parameters/invariant.spice')+flatten(pdk/'models/r+c/res_typical__cap_typical.spice')+flatten(pdk/'models/r+c/res_typical__cap_typical__lin.spice')+flatten(pdk/'models/corners/tt.spice')
    # Unused obsolete ESD include uses non-SPICE 'include' in the upstream
    # raw library. Keep this parser-only removal explicit in source identity.
    models=re.sub(r'^include .+$','* ignored obsolete non-SPICE include',models,flags=re.M)
    models=re.sub(r"\s+dev/gauss\s*=\s*'[^']+'",'',models)
    models=re.sub(r"\s+dev/gauss=\S+",'',models)
    (output/'models.spice').write_text(models)
    cells=sorted(set(re.findall(r'\bsky130_fd_sc_(?:hvl|hd)__[A-Za-z0-9_]+',text)))
    included=[]
    for cell in cells:
        group=cell.split('__')[0]
        name=cell.split('__')[1]
        directory=name.rsplit('_',1)[0]
        root=hvl if group.endswith('hvl') else hd
        matches=list((root/'cells'/directory).glob(cell+'.spice'))
        if not matches:
            # XSPICE cells are already converted and their comment names have
            # no transistor instance, so only actual source instances need a cell.
            if re.search(r'^[xX].*\b'+re.escape(cell)+r'(?:\s|$)',text,re.M):
                raise ValueError('missing cell '+cell)
            continue
        if cell_view=='cdl-level-shifters' and directory in ['lsbuflv2hv','lsbufhv2lv']:
            included.append(cdl_level_shifter(matches[0].with_suffix('.cdl')))
        else:
            included.append(matches[0].read_text())
    (output/'cells.spice').write_text('\n'.join(included))
    text=text.replace('**** begin user architecture code','.include models.spice\n.include cells.spice\n**** begin user architecture code',1)
    (output/'por.cir').write_text(text)
    identity={}
    for name,root in [('por',source),('fd_pr',pdk),('fd_sc_hvl',hvl),('fd_sc_hd',hd)]:
        identity[name]=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    identity['deck_sha256']=hashlib.sha256(text.encode()).hexdigest()
    identity['cell_view']=cell_view
    identity['mode']='short one-shots, force_short_oneshot=1, no sleep'
    identity['processing']=['recursive include flatten','CACE configuration substitution','ngspice W/NF bin selection wnflag=1','obsolete non-SPICE include omitted','unsupported dev/gauss annotations omitted at nominal TT']
    (output/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['source','pdk','hvl','hd','output']: p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--cell-view',choices=['spice','cdl-level-shifters'],default='spice')
    a=p.parse_args();build(a.source,a.pdk,a.hvl,a.hd,a.output,a.cell_view)
