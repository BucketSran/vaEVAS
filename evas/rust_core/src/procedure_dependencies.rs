//! Dependency metadata for source programs, separate from their executable
//! numerical equations. Never substitute these zero coefficient rows in a solve.
use super::*;
use crate::ir::Statement as S;

pub(crate) struct Sources<'a>{values:Vec<Vec<&'a E>>}
impl Sources<'_> {
    /// Borrow one source definition for an eligibility scan. Multiple writes
    /// are not a value proof and must stay on the conservative path.
    /// The caller prepays the lookup and its recursion-path storage.
    pub(crate) fn single_binding_value(&self, binding: usize) -> Result<Option<&E>, Error> {
        let values = self.values.get(binding)
            .ok_or_else(|| invalid("binding dependency index out of range"))?;
        Ok(match values.as_slice() {
            [value] => Some(*value),
            _ => None,
        })
    }
}
fn add<'a>(binding:usize,value:&'a E,values:&mut [Vec<&'a E>],w:&Work)->Result<(),Error>{w.debit(2,32)?;values.get_mut(binding).ok_or_else(||invalid("source binding index out of range"))?.push(value);Ok(())}
fn steps<'a>(body:&'a [ProcedureStep],values:&mut [Vec<&'a E>],w:&Work)->Result<(),Error>{for step in body{w.step()?;match &step.action{A::Control(C::RealBind{binding,value,..})=>add(*binding,value,values,w)?,A::Control(C::ProcedureIf{then_body,else_body,..})=>{steps(then_body,values,w)?;steps(else_body,values,w)?;},A::Control(C::ProcedureLoop{initialize,body,update,..})=>for body in [initialize,body,update]{steps(body,values,w)?;},_=>{}}}Ok(())}
fn expression<'a>(e:&'a E,values:&mut [Vec<&'a E>],w:&Work)->Result<(),Error>{w.step()?;if let E::RealCall{body,..}=e{steps(body,values,w)?;}calls::children(e,&mut |e|expression(e,values,w))}
fn statements<'a>(body:&'a [S],values:&mut [Vec<&'a E>],w:&Work)->Result<(),Error>{for s in body{w.step()?;match s{S::Assign(a)=>expression(&a.rhs,values,w)?,S::ArrayWrite{index,rhs,..}=>{expression(index,values,w)?;expression(rhs,values,w)?;},S::Display{args,..}=>for e in args{expression(e,values,w)?;},S::If{left,right,then_body,else_body,..}=>{expression(left,values,w)?;expression(right,values,w)?;statements(then_body,values,w)?;statements(else_body,values,w)?;},S::Loop{initialize,left,right,body,update,..}=>{expression(left,values,w)?;expression(right,values,w)?;for body in [initialize,body,update]{statements(body,values,w)?;}}}}Ok(())}
pub(crate) fn sources<'a>(p:&'a Program,w:&Work)->Result<Sources<'a>,Error>{
 w.debit(2,(p.real_bindings.len()*32+64) as u64)?;let mut values=vec![Vec::new();p.real_bindings.len()];
 for q in &p.procedures{steps(&q.body,&mut values,w)?;calls::step_expressions(&q.body,&mut |e|expression(e,&mut values,w))?;}
 for event in &p.events{statements(&event.body,&mut values,w)?;}
 for c in &p.contributions{expression(&c.rhs,&mut values,w)?;}
 for b in &p.step_bounds{expression(&b.value,&mut values,w)?;expression(&b.active,&mut values,w)?;}
 for o in &p.operators{w.step()?;expression(calls::input(o),&mut values,w)?;if let ir::OperatorSpec::Idt{reset:Some(e),..}=o{expression(e,&mut values,w)?;}}
 Ok(Sources{values})
}
pub(crate) fn dependencies(e:&E,p:&Program,sources:&Sources<'_>,w:&Work)->Result<crate::events::AffineState,Error>{
 w.debit(2,((p.nodes.len()+p.states.len()+p.operators.len())*16+128) as u64)?;
 let mut row=crate::events::affine(&E::Affine{constant:0.,terms:Vec::new()},p,"")?;
 let mut seen=BTreeSet::new();
 fn insert(set:&mut BTreeSet<usize>,value:usize,w:&Work)->Result<(),Error>{w.debit(2,((set.len()+1).ilog2() as u64+2)*32)?;set.insert(value);Ok(())}
 fn integer(n:&ir::IntegerOperand,row:&mut crate::events::AffineState,w:&Work)->Result<(),Error>{w.step()?;match n{ir::IntegerOperand::IntegerLiteral{..}=>{},ir::IntegerOperand::IntegerState{state}=>insert(&mut row.state_dependencies,*state,w)?,ir::IntegerOperand::IntegerPrimitive{args,..}=>for n in args{integer(n,row,w)?;}}Ok(())}
 fn visit(e:&E,sources:&Sources<'_>,row:&mut crate::events::AffineState,seen:&mut BTreeSet<usize>,w:&Work)->Result<(),Error>{
  w.step()?;match e{
   E::Affine{terms,..}=>for t in terms{insert(&mut row.node_dependencies,t.node,w)?;},
   E::State{state}=>insert(&mut row.state_dependencies,*state,w)?,
   E::Operator{operator}=>insert(&mut row.operator_dependencies,*operator,w)?,
   E::RealLocal{binding}=>{w.debit(2,((seen.len()+1).ilog2() as u64+2)*32)?;if seen.insert(*binding){for value in sources.values.get(*binding).ok_or_else(||invalid("binding dependency index out of range"))?{visit(value,sources,row,seen,w)?;}}},
   E::ArrayRead{states,index,..}=>{for &state in states{insert(&mut row.state_dependencies,state,w)?;}visit(index,sources,row,seen,w)?;},
   E::IntegerPrimitive{args,..}=>for n in args{integer(n,row,w)?;},
   E::UnsupportedSystemCall{seed,args,..}=>{insert(&mut row.state_dependencies,*seed,w)?;for e in args{visit(e,sources,row,seen,w)?;}},
   _=>calls::children(e,&mut |e|visit(e,sources,row,seen,w))?,
  }Ok(())
 }
 visit(e,sources,&mut row,&mut seen,w)?;
 row.mark_dependency_metadata();Ok(row)
}
