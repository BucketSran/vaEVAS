//! Private capability for constant-initial, direct held event source values.
//! Sharing payment never grants History admission or changes its semantics.
use crate::ir::{Error, EventTrigger, Expression as E, Program, Statement};
use crate::pwl::Trajectory;
use crate::transition_source_plan::{ProofContext, Work};
use std::sync::Arc;
#[path = "analytic_sampled_consumer.rs"]
mod sampled;
#[path = "analytic_sample_domain.rs"]
mod sample_domain;
fn scope(s: &str) -> Error {
    Error::new("unsupported_analytic_source_consumer", s)
}
pub(crate) struct Request {
    context: Arc<ProofContext>,
    sampled: Option<sampled::Admission>,
    domains: sample_domain::Cache,
}
/// Payment and original physical input mapping only. None of these variants
/// grants another variant's history, forcing, operator or native capability.
pub(crate) enum ProofOwner<'a> {
    History(&'a crate::history_admission::Admission),
    Analytic(&'a Request),
    ForcingCalendar(&'a crate::forcing_graph::Graph),
}
impl<'a> ProofOwner<'a> {
    pub(crate) fn work(self) -> &'a Work {
        match self {
            Self::History(a) => a.context.borrow_work(),
            Self::Analytic(a) => a.work(),
            Self::ForcingCalendar(g) => g.request_work(),
        }
    }
    pub(crate) fn input_nodes(self) -> &'a [usize] {
        match self {
            Self::History(a) => a.context.event_input_nodes(),
            Self::Analytic(a) => a.context.event_input_nodes(),
            Self::ForcingCalendar(g) => g.input_nodes(),
        }
    }
}
impl Copy for ProofOwner<'_> {}
impl Clone for ProofOwner<'_> {
    fn clone(&self) -> Self {
        *self
    }
}
pub(crate) fn proof_owner(model: &crate::events::EventModel) -> Option<ProofOwner<'_>> {
    match (&model.history_admission, &model.analytic_request) {
        (Some(a), None) => Some(ProofOwner::History(a)),
        (None, Some(a)) => {
            // Request::activate and the transient factory reject this mixture.
            // Never silently choose one ledger for two physical capabilities.
            assert!(
                model.forcing.is_none(),
                "analytic request cannot carry forcing"
            );
            Some(ProofOwner::Analytic(a))
        }
        (None, None) => model
            .forcing
            .as_ref()
            .filter(|g| g.requires_composed_history())
            .map(|g| ProofOwner::ForcingCalendar(g)),
        (Some(_), Some(_)) => unreachable!("distinct source capabilities cannot coexist"),
    }
}
impl Request {
    pub(crate) fn context(&self) -> &Arc<ProofContext> {
        &self.context
    }
    pub(crate) fn work(&self) -> &Work {
        self.context.borrow_work()
    }
    pub(crate) fn fixed_timer_held_transitions(&self) -> bool {
        self.sampled.is_some()
    }
    // Rational-domain memoization is private to the serial transient request.
    // Arc retains shared proof ownership; Rust still prevents sending this
    // RefCell-backed token to another thread.
    #[allow(clippy::arc_with_non_send_sync)]
    pub(crate) fn prepare(
        p: &Program,
        t: &Trajectory,
        driven: &[String],
    ) -> Result<Arc<Self>, Error> {
        let w = t
            .analytic_work()
            .ok_or_else(|| scope("missing original analytic request owner"))?;
        crate::analytic_source::charge_config(p, w)?;
        crate::analytic_source::charge_config(driven, w)?;
        if !p.operators.is_empty() {
            // Bind the original complete request before joint role admission.
            // The private token proves this bounded combination; sharing its
            // ledger does not grant History or observer-math capabilities.
            let bytes = crate::event_floor::encoded_size(p, w)?;
            let context = ProofContext::event_request_with_work(p, t, driven, bytes, w.clone())?;
            let sampled = sampled::Admission::qualify(p, &context)?;
            w.debit(2, (std::mem::size_of::<Self>() + 32) as u64)?;
            return Ok(Arc::new(Self {
                context,
                sampled: Some(sampled),
                domains: Default::default(),
            }));
        }
        if !p.operators.is_empty() || !p.step_bounds.is_empty() {
            return Err(scope("analytic event source values require direct held outputs without operators or bound_step"));
        }
        w.debit(
            2,
            (p.nodes.len() + p.states.len() + driven.len() + 8) as u64,
        )?;
        let mut input_nodes = Vec::with_capacity(driven.len());
        for name in driven {
            let mut found = None;
            for (index, node) in p.nodes.iter().enumerate() {
                w.debit(2, (node.len() + name.len() + 2) as u64)?;
                if node == name {
                    found = Some(index);
                    break;
                }
            }
            input_nodes.push(found.ok_or_else(|| scope("unknown original driven node"))?);
        }
        // The initial representation must survive resolve byte-for-byte.
        for state in &p.states {
            w.step()?;
            state.initial.constant().map_err(|_| {
                scope("analytic source initialization expressions are not yet certified")
            })?;
        }
        for c in &p.contributions {
            raw(&c.rhs, p, &input_nodes, false, t, w)?;
            crate::history_admission::affine_paid(&c.rhs, p, w)?;
        }
        for event in &p.events {
            w.step()?;
            match &event.trigger {
                EventTrigger::Cross{guard,..}=>{
                    raw(guard,p,&input_nodes,true,t,w)?;
                    crate::history_admission::affine_paid(guard,p,w)?;
                }
                EventTrigger::Timer{..}|EventTrigger::InitialStep {}=>(),
                _=>return Err(scope("analytic source-value calendar currently accepts independent PWL cross or fixed timer leaves")),
            }
            for statement in &event.body {
                w.step()?;
                match statement {
                    Statement::Assign(assignment)=>{
                        let rhs=&assignment.rhs;
                        raw(rhs,p,&input_nodes,false,t,w)?;
                        let dynamic = scalar_shape(rhs, w)?;
                        if matches!(event.trigger, EventTrigger::InitialStep {}) && dynamic {
                            return Err(scope("analytic initial event requires constant source assignments"));
                        }
                    }
                    _=>return Err(scope("analytic source-value event body requires direct affine assignments; every hidden arm is audited")),
                }
            }
        }
        let bytes = crate::event_floor::encoded_size(p, w)?;
        let context = ProofContext::event_request_with_work(p, t, driven, bytes, w.clone())?;
        w.debit(2, (std::mem::size_of::<Self>() + 32) as u64)?;
        Ok(Arc::new(Self {
            context,
            sampled: None,
            domains: Default::default(),
        }))
    }
    pub(crate) fn sample_domain(
        &self, index:usize, p:&Program, trajectory:&Trajectory,
        root:&crate::exact_source::RootTime, w:&Work,
    )->Result<Option<std::sync::Arc<crate::source_domain::Domain>>,Error>{
        if !self.work().same_owner(w){return Err(scope("analytic source domain belongs to another request"));}
        let Some(&node)=self.context.event_input_nodes().get(index) else{return Ok(None)};
        if !sample_domain::read_node(p,node,w)? {return Ok(None);}
        let Some(Some(source))=trajectory.config.analytic_sources.get(index) else{return Ok(None)};
        let error=trajectory.config.pwl_errors_v.as_ref().and_then(|errors|errors.get(index)).map_or(0.,crate::ir::SourceError::bound);
        self.domains.at_root(index,source,error,root,w)
    }
    pub(crate) fn activate(
        self: &Arc<Self>,
        mut model: crate::events::EventModel,
        t: &Trajectory,
    ) -> Result<crate::events::EventModel, Error> {
        crate::event_floor::check_provided_binding(
            &self.context,
            &model.program,
            t,
            &model.driven,
        )?;
        if model.history_admission.is_some()
            || model.forcing.is_some()
            || model.floor_source.is_some()
        {
            return Err(scope(
                "analytic request cannot grant another physical capability",
            ));
        }
        let actual = model
            .source_context
            .as_ref()
            .ok_or_else(|| scope("analytic request lost original source binding"))?;
        if !Arc::ptr_eq(actual, &self.context) {
            return Err(scope("analytic request changed original proof context"));
        }
        model.analytic_request = Some(self.clone());
        Ok(model)
    }
}
/// Retain original dependencies before arithmetic simplification, including zero
/// coefficients and all syntactic children. Guards never read an analytic input.
fn raw(
    e: &E,
    p: &Program,
    inputs: &[usize],
    guard: bool,
    t: &Trajectory,
    w: &Work,
) -> Result<(), Error> {
    w.step()?;
    match e {
        E::Affine{constant,terms}=>{
            if !constant.is_finite(){return Err(scope("nonfinite source expression"));}
            for (j,term) in terms.iter().enumerate() {
                w.debit(2,(inputs.len()+j+2) as u64)?;
                if terms[..j].iter().any(|other|other.node==term.node){return Err(scope("duplicate original affine dependency"));}
                if !term.coefficient.is_finite() || term.node>=p.nodes.len(){return Err(scope("unknown original dependency"));}
                if term.node==0{continue;}
                let k=inputs.iter().position(|&n|n==term.node).ok_or_else(||scope("analytic source-value scope excludes internal voltage dependencies"))?;
                if guard && t.config.analytic_sources[k].is_some(){return Err(scope("sine cross guards require an independent complete root certificate"));}
                if guard && t.config.pwl_errors_v.as_ref().and_then(|errors|errors.get(k)).is_some_and(|error|error.bound()>0.) {return Err(scope("analytic source calendar requires independent zero-error PWL guard dependencies"));}
            }
        }
        E::State{state} if !guard=>{if *state>=p.states.len(){return Err(scope("unknown original state dependency"));}},
        E::Add{left,right}|E::Multiply{left,right}|E::Divide{left,right}=>{raw(left,p,inputs,guard,t,w)?;raw(right,p,inputs,guard,t,w)?;}
        E::Power{base,..}=>raw(base,p,inputs,guard,t,w)?,
        E::RealBoundary { value, .. } if !guard => raw(value,p,inputs,false,t,w)?,
        E::RealBinary { left, right, .. } if !guard => {raw(left,p,inputs,false,t,w)?;raw(right,p,inputs,false,t,w)?;}
        _=>return Err(scope("analytic source-value expression is outside direct affine scope; hidden arms remain unsupported")),
    }
    Ok(())
}

