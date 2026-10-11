"""Different authored state realizations; live calibration remains required."""
import re

REASONS={
 '071':'voltage deficit relative to vinit is the acquisition state',
 '038':'latched discrete gain mode; gain voltage computed continuously',
 '082':'integer hundredths gain controller instead of real gain accumulator',
 '091':'LP accumulator in unscaled input units; derived baseband voltage',
 '307':'saturated integrator deviation relative to vcm is the stored state',
 '308':'reset latch stores signed deviation, derives absolute boundary voltage',
 '370':'three-bit history of qualifying errors instead of convergence counter',
 '353':'circular three-symbol buffer instead of shifting three registers',
 '055':'post-feedback residual is stored; next quantizer input is temporary',
 '002':'latched digital code/calibration word instead of two latched analog levels',
 '003':'ternary sub-ADC decision state drives residue and bit decoding',
 '047':'two sampled comparator states feed combinational window AND',
 '314':'inside rail voltage is the hysteresis memory instead of a boolean',
 '001':'packed three-sample history with decision lookup instead of separate latches',
 '396':'rotating two-bit quadrature state instead of modulo phase counter',
 '186':'packed SAR masks and bit updates instead of four-element arrays',
}


def replace(source,old,new):
    if old not in source:raise ValueError(f'missing alternative edit: {old}')
    return source.replace(old,new)


