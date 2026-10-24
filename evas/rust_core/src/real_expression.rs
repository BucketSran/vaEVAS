//! Materialization of binary64 program values. Physical roots remain elsewhere.
use crate::interval::Interval as I;
use crate::ir::{Error, Expression as E, RealOperation};
use crate::real_rounding::{self, Fault, Image, Op};

pub(crate) fn operation(op: RealOperation) -> Op {
    match op { RealOperation::Add=>Op::Add, RealOperation::Subtract=>Op::Subtract,
        RealOperation::Multiply=>Op::Multiply, RealOperation::Divide=>Op::Divide }
}
pub(crate) fn fault<T: std::fmt::Debug>(error: Fault<T>) -> Error {
    Error::new("real_arithmetic", format!("program-real arithmetic: {error:?}"))
}
pub(crate) fn literal(value:f64)->E { E::Affine{constant:value,terms:Vec::new()} }
pub(crate) fn point(op:RealOperation,a:f64,b:f64)->Result<f64,Error> {
    real_rounding::point(operation(op),a,b).map_err(fault)
}
pub(crate) fn constant(e:&E)->Option<f64> {
    match e {
        E::Affine{constant,terms} if terms.is_empty()=>Some(*constant),
        E::RealBoundary{value,..}=>constant(value),
        E::RealBinary{operation,left,right,..}=>point(*operation,constant(left)?,constant(right)?).ok(),
        _=>None,
    }
}
pub(crate) fn materialized(e:&E)->Result<E,Error> {
    constant(e).map(literal).ok_or_else(||Error::new("invalid_ir","unbound real value requires its procedure frame"))
}
pub(crate) fn interval(
    value:I, work:Option<&crate::transition_source_plan::Work>,
)->Result<I,Error> {
    if value.lo.to_bits()==value.hi.to_bits() {return Ok(value);}
    let lo=crate::exact_source::binary(value.lo).ok_or_else(||Error::new("real_arithmetic","nonfinite real sample"))?;
    let hi=crate::exact_source::binary(value.hi).ok_or_else(||Error::new("real_arithmetic","nonfinite real sample"))?;
    let result=real_rounding::image(&lo,&hi,&mut |n|work.map_or(Ok(()),|w|w.debit(2,n)))
        .map_err(|e|match e {Fault::Quota(e)=>e,other=>fault(other)})?;
    Ok(I{lo:result.lo,hi:result.hi})
}
pub(crate) fn binary_interval(op:RealOperation,a:I,b:I,work:Option<&crate::transition_source_plan::Work>)->Result<I,Error>{
    let result=real_rounding::binary_image(operation(op),Image{lo:a.lo,hi:a.hi},Image{lo:b.lo,hi:b.hi},
        &mut |n|work.map_or(Ok(()),|w|w.debit(2,n)))
        .map_err(|e|match e {Fault::Quota(e)=>e,other=>fault(other)})?;
    Ok(I{lo:result.lo,hi:result.hi})
}

pub(crate) fn work(model:&crate::events::EventModel)->&crate::transition_source_plan::Work{
    if let Some(owner)=crate::analytic_request::proof_owner(model){return owner.work();}
    if let Some(owner)=&model.floor_source{return owner.work();}
    if let Some(owner)=&model.source_context{return owner.borrow_work();}
    model.mixed_cold_work.get_or_init(Default::default)
}
