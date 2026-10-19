use super::SCHEMA_VERSION;
use serde_json::{json, Value};
pub(crate) fn fixture() -> Value {
    let o = json!({"source":"history-consumer.va","line":1,"column":1,"instance":"M"});
    let c = |v: f64| json!({"op":"affine","constant":v,"terms":[]});
    let s = |i: usize| json!({"op":"state","state":i});
    let n = |i: usize| json!({"op":"affine","constant":0.,"terms":[{"node":i,"coefficient":1.}]});
    let select = |left: Value, right: Value, a: Value, b: Value| json!({"op":"select","relation":"gt","left":left,"right":right,"then_value":a,"else_value":b,"origin":o});
    let add = |a: Value, b: Value| json!({"op":"add","left":a,"right":b});
    let contribution = |node: usize, name: &str, rhs: Value| json!({"positive":node,"negative":0,"branch":{"instance":"M","local_positive":name,"local_negative":"zzref","kind":"voltage"},"rhs":rhs,"origin":o});
    let startup = select(s(0), c(1.), c(1.), c(0.));
    let gate = select(n(2), c(0.5), add(n(1), c(0.125)), c(0.));
    // The second simultaneous callback samples the accepted physical history.
    // It must not observe the just-incremented counter as startup permission.
    let clock =
        json!({"kind":"timer","start":0.25,"period":0.25,"time_tolerance":1e-12,"enabled":true});
    json!({"program":{"schema_version":SCHEMA_VERSION,"nodes":["0","temp","startup","core","sample","top"],
        "states":[{"instance":"M","name":"por_count","kind":"integer","initial":0.},
                  {"instance":"M","name":"sampled","kind":"real","initial":0.}],
        "operators":[{"kind":"transition","input":startup,"delay":0.,"rise":0.25,"fall":0.25,"origin":o}],
        "events":[{"origin":o,"trigger":clock,"body":[{"kind":"if","origin":o,"relation":"lt","left":s(0),"right":c(2.),"then_body":[{"kind":"assign","state":0,"rhs":add(s(0),c(1.))}],"else_body":[]}]},
                  {"origin":o,"trigger":clock,"body":[{"kind":"assign","state":1,"rhs":n(3)}]}],
        "contributions":[contribution(2,"startup",json!({"op":"operator","operator":0})),
                         contribution(3,"core",gate),contribution(4,"sample",s(1)),
                         contribution(5,"top",select(n(3),c(0.75),c(0.75),n(3)))]},
        "driven":["temp"],"samples":[],"tolerances":{"absolute":1e-10,"relative":0.},
        "transient":{"pwl":[[[0.,0.5],[1.,0.5]]],"output_times":[0.,0.25,0.5,0.5625,0.625,0.6875,0.75,1.],"stop":1.,"max_step":0.0625}})
}