def alternative(source,sid,filename):
    s=source
    if sid=='071':
        s=replace(s,'real held;','real deficit;')
        s=replace(s,'held = vinit;','deficit = 0;')
        s=replace(s,'held = held + alpha * (V(vin) - held);','deficit = (1-alpha)*deficit + alpha*(vinit-V(vin));')
        s=replace(s,'transition(held,','transition(vinit-deficit,')
    elif sid=='038':
        s=replace(s,'real gain_value;','integer gain_mode;\n    real gain_value;')
        s=replace(s,'gain_value = 1.0;','gain_mode = 0;')
        s=replace(s,'gain_value = gain_high;','gain_mode = 2;')
        s=replace(s,'gain_value = gain_low;','gain_mode = 1;')
        s=replace(s,'raw = vcm', 'gain_value = gain_mode==0 ? 1.0 : (gain_mode==1 ? gain_low : gain_high);\n        raw = vcm')
    elif sid=='082':
        s=replace(s,'real gainv,','integer gain_code;\nreal')
        s=replace(s,'gainv = 2.2;','gain_code = 220;')
        s=replace(s,'gainv = gainv - 0.18;','gain_code = gain_code - 18;')
        s=replace(s,'gainv = gainv + 0.10;','gain_code = gain_code + 10;')
        s=replace(s,'if (gainv > 3.0) gainv = 3.0;','if (gain_code > 300) gain_code = 300;')
        s=replace(s,'if (gainv < 0.45) gainv = 0.45;','if (gain_code < 45) gain_code = 45;')
        s=re.sub(r'\bgainv\b','(0.01*gain_code)',s)
    elif sid=='091' and filename=='synchronous_lp_state.va':
        s=replace(s,'real baseband_q,','real accumulator; real baseband_q,')
        s=replace(s,'baseband_q=0;', 'accumulator=0; baseband_q=0;')
        s=replace(s,'baseband_q=baseband_q+lp_alpha*(V(demod_sample)-baseband_q);','accumulator=(1-lp_alpha)*accumulator+V(demod_sample); baseband_q=lp_alpha*accumulator;')
    elif sid=='307' and filename=='integrator_state_cell.va':
        s=re.sub(r'\bstate_v\b','deviation',s)
        s=replace(s,'deviation = vcm;', 'deviation = 0;')
        s=replace(s,'clip01(deviation + 1.0 * k_int * (V(sample_node) - vcm))','clip01(vcm + deviation + k_int*(V(sample_node)-vcm))-vcm')
        s=replace(s,'clip01(deviation)', 'clip01(vcm+deviation)')
    elif sid=='308' and filename=='reset_sample_latch.va':
        s=re.sub(r'\breset_sample\b','reset_delta',s)
        s=replace(s,'reset_delta = vcm;', 'reset_delta = 0;')
        s=replace(s,'reset_delta=vcm;', 'reset_delta=0;')
        s=replace(s,'reset_delta = V(vin);', 'reset_delta = V(vin)-vcm;')
        s=replace(s,'clip01(reset_delta)', 'clip01(vcm+reset_delta)')
    elif sid=='370':
        s=re.sub(r'\bsettle_count\b','good_history',s)
        s=replace(s,'if (absval(err_v) < settle_tol) good_history = good_history + 1; else good_history = 0;', 'good_history=((good_history << 1) | (absval(err_v)<settle_tol)) & 7;')
        s=replace(s,'good_history >= 3','good_history == 7')
    elif sid=='353':
        s=replace(s,'integer sym0;', 'integer history[0:2]; integer head;\n    integer sym0;')
        s=replace(s,'sym0 = 0;', 'history[0]=0;history[1]=0;history[2]=0;head=2;\n            sym0 = 0;')
        s=replace(s,'sym2 = sym1;\n                sym1 = sym0;\n                sym0 = (V(data) > vth) ? 1 : -1;', 'head=(head+1)%3;history[head]=(V(data)>vth)?1:-1;\n                sym0=history[head];sym1=history[(head+2)%3];sym2=history[(head+1)%3];')
    elif sid=='055':
        s=replace(s,'real acc;', 'real residual; real acc;')
        s=replace(s,'acc = 0.0;', 'residual = 0.0; acc = 0.0;')
        s=replace(s,'acc = acc + V(vin) / vref - bit_state;', 'acc = residual + V(vin)/vref;')
        s=replace(s,'bit_state = (acc >= 0.0) ? 1 : 0;', 'bit_state = (acc >= 0.0) ? 1 : 0;\n        residual=acc-bit_state;')
    elif sid=='002':
        s=replace(s,'integer code;', 'integer sampled; integer code;')
        s=replace(s,'vdac_p_level = vcm;\n            vdac_n_level = vcm;', 'sampled=0;code=0;cal=0;')
        start=s.index('            vdac_p_level = vcm + swing')
        end=s.index('\n        V(VDAC_P',start)
        s=s[:start]+'''            sampled=1;
        end
        vdac_p_level=sampled ? vcm+swing*(((code+32*cal)/1023.0)-0.5)*0.5 : vcm;
        vdac_n_level=sampled ? vcm-swing*(((code+32*cal)/1023.0)-0.5)*0.5 : vcm;
'''+s[end:]
    elif sid=='003':
        s=replace(s,'real vin_s;', 'integer decision; real vin_s;')
        start=s.index('        if (vin_rel > vref_qtr)')
        end=s.index('        if (vres_level > V(VDD))',start)
        s=s[:start]+'''        decision=0;
        if(vin_rel>vref_qtr)decision=1;
        else if(vin_rel < -vref_qtr)decision=-1;
        d1_level=decision==1 ? V(VDD) : V(VSS);
        d0_level=decision==0 ? V(VDD) : V(VSS);
        vres_level=vcm+2.0*vin_rel-decision*V(VREF)/2.0;

'''+s[end:]
    elif sid=='047':
        s=replace(s,'integer state;', 'integer lower_ok,upper_ok;')
        s=replace(s,'@(initial_step)state=(V(vin,VSS)>vlow && V(vin,VSS)<vhigh);', '@(initial_step)begin lower_ok=(V(vin,VSS)>vlow);upper_ok=(V(vin,VSS)<vhigh);end')
        s=replace(s,'@(timer(0,tick))state=(V(vin,VSS)>vlow && V(vin,VSS)<vhigh);','@(timer(0,tick))begin lower_ok=(V(vin,VSS)>vlow);upper_ok=(V(vin,VSS)<vhigh);end')
        s=replace(s,'transition(state,','transition(lower_ok && upper_ok,')
    elif sid=='314':
        s=replace(s,'integer state,oldstate;', 'real state,oldstate;')
        s=re.sub(r'\bstate=0;', 'state=vss;',s)
        s=replace(s,'oldstate=0;', 'oldstate=vss;')
        s=replace(s,'state==0','state==vss');s=replace(s,'state==1','state==vdd')
        s=replace(s,'state=1;', 'state=vdd;')
        s=replace(s,'state?vdd:vss','state')
    elif sid=='001':
        s=replace(s,'integer a,b,c,u,d;', 'integer samples,u,d;')
        s=replace(s,'a=0;b=0;c=0;', 'samples=0;')
        s=replace(s,'b=(V(data)>vth);','samples=(samples & 5) | ((V(data)>vth)<<1);')
        s=replace(s,'a=c;c=(V(data)>vth);u=(a!=b && b==c);d=(a==b && b!=c);', 'samples=((samples & 1)<<2) | (samples & 2) | (V(data)>vth);u=(samples==3 || samples==4);d=(samples==1 || samples==6);')
        s=replace(s,'c?vdd:0', '(samples & 1)?vdd:0')
    elif sid=='396':
        s=replace(s,'integer phase_state;', 'integer next_i,next_q,previous_i;')
        s=replace(s,'phase_state = 0;', 'next_i=1;next_q=0;')
        start=s.index('                output_state = phase_state;')
        end=s.index('                enabled_edge_count',start)
        s=s[:start]+'''                lo_i_state=next_i;lo_q_state=next_q;
                output_state=next_q ? (next_i ? 1 : 2) : (next_i ? 0 : 3);
'''+s[end:]
        s=replace(s,'phase_state = (phase_state + 1) % 4;', 'previous_i=next_i;next_i=1-next_q;next_q=previous_i;')
    elif sid=='186':
        s=replace(s,'integer p[0:3], m[0:3], dout[0:3], dtest[0:3];', 'integer pword,mword,outword,testword;')
        s=replace(s,'p[0]=0; m[0]=0; p[1]=1; m[1]=1; p[2]=1; m[2]=1; p[3]=1; m[3]=1;', 'pword=14;mword=14;')
        s=replace(s,'dout[0]=0; dout[1]=0; dout[2]=0; dout[3]=0;', 'outword=0;')
        s=replace(s,'dout[3]=p[0]; dout[2]=p[1]; dout[1]=p[2]; dout[0]=p[3];', 'outword=((pword&1)<<3) | ((pword&2)<<1) | ((pword&4)>>1) | ((pword&8)>>3);')
        s=replace(s,'dtest[0]=V(dtest3)>0.45; dtest[1]=V(dtest2)>0.45; dtest[2]=V(dtest1)>0.45; dtest[3]=V(dtest0)>0.45;', 'testword=(V(dtest3)>0.45) | ((V(dtest2)>0.45)<<1) | ((V(dtest1)>0.45)<<2) | ((V(dtest0)>0.45)<<3);')
        s=replace(s,'if (V(test)<0.45) begin p[pointer]=dcmp; m[pointer]=1-dcmp; end\n            else begin p[pointer]=dtest[pointer]; m[pointer]=1-dtest[pointer]; end', 'if(V(test)>=0.45)dcmp=(testword>>pointer)&1;\n            pword=(pword & ~(1<<pointer)) | (dcmp<<pointer);\n            mword=(mword & ~(1<<pointer)) | ((1-dcmp)<<pointer);')
        for name,word in [('p','pword'),('m','mword'),('dout','outword')]:
            s=re.sub(name+r'\[(\d)\]',lambda m:f'(({word}>>{m[1]})&1)',s)
    return s


