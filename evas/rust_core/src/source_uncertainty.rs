//! A scalar amplitude band is unrelated to an independent zero-error calendar.
//! This admission proves only direct source dependencies, never a state value.
use crate::{events::EventModel,ir::{Error,Expression as E,EventTrigger},pwl::Trajectory,transition_source_plan::Work};

fn guard_is_independent(e:&E,uncertain:&[Option<bool>],w:&Work,depth:usize)->Result<bool,Error>{
    w.step()?;
    if depth>128{return Ok(false);}
    Ok(match e{
        E::Affine{terms,..}=>{
            let mut independent=true;
            for term in terms{
                w.step()?;
                let source=uncertain.get(term.node).ok_or_else(||Error::new("invalid_ir","cross dependency node outside original table"))?;
                if term.coefficient!=0. && *source!=Some(false){independent=false;}
            }
            independent
        },
        E::Add{left,right}|E::Multiply{left,right}|E::Divide{left,right}=>{
            let a=guard_is_independent(left,uncertain,w,depth+1)?;
            let b=guard_is_independent(right,uncertain,w,depth+1)?;a&&b
        },
        E::Power{base,..}=>guard_is_independent(base,uncertain,w,depth+1)?,
        // State/local/call/selection and solved internal nodes do not carry an
        // original zero-error source-dependency certificate on this route.
        _=>false,
    })
}

pub(crate) fn validate_independent_cross(model:&EventModel,trajectory:&Trajectory)->Result<(),Error>{
    let Some(errors)=&trajectory.config.pwl_errors_v else{return Ok(());};
    if !model.program.operators.is_empty(){return Ok(());}
    let w=crate::real_expression::work(model);
    w.debit(2,(errors.len()*2+model.triggers.len()+16) as u64)?;
    if !errors.iter().any(|e|e.bound()>0.)
        || errors.iter().all(|e|e.bound()==0. || e.shape().is_some())
        || !model.triggers.iter().any(|leaf|matches!(leaf.trigger,EventTrigger::Cross{..}|EventTrigger::HeldTimer{..})){return Ok(());}
    w.debit(2,(model.program.nodes.len()*8+32) as u64)?;
    let mut uncertain=vec![None;model.program.nodes.len()];
    if let Some(ground)=uncertain.first_mut(){*ground=Some(false);}
    for (k,name) in model.driven.iter().enumerate(){
        w.step()?;let error=errors.get(k).ok_or_else(||Error::new("invalid_inputs","source uncertainty dimension mismatch"))?;
        let mut found=false;
        for (node,value) in model.program.nodes.iter().enumerate(){
            w.debit(2,(name.len()+value.len()+1) as u64)?;
            if name==value{uncertain[node]=Some(error.bound()>0.);found=true;break;}
        }
        if !found{return Err(Error::new("invalid_inputs","source uncertainty node absent"));}
    }
    for leaf in &model.triggers{
        w.step()?;
        let allowed=match &leaf.trigger{
            EventTrigger::Cross{guard,..}=>guard_is_independent(guard,&uncertain,w,0)?,
            EventTrigger::HeldTimer{..}=>false,
            EventTrigger::Timer{..}|EventTrigger::InitialStep{}|EventTrigger::FinalStep{}=>true,
            EventTrigger::Or{..}=>return Err(Error::new("invalid_ir","unflattened event uncertainty trigger")),
        };
        if !allowed{
            let origin=&model.program.events[leaf.event].origin;
            w.debit(2,((origin.source.len()+origin.instance.len())*2+256) as u64)?;
            return Err(Error::new("unsupported_source_uncertainty",format!("scalar source uncertainty requires a cross guard certified from independent zero-error driven inputs at {}",origin.label())));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests{
    use super::*;
    #[test]
    fn original_cross_admission_uses_its_existing_owner_and_failure_is_sticky(){
        let request:crate::ir::Request=serde_json::from_str(include_str!("../tests/source_uncertainty_original.request.json")).unwrap();
        let trajectory=Trajectory::new(request.transient.unwrap(),request.driven.len()).unwrap();
        let model=EventModel::new_with_trajectory(request.program,request.driven,request.tolerances,Some(&trajectory)).unwrap();
        let w=crate::real_expression::work(&model);let alias=w.clone();let before=w.spent();
        validate_independent_cross(&model,&trajectory).unwrap();
        assert!(w.same_owner(&alias));assert!(alias.spent()>before);
        assert!(w.debit(2,u64::MAX).is_err());
        assert_eq!(validate_independent_cross(&model,&trajectory).unwrap_err().kind,"step_budget");
        assert_eq!(validate_independent_cross(&model,&trajectory).unwrap_err().kind,"step_budget");
    }
}
