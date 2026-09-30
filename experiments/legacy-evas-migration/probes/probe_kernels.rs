// Executes the original, unmodified Rust crate through public API.
use evas_rust_core::{evaluate_body_ir_ops_at_time, EvasRustBodyExprOp as Expr, EvasRustBodyStmtOp as Stmt};
fn run(kind: u8, state: &mut [f64], time: f64, args: &[f64]) -> f64 {
    let expressions: Vec<_> = args.iter().map(|&value| Expr{op_kind:0,index:0,value}).collect();
    let statements = [Stmt {target_kind:kind,target_integer:0,target_id:0,expr_start:0,expr_count:args.len()}];
    evaluate_body_ir_ops_at_time(&statements,&expressions,&mut [],state,&[],time).unwrap();
    state[0]
}
fn main() {
    let mut s=[0.;5];
    run(238,&mut s,0.,&[0.,0.]);
    let first=run(238,&mut s,1.,&[2.,0.]);
    let corrected=run(238,&mut s,1.,&[4.,0.]);
    println!("{{\"id\":\"K01_same_time_trial\",\"first\":{first},\"corrected\":{corrected},\"expected_recomputed_from_t0\":2.0}}");
    let replay=run(238,&mut s,0.5,&[1.,0.]);
    println!("{{\"id\":\"K02_backwards_query\",\"observed\":{replay},\"expected_ramp_history\":0.25}}");
    let mut s=[0.;5];
    run(225,&mut s,0.,&[0.,1.,1.,1.,1.]);
    let y=run(225,&mut s,1e-20,&[1.,1.,1.,1.,1.]);
    let expected=-(-1e-20_f64).exp_m1();
    println!("{{\"id\":\"K03_small_exponential_increment\",\"observed\":{y},\"stable_reference\":{expected}}}");
    let mut s=[0.;5];
    let y=run(244,&mut s,0.,&[0.,-0.25,-1.]);
    println!("{{\"id\":\"K04_negative_modulus\",\"observed\":{y},\"expected\":\"reject nonpositive specified modulus\"}}");
}
