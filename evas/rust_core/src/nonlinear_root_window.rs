//! Certified differential-inclusion history across an isolated source root.
//! The full root certificate is retained even when this epoch ends inside it.
use super::*;

#[derive(Clone, PartialEq)]
struct RootWindow {
    certificate: I,
    parameters: Vec<I>,
    initial: Vec<I>,
    tube: Vec<I>,
    velocity: Vec<I>,
}
#[derive(Clone, PartialEq)]
enum StepKind {
    Taylor(DenseStep),
    Root(RootWindow),
}
#[derive(Clone, PartialEq)]
pub(super) struct HistoryStep {
    pub(super) start: f64,
    pub(super) end: f64,
    kind: StepKind,
}
impl HistoryStep {
    pub(super) fn taylor(step: DenseStep) -> Self {
        Self { start:step.start,end:step.end,kind:StepKind::Taylor(step) }
    }
    pub(super) fn is_root(&self) -> bool { matches!(self.kind,StepKind::Root(_)) }
    pub(super) fn root_velocity(&self) -> Option<&[I]> {
        match &self.kind { StepKind::Root(r)=>Some(&r.velocity),_=>None }
    }
    pub(super) fn range(&self,time:I)->Vec<I> {
        match &self.kind {
            StepKind::Taylor(step)=>step.range(time),
            StepKind::Root(root)=>{
                // Every physical elapsed time is nonnegative. Outward rounding
                // may give a negative subnormal at an exact zero subtraction.
                let elapsed=time-I::point(self.start);
                let elapsed=I{lo:elapsed.lo.max(0.),hi:elapsed.hi};
                root.initial.iter().zip(&root.velocity).map(|(&x,&d)| x+elapsed*d).collect()
            }
        }
    }
    pub(super) fn centered_range(&self,h:I,tail:bool)->Option<Vec<CenterValue>> {
        match &self.kind { StepKind::Taylor(s)=>s.centered_range(h,tail),_=>None }
    }
}