// A role audit only: the original rounded tree stays in the bound Program.
// No row returned here is a mathematical certificate for a rounded operation.
fn scalar_shape(e: &E, w: &Work) -> Result<bool, Error> {
    w.step()?;
    Ok(match e {
        E::Affine { terms, .. } => {
            let mut dynamic=false;
            for term in terms {w.step()?;dynamic |= term.node!=0 && term.coefficient!=0.;}
            dynamic
        }
        E::State { .. } => true,
        E::RealBoundary { value, .. } => scalar_shape(value,w)?,
        E::Add { left,right } | E::Multiply { left,right } | E::Divide { left,right }
        | E::RealBinary { left,right,.. } => {
            let a=scalar_shape(left,w)?;let b=scalar_shape(right,w)?;
            let multiply=matches!(e,E::Multiply {..}|E::RealBinary {operation:crate::ir::RealOperation::Multiply,..});
            let divide=matches!(e,E::Divide {..}|E::RealBinary {operation:crate::ir::RealOperation::Divide,..});
            if b && (divide || multiply && a) {return Err(scope("analytic scalar source tree requires affine physical leaves"));}
            a||b
        }
        E::Power { .. } => return Err(scope("analytic scalar source tree requires the original affine arithmetic roles")),
        _=>return Err(scope("analytic scalar source tree contains an unsupported role")),
    })
}