def main():
    import hashlib
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[3]
    out=Path(__file__).resolve().parent
    changes=[]
    for sid,reason in REASONS.items():
        task=next((root/'benchmark/tasks').glob('v2-spec-'+sid+'-*'))
        dest=out/'candidates'/task.name/'alternative'
        files={}
        for f in (task/'solution').glob('*.va'):
            target=dest/f.name;before=target.read_bytes()
            after=alternative(f.read_text(),sid,f.name).encode()
            target.write_bytes(after)
            files[f.name]=dict(before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(after).hexdigest(),changed=before!=after)
        changes.append(dict(source_id=sid,reason=reason,files=files,calibration='pending-live-execution'))
    plan_path=out/'run-plan.json';plan=json.loads(plan_path.read_text())
    for row in plan:
        sid=Path(row['task']).name.split('-')[2]
        if row['variant']=='alternative' and sid in REASONS:
            row['semantic_behavior']=REASONS[sid];row['certification']='pending-live-execution'
    plan_path.write_text(json.dumps(plan,indent=2)+'\n')
    manifest_path=out/'manifest.json';manifest=json.loads(manifest_path.read_text())
    for row in manifest['sources']:
        sid=row['source_id']
        if sid in REASONS:
            row['alternative_calibration']='pending'
            task=root/row['assets']['task']
            for variant in row['variants']:
                if variant['id']=='alternative':
                    variant['status']='pending';variant['semantic_behavior']=REASONS[sid]
                    variant['files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'candidates'/task.name/'alternative').glob('*.va')}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    # Caller retains pre/post identity in ignored evidence; do not turn it into
    # an assertion of actual backend acceptance.
    print(json.dumps(changes,indent=2))

if __name__=='__main__':main()