pub(super) fn compatible(a:&NonlinearContinuous,b:&NonlinearContinuous,seed:&[I])->bool {
    a.implicit.is_none() && b.implicit.is_none()
        && a.initial==seed && b.initial==seed
        && a.parameters==b.parameters && a.context.driven==b.context.driven
        && a.functions.len()==seed.len() && b.functions.len()==seed.len()
        && a.values==b.values && a.accuracy_rows==b.accuracy_rows && a.math_outputs==b.math_outputs
        && a.operators.len()==b.operators.len()
        && a.operators.iter().zip(&b.operators).all(|(a,b)| {
            a.operator==b.operator && a.kind==b.kind && a.origin==b.origin
                && a.states==b.states && a.held_reset==b.held_reset
                && match (&a.laplace,&b.laplace) {
                    (None,None)=>true,
                    (Some(a),Some(b))=>a.a==b.a && a.b==b.b && a.c==b.c && a.d==b.d,
                    _=>false,
                }
        })
}
impl NonlinearContinuous {
    pub(super) fn switched_enclosure(fields:&[&Self],seed:&[I],source:&[I],span:I,elapsed:I,
        remaining_work:&mut usize,work_limit:usize)->Result<(Vec<I>,Vec<I>),Error> {
        let fail=|s|Error::new("condition_precision",s);
        if fields.is_empty() || fields.len()>32 || elapsed.lo<0. || !elapsed.finite() {
            return Err(fail("switched enclosure requires a complete bounded field set"));
        }
        let mut evaluate=|state:&[I]| -> Result<Vec<I>,Error> {
            let variables:Vec<_>=state.iter().chain(source).map(|&v|vec![v]).collect();
            let mut derivatives=Vec::new();
            for mode in fields {
                Self::charge_trial(remaining_work,span.lo,span.hi,work_limit)?;
                let rows=mode.derivative_jets(&variables,&[],0).ok_or_else(||fail("root-window field unavailable"))?;
                if rows.iter().any(|r|r.is_empty() || !r[0].finite()) { return Err(fail("root-window field is nonfinite")); }
                derivatives.push(rows.into_iter().map(|r|r[0]).collect::<Vec<_>>());
            }
            let mut result=derivatives.remove(0);
            for field in derivatives { for (x,d) in result.iter_mut().zip(field) { *x=x.hull(d); } }
            Ok(result)
        };
        let mut velocity=evaluate(seed)?;
        let mut previous=seed.to_vec();
        let mut proof=None;
        for _ in 0..TUBE_ATTEMPTS {
            let tube:Vec<_>=seed.iter().zip(&velocity).zip(&previous).map(|((&x,&d),&prior)| {
                let radius=(I::point(elapsed.hi)*I::point(d.magnitude().max(1e-15))*I::point(2.)).hi;
                let z=(x+I{lo:-radius,hi:radius}).hull(prior);
                I{lo:z.lo.next_down(),hi:z.hi.next_up()}
            }).collect();
            if tube.iter().any(|v|!v.finite()) { break; }
            velocity=evaluate(&tube)?;
            let image:Vec<_>=seed.iter().zip(&velocity).map(|(&x,&d)|x+elapsed*d).collect();
            if image.iter().zip(&tube).all(|(x,z)| x.finite() && x.lo>z.lo && x.hi<z.hi) {
                proof=Some(tube);break;
            }
            previous=tube.iter().zip(image).map(|(&z,x)|z.hull(x)).collect();
        }
        let tube=proof.ok_or_else(||fail("switched differential inclusion has no certified tube"))?;
        Ok((tube,velocity))
    }
    pub(super) fn root_window_mode(&self,root:I,span:I,seed:&[I],remaining_work:&mut usize)->Result<Self,Error> {
        let fail=|s|Error::new("condition_precision",s);
        let [left,right]=selection::isolated_root_witnesses(&self.context,&self.parameters,root)?;
        if !root.finite() || root.lo>=root.hi || !span.finite() || span.lo>=span.hi || span.lo<root.lo
            || span.hi>root.hi || left<0. || right>self.context.trajectory.config.stop {
            return Err(fail("root window lacks physical two-sided witnesses"));
        }
        let compile=|time| Self::initialized(
            selection::freeze_context(&self.context,&self.parameters,time)?,
            self.parameters.clone(),span.lo,Some(seed.to_vec()),&self.tolerances);
        let mut old=compile(left)?;let post=compile(right)?;
        if !compatible(&old,&post,seed) {
            return Err(fail("root-window modes do not share state and output coordinates"));
        }
        let source=self.context.trajectory.range(span)?.0;
        // Keep the same source-domain checks as an ordinary Taylor step.
        let coordinates=|sources:Vec<I>| seed.iter().copied().chain(sources).map(|v|vec![v]).collect::<Vec<_>>();
        let source_left=coordinates(self.context.trajectory.value_bounds(span.lo));
        let source_right=coordinates(self.context.trajectory.value_bounds(span.hi));
        let source_tube=coordinates(source.clone());
        for field in [&old,&post] {
            for f in &field.functions { f.certify_source_denominators(seed.len(),&source_left,&source_right,&source_tube)?; }
        }
        let elapsed=I{lo:0.,hi:(I::point(span.hi)-I::point(span.lo)).hi};
        let (tube,velocity)=Self::switched_enclosure(&[&old,&post],seed,&source,span,elapsed,remaining_work,self.step_budget())?;
        let variables:Vec<_>=tube.iter().chain(&source).map(|&v|vec![v]).collect();
        let mut cap=self.context.trajectory.config.max_step;
        for field in [&old,&post] {
            for (active,value) in &field.step_bounds {
                let active=active.jet(&variables,0)[0];
                if !active.finite() { return Err(fail("root-window timestep activation is not finite")); }
                if active.zero() { continue; }
                let bound=value.jet(&variables,0)[0];
                if !bound.finite() || bound.lo<0. {
                    return Err(Error::new("invalid_bound_step","root-window timestep request is negative or nonfinite"));
                }
                cap=cap.min(bound.lo);
            }
        }
        if elapsed.hi>cap {
            return Err(Error::new("waveform_accuracy","root-window span exceeds the certified timestep cap"));
        }
        // The interval extension is retained for every dense query, not only
        // the restart seed. Do not intersect an empty box or choose a side.
        let step=HistoryStep{start:span.lo,end:span.hi,kind:StepKind::Root(RootWindow{
            certificate:root,parameters:self.parameters.clone(),initial:seed.to_vec(),tube,velocity,
        })};
        let endpoint=step.range(I::point(span.hi));
        if old.accuracy_ratio(&endpoint,&old.context.trajectory.value_bounds(span.hi),false)>1. {
            return Err(Error::new("waveform_accuracy","root-window endpoint exceeds the unchanged voltage budget"));
        }
        old.steps=Arc::new(vec![step]);
        Ok(old)
    }
}
