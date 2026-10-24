//! Optional exact values local to one event-path proof. Unknown incoming boxes
//! remain unknown; rational certificates never replace inherited uncertainty.
use crate::exact_source::{binary, enclosure, Budget};
use crate::interval::Interval as I;
use crate::ir::{EventMathFunction as F, Expression as E};
use num_rational::BigRational as R;
use num_traits::{Signed, Zero};
#[path = "event_history_proof.rs"]
pub(crate) mod history;

pub(crate) type Proofs = std::collections::BTreeMap<usize, R>;

pub(crate) fn binary_state_identity(value:&R,point:f64,w:&crate::transition_source_plan::Work)->Result<bool,crate::ir::Error>{
    w.debit(2,0)?;w.debit(2,8)?;
    if !point.is_finite()||!value.denom().is_positive(){return Ok(false);}
    if point==0.{return Ok(value.is_zero()&&value.denom().bits()==1);}
    if value.is_zero()||value.numer().is_negative()!=point.is_sign_negative(){return Ok(false);}
    let raw=point.to_bits();let exponent=((raw>>52)&2047)as i64;
    let mantissa=(raw&((1u64<<52)-1))|if exponent==0{0}else{1u64<<52};
    let zeros=mantissa.trailing_zeros();let significant=mantissa>>zeros;
    let power=if exponent==0{-1074}else{exponent-1023-52}+i64::from(zeros);
    let numerator_shift=power.max(0)as u64;let denominator_shift=(-power).max(0)as u64;
    let bits=u64::from(64-significant.leading_zeros());
    let numerator=value.numer().magnitude();let denominator=value.denom().magnitude();
    w.debit(2,numerator.bits().div_ceil(64)+denominator.bits().div_ceil(64)+bits+16)?;
    if numerator.bits()!=bits+numerator_shift||denominator.bits()!=denominator_shift+1||numerator.trailing_zeros()!=Some(numerator_shift)||denominator.trailing_zeros()!=Some(denominator_shift){return Ok(false);}
    for bit in 0..bits{if numerator.bit(numerator_shift+bit)!=((significant>>bit)&1!=0){return Ok(false);}}
    Ok(true)
}

#[derive(Clone)]
pub(crate) struct NominalFrame{pub states:Vec<f64>,pub operators:Vec<f64>,pub inputs:Vec<f64>}
pub(crate) struct Context<'a> {
    states: &'a Proofs,
    rooted_occurrence: bool,
    nominal_frame:Option<std::sync::Arc<NominalFrame>>,
    nodes: Vec<Option<R>>,
    operators: Vec<I>,
    floor_work: Option<crate::transition_source_plan::Work>,
    history_work: Option<crate::transition_source_plan::Work>,
    floor_bounds: Option<Vec<I>>,
    source_domains: Option<std::sync::Arc<crate::source_domain::Sources>>,
}
impl<'a> Context<'a> {
    pub(crate) fn candidate_frame(proofs:&'a Proofs,node_count:usize,states:&[f64],operators:&[f64],work:&crate::transition_source_plan::Work)->Result<Self,crate::ir::Error>{
        work.debit(2,((node_count+states.len()+operators.len())*64+64) as u64)?;
        Ok(Self{states:proofs,rooted_occurrence:false,nominal_frame:Some(std::sync::Arc::new(NominalFrame{states:states.to_vec(),operators:operators.to_vec(),inputs:Vec::new()})),nodes:vec![None;node_count],operators:operators.iter().copied().map(I::point).collect(),floor_work:None,history_work:Some(work.clone()),floor_bounds:None,source_domains:None})
    }

    // Identity, not equality: two different accepted Frames can contain two
    // distinct exact rationals inside the same outward-rounded interval.
    pub(crate) fn rooted_occurrence(&self)->bool{self.rooted_occurrence}
    pub(crate) fn nominal_frame(&self)->Option<&NominalFrame>{self.nominal_frame.as_deref()}
    pub(crate) fn set_candidate_frame(&mut self,states:&[f64],operators:&[f64],inputs:&[f64],ordered:bool)->Result<(),crate::ir::Error>{
        if let Some(w)=self.execution_work(){w.debit(2,((states.len()+operators.len()+inputs.len())*8+32) as u64)?;}
        self.nominal_frame=Some(std::sync::Arc::new(NominalFrame{states:states.to_vec(),operators:operators.to_vec(),inputs:inputs.to_vec()}));
        self.rooted_occurrence=ordered;Ok(())
    }
    pub(crate) fn execution_work(&self)->Option<&crate::transition_source_plan::Work>{self.history_work.as_ref().or(self.floor_work.as_ref())}
    pub(crate) fn proof_identity(&self) -> *const Proofs {
        self.states as *const Proofs
    }

    pub(crate) fn floor_work(&self) -> Option<&crate::transition_source_plan::Work> {
        self.floor_work.as_ref()
    }

    pub(crate) fn try_new(
        model:&crate::events::EventModel, trajectory:&crate::pwl::Trajectory,
        inputs:&[I], states:&'a Proofs, root:Option<&crate::exact_source::RootTime>,
    )->Result<Self,crate::ir::Error>{
        let mut result=Self::try_new_base(model,trajectory,inputs,states,root)?;

        if let Some(root)=root{
            let w=crate::real_expression::work(model);
            w.debit(2,(model.program.nodes.len()*16+64) as u64)?;
            let mut bands=vec![None;model.program.nodes.len()];let mut any=false;
            for (k,name) in model.driven.iter().enumerate(){
                w.step()?;let band=trajectory.sample_domain_at_root(k,root,w)?;
                let band=match band {Some(band)=>Some(band),None=>match &model.analytic_request {
                    Some(request)=>request.sample_domain(k,&model.program,trajectory,root,w)?,None=>None,
                }};
                let Some(band)=band else{continue;};
                let Some(bounds)=inputs.get(k) else{continue;};if !band.contained(*bounds,w)?{continue;}
                let mut index=None;
                for (n,node) in model.program.nodes.iter().enumerate(){w.debit(2,(node.len()+name.len()+1) as u64)?;if node==name{index=Some(n);break;}}
                let node=index.ok_or_else(||crate::ir::Error::new("invalid_ir","source domain input node absent"))?;
                result.nodes[node]=None;bands[node]=Some(band);any=true;
            }
            if any{result.source_domains=Some(crate::source_domain::Sources::new(bands,w)?);}
        }
        if root.is_some() && !model.program.procedures.is_empty() && model.forcing.is_none() && model.dc_projection.is_none() {
            let owner=result.execution_work().unwrap_or_else(||crate::real_expression::work(model));
            owner.debit(2,16)?;let owner=owner.clone();let w=&owner;
            if model.independent_physical.get().is_none() {
                w.debit(2,(model.driven.len()*8+32) as u64)?;
                let mut driven=Vec::with_capacity(model.driven.len());
                for name in &model.driven {
                    let mut found=None;
                    for (index,node) in model.program.nodes.iter().enumerate(){
                        w.debit(2,(name.len()+node.len()+1) as u64)?;
                        if node==name {found=Some(index);break;}
                    }
                    driven.push(found.ok_or_else(||crate::ir::Error::new("invalid_ir","physical projection source absent"))?);
                }
                let projection=crate::procedure_affine::project(&model.program,&driven,w)?;
                let projection=projection.map(|p|{w.debit(2,96)?;Ok::<_,crate::ir::Error>(std::sync::Arc::new(p))}).transpose()?;
                let _=model.independent_physical.set(projection);
            }
            if let Some(projection)=model.independent_physical.get().and_then(Option::as_ref) {
                w.debit(2,16)?;
                if !projection.owner.same_owner(w){return Err(crate::ir::Error::new("invalid_ir","physical projection belongs to another request"));}
                for (node,row) in projection.rows.iter().enumerate() {
                    w.step()?;
                    if result.nodes[node].is_some(){continue;}
                    let mut independent=true;
                    for value in &row[projection.opaque_start..row.len()-1]{w.step()?;if !value.is_zero(){independent=false;break;}}
                    if !independent {continue;}
                    let mut paid=crate::exact_source::history_paid::Paid::new(w);
                    let value=(||{
                        let mut sum=paid.copy(row.last()?)?;
                        for (&input,coefficient) in projection.driven.iter().zip(row) {
                            paid.pay(1)?;
                            if coefficient.is_zero(){continue;}
                            let value=result.nodes.get(input)?.as_ref()?;
                            let product=paid.op(coefficient,value,'*')?;
                            sum=paid.op(&sum,&product,'+')?;
                        }
                        Some(sum)
                    })();
                    result.nodes[node]=paid.finish(value)?;
                }
            }
        }
        Ok(result)
    }
    fn try_new_base(
        model: &crate::events::EventModel,
        trajectory: &crate::pwl::Trajectory,
        inputs: &[I],
        states: &'a Proofs,
        root: Option<&crate::exact_source::RootTime>,
    ) -> Result<Self, crate::ir::Error> {
        if crate::analytic_request::proof_owner(model).is_some() {
            return history::context_new(model, trajectory, inputs, states, root);
        }
        if let Some(request) = &model.floor_source {
            request.check_source(trajectory)?;
            // Context::new invokes at_root at most once per actual driven input.
            // The helper keeps its local200000 cap, reserved before invocation.
            if root.is_some() {
                crate::event_floor::charge(
                    request.work(),
                    model.driven.len().saturating_add(1).saturating_mul(8),
                    "floor_source_binding_scan",
                )?;
                let calls = trajectory
                    .exact_sources
                    .iter()
                    .zip(inputs)
                    .take(model.driven.len())
                    .filter(|(source, bounds)| {
                        source.is_some() && !(bounds.finite() && bounds.lo == bounds.hi)
                    })
                    .count();
                crate::event_floor::charge(
                    request.work(),
                    200000 * calls,
                    "floor_source_helper_reservations",
                )?;
                crate::diagnostics::counter("floor_source_helper_calls", calls);
            }
            crate::event_floor::charge(
                request.work(),
                144 * (model.program.nodes.len() + states.len() + inputs.len() + 1),
                "floor_source_copy",
            )?;
            crate::event_floor::charge(
                request.work(),
                1024 * (states.len() + inputs.len()),
                "floor_source_exact_enclosure",
            )?;
        }
        let indices = model
            .floor_source
            .as_ref()
            .map(|r| r.input_nodes())
            .transpose()?;
        let mut result = if indices.is_some() {
            Self::build(model, trajectory, inputs, states, root, indices)
        } else {
            Self::new(model, trajectory, inputs, states, root)
        };
        result.floor_work = model.floor_source.as_ref().map(|r| r.work().clone());
        if result.floor_work.is_some() {
            let mut b = vec![
                I {
                    lo: f64::NEG_INFINITY,
                    hi: f64::INFINITY
                };
                model.program.nodes.len()
            ];
            b[0] = I::ZERO;
            for (&node, &v) in indices.unwrap().iter().zip(inputs) {
                b[node] = v;
            }
            result.floor_bounds = Some(b);
        }
        if !model.program.procedures.is_empty() && result.history_work.is_none() && result.floor_work.is_none(){
            let w=crate::real_expression::work(model);
            w.debit(2,model.source_copy_items as u64)?;
            result.history_work=Some(w.clone());
        }
        Ok(result)
    }
    pub(crate) fn try_with_operators(&self, operators: &[I]) -> Result<Self, crate::ir::Error> {
        if self.history_work.is_some() {
            return history::context_operators(self, operators);
        }
        if let Some(w) = &self.floor_work {
            crate::event_floor::charge(
                w,
                self.nodes.len().saturating_add(1),
                "floor_source_binding_scan",
            )?;
            let limbs = self
                .nodes
                .iter()
                .flatten()
                .map(|r| 1 + (r.numer().bits() + r.denom().bits()).div_ceil(64) as usize)
                .sum::<usize>();
            crate::event_floor::charge(
                w,
                limbs + operators.len() + self.nodes.len() * 2 + 1,
                "floor_source_copy",
            )?;
        }
        if let Some(bands)=&self.source_domains{bands.share_cost()?;}
        Ok(self.with_operators(operators))
    }

    pub(crate) fn with_operators(&self, operators: &[I]) -> Self {
        Self {
            states: self.states,
            rooted_occurrence:self.rooted_occurrence,
            nominal_frame:self.nominal_frame.clone(),
            nodes: self.nodes.clone(),
            operators: operators.to_vec(),
            floor_work: self.floor_work.clone(),
            history_work: self.history_work.clone(),
            floor_bounds: self.floor_bounds.clone(),
            source_domains:self.source_domains.clone(),
        }
    }
    pub(crate) fn operators(&self) -> &[I] {
        &self.operators
    }
    pub(crate) fn new(
        model: &crate::events::EventModel,
        trajectory: &crate::pwl::Trajectory,
        inputs: &[I],
        states: &'a Proofs,
        root: Option<&crate::exact_source::RootTime>,
    ) -> Self {
        Self::build(model, trajectory, inputs, states, root, None)
    }
    fn build(
        model: &crate::events::EventModel,
        trajectory: &crate::pwl::Trajectory,
        inputs: &[I],
        states: &'a Proofs,
        root: Option<&crate::exact_source::RootTime>,
        indices: Option<&[usize]>,
    ) -> Self {
        let mut nodes = vec![None; model.program.nodes.len()];
        nodes[0] = binary(0.);
        for (k, (name, &bounds)) in model.driven.iter().zip(inputs).enumerate() {
            // A finite inherited singleton already certifies this exact binary
            // value. The old root result could only be used if enclosed by
            // that same singleton, so both rational values would be equal.
            // Restrict this order to the source Floor consumer. Nonpoint boxes
            // and every legacy caller retain their original root proof.
            let value = if indices.is_some() && bounds.finite() && bounds.lo == bounds.hi {
                point(bounds)
            } else {
                root.and_then(|r| trajectory.exact_sources.get(k)?.as_ref()?.at_root(r))
                    .filter(|v| {
                        enclosure(v).is_some_and(|i| bounds.lo <= i.lo && i.hi <= bounds.hi)
                    })
                    .or_else(|| point(bounds))
            };
            let node = indices.map_or_else(
                || model.program.nodes.iter().position(|n| n == name).unwrap(),
                |indices| indices[k],
            );
            nodes[node] = value;
        }
        Self {
            states,
            rooted_occurrence:false,
            nominal_frame:None,
            nodes,
            operators: Vec::new(),
            floor_work: None,
            history_work: None,
            floor_bounds: None,
            source_domains:None,
        }
    }
}

#[derive(Clone)]
pub(crate) struct LocalState {
    bounds: Vec<I>,
    exact: Vec<Option<R>>,
    nodes: Option<Vec<Option<R>>>,
    floor_work: Option<crate::transition_source_plan::Work>,
    history_work: Option<crate::transition_source_plan::Work>,
    floor_bounds: Option<Vec<I>>,
    source_domains: Option<std::sync::Arc<crate::source_domain::Sources>>,
}
impl std::ops::Deref for LocalState {
    type Target = [I];
    fn deref(&self) -> &[I] {
        &self.bounds
    }
}
impl LocalState {
    /// Only the strict point-lineage consumer supplies these source proofs.
    /// Unlike legacy constructors, singleton bounds do not manufacture proof.
    pub(crate) fn strict_point_lineage(
        bounds: &[I],
        proofs: &Proofs,
        nodes: Vec<Option<R>>,
        work: &crate::transition_source_plan::Work,
    ) -> Result<Option<Self>, crate::ir::Error> {
        work.debit(
            2,
            (16 + bounds.len() * 4 + nodes.len() * 2 + proofs.len() * 4) as u64,
        )?;
        for value in proofs.values() {
            work.step()?;
            let bits = value.numer().bits().saturating_add(value.denom().bits());
            work.debit(2, 1 + bits.div_ceil(64))?;
            if value.numer().bits() > crate::exact_source::MAX_BITS
                || value.denom().bits() > crate::exact_source::MAX_BITS
            {
                return Ok(None);
            }
        }
        if !valid_with_work(proofs, bounds, work)? {
            return Ok(None);
        }
        let mut exact = vec![None; bounds.len()];
        for (&state, value) in proofs {
            // All limb copying was reserved before cloning or allocating.
            exact[state] = Some(value.clone());
        }
        Ok(Some(Self {
            bounds: bounds.to_vec(),
            exact,
            nodes: Some(nodes),
            floor_work: None,
            history_work: None,
            floor_bounds: None,
            source_domains:None,
        }))
    }

    fn prepay_copy(&self) -> Result<(), crate::ir::Error> {
        if let Some(bands)=&self.source_domains{bands.share_cost()?;}
        if self.history_work.is_some() {
            return history::charge_local_copy(self);
        }
        if let Some(w) = &self.floor_work {
            let mut items = 16
                + self.bounds.len() * 4
                + self.exact.len()
                + self.nodes.as_ref().map_or(0, Vec::len)
                + self.floor_bounds.as_ref().map_or(0, Vec::len);
            for r in self
                .exact
                .iter()
                .flatten()
                .chain(self.nodes.iter().flatten().flatten())
            {
                crate::event_floor::charge(w, 1, "floor_source_ast")?;
                items += 8 + (r.numer().bits() + r.denom().bits()).div_ceil(64) as usize;
            }
            crate::event_floor::charge(w, items, "floor_source_copy")?;
        }
        Ok(())
    }
    pub(crate) fn try_clone(&self) -> Result<Self, crate::ir::Error> {
        self.prepay_copy()?;
        Ok(self.clone())
    }
    /// Reuse only this input frame's paid state proof. Bounds alone do not
    /// imply identity: mutable legacy frames can retain their previous bounds.
    pub(crate) fn try_point_state(&self,state:usize,point:f64,bound:I,w:&crate::transition_source_plan::Work)->Result<Option<R>,crate::ir::Error>{
        w.debit(2,0)?;w.debit(2,8)?;
        if !self.history_work.as_ref().is_some_and(|owner|owner.same_owner(w)) || !point.is_finite(){return Ok(None);}
        let same=|b:I|b.lo.to_bits()==point.to_bits()&&b.hi.to_bits()==point.to_bits();
        if !same(bound)||!self.bounds.get(state).is_some_and(|b|same(*b)){return Ok(None);}
        let Some(value)=self.exact.get(state).and_then(Option::as_ref)else{return Ok(None);};
        if !binary_state_identity(value,point,w)?{return Ok(None);}
        let mut paid=crate::exact_source::history_paid::Paid::new(w);let copy=paid.copy(value);paid.finish(copy)
    }

    /// A solver's private hypothesis domain. It is never installed in the
    /// accepted Context or promoted into exact node proofs. Only a separate
    /// complete RN-cell verifier can certify the resulting physical root.
    pub(crate) fn try_candidate_domains(
        &self, bands: Vec<Option<std::sync::Arc<crate::source_domain::Domain>>>,
        w: &crate::transition_source_plan::Work,
    ) -> Result<Self, crate::ir::Error> {
        for owner in [&self.floor_work,&self.history_work].into_iter().flatten() {
            if !owner.same_owner(w) {return Err(crate::ir::Error::new("invalid_ir","candidate cell belongs to another request"));}
        }
        w.debit(2,((self.bounds.len()+self.exact.len()+bands.len())*32+128) as u64)?;
        let mut exact=Vec::with_capacity(self.exact.len());
        for value in &self.exact {
            w.step()?;
            let mut paid=crate::exact_source::history_paid::Paid::new(w);
            let copy=match value {Some(r)=>{let copy=paid.copy(r);Some(paid.finish(copy)?.ok_or_else(||crate::ir::Error::new("waveform_accuracy","candidate state proof exceeds rational limit"))?)},None=>None};
            exact.push(copy);
        }
        let count=bands.len();
        Ok(Self{bounds:self.bounds.clone(),exact,nodes:Some(vec![None;count]),floor_work:Some(w.clone()),history_work:Some(w.clone()),floor_bounds:None,source_domains:Some(crate::source_domain::Sources::new(bands,w)?)})
    }
    pub(crate) fn source_domain(&self,constant:f64,terms:&[crate::ir::Term],bounds:&[I],w:&crate::transition_source_plan::Work)->Result<Option<std::sync::Arc<crate::source_domain::Domain>>,crate::ir::Error>{

        crate::source_domain::Sources::affine(self.source_domains.as_deref(),constant,terms,self.nodes.as_deref().unwrap_or(&[]),bounds,w)
    }
    pub(crate) fn try_value(&self, e: &E, nodes: &[I]) -> Result<Option<R>, crate::ir::Error> {
        if let Some(w) = self.history_work.as_ref() {
            return history::value(self, e, nodes, w);
        }
        let Some(w) = &self.floor_work else {
            return Ok(self.value(e, nodes));
        };
        // Retain the old exact evaluator's local cap. Prepay every rational
        // clone it can perform before invoking it, including state/source limbs.
        let size = crate::event_floor::encoded_size(e, w)?;
        crate::event_floor::charge(w, size * 144, "floor_source_copy")?;
        self.value_with_work(e, nodes, &mut || {
            crate::event_floor::charge(w, 1, "floor_source_exact_ops").ok()
        })
        .map_err(|_| crate::ir::Error::new("step_budget", "source floor provenance work exhausted"))
    }
    pub(crate) fn prepay_comparison(&self, other: &Self) -> Result<(), crate::ir::Error> {
        if self.history_work.is_some() {
            return history::charge_local_comparison(self, other);
        }
        if let Some(w) = &self.floor_work {
            crate::event_floor::charge(
                w,
                144 * (self.len() + other.len() + 1),
                "floor_source_identity_debit",
            )?;
        }
        Ok(())
    }
    pub(crate) fn history_work(&self) -> Option<&crate::transition_source_plan::Work> {
        self.history_work.as_ref()
    }
    pub(crate) fn try_enclosure(&self, value: &R) -> Result<Option<I>, crate::ir::Error> {
        if let Some(w) = &self.history_work {
            crate::exact_source::enclosure_with_work(value, w)
        } else {
            Ok(enclosure(value))
        }
    }
    pub(crate) fn floor_bound(&self, n: usize) -> Option<I> {
        self.floor_bounds.as_ref()?.get(n).copied()
    }
    pub(crate) fn floor_work(&self) -> Option<&crate::transition_source_plan::Work> {
        self.floor_work.as_ref()
    }
    pub(crate) fn floor_node(&self, n: usize) -> Option<&R> {
        self.nodes.as_ref()?.get(n)?.as_ref()
    }
    pub(crate) fn try_with_context(
        bounds: &[I],
        context: Option<&Context<'_>>,
    ) -> Result<Self, crate::ir::Error> {
        if context.is_some_and(|c| c.history_work.is_some()) {
            let mut local=history::local_new(bounds,context.unwrap())?;
            if let Some(bands)=&context.unwrap().source_domains{bands.share_cost()?;local.source_domains=Some(bands.clone());}
            return Ok(local);
        }
        if let Some(w) = context.and_then(|c| c.floor_work.as_ref()) {
            let c = context.unwrap();
            crate::event_floor::charge(
                w,
                c.nodes
                    .len()
                    .saturating_add(c.states.len())
                    .saturating_add(1),
                "floor_source_binding_scan",
            )?;
            let limbs = c
                .nodes
                .iter()
                .flatten()
                .chain(c.states.values())
                .map(|r| 1 + (r.numer().bits() + r.denom().bits()).div_ceil(64) as usize)
                .sum::<usize>();
            crate::event_floor::charge(
                w,
                limbs + c.nodes.len() * 2 + bounds.len() * 4 + 1,
                "floor_source_copy",
            )?;
            crate::event_floor::charge(w, 1024 * c.states.len(), "floor_source_exact_enclosure")?;
        }
        let mut local=Self::with_context(bounds,context);
        if let Some(bands)=context.and_then(|c|c.source_domains.as_ref()){bands.share_cost()?;local.source_domains=Some(bands.clone());}
        Ok(local)
    }

    pub(crate) fn new(bounds: &[I]) -> Self {
        Self {
            bounds: bounds.to_vec(),
            exact: bounds.iter().map(|v| point(*v)).collect(),
            nodes: None,
            floor_work: None,
            history_work: None,
            floor_bounds: None,
            source_domains:None,
        }
    }
    pub(crate) fn with_context(bounds: &[I], context: Option<&Context<'_>>) -> Self {
        let mut local = Self::with_proofs(bounds, context.map(|c| c.states));
        local.nodes = context.map(|c| c.nodes.clone());
        local.floor_work = context.and_then(|c| c.floor_work.clone());
        local.floor_bounds = context.and_then(|c| c.floor_bounds.clone());
        local
    }
    pub(crate) fn with_proofs(bounds: &[I], proofs: Option<&Proofs>) -> Self {
        let mut local = Self::new(bounds);
        if let Some(proofs) = proofs {
            for (&state, value) in proofs {
                if let Some(b) = bounds.get(state) {
                    if enclosure(value).is_some_and(|v| b.lo <= v.lo && v.hi <= b.hi) {
                        local.exact[state] = Some(value.clone());
                    }
                }
            }
        }
        local
    }
    pub(crate) fn try_assign(
        &mut self,
        state: usize,
        expr: &E,
        nodes: &[I],
        bounds: I,
    ) -> Result<(), crate::ir::Error> {
        if self.history_work.is_some() {
            return history::assign(self, state, expr, nodes, bounds);
        }
        let has_floor = if let Some(w) = self.floor_work() {
            crate::event_floor::contains_charged(expr, w)?
        } else {
            false
        };
        if has_floor {
            let e = crate::event_floor::resolve(expr, nodes, self)?;
            let w = self
                .floor_work
                .as_ref()
                .ok_or_else(|| {
                    crate::ir::Error::new("event_condition", "source floor assignment lacks owner")
                })?
                .clone();
            let exact = self.try_value(&e, nodes)?;
            crate::event_floor::charge(&w, 1024, "floor_source_exact_enclosure")?;
            let tighter = exact
                .as_ref()
                .and_then(enclosure)
                .filter(|v| bounds.lo <= v.lo && v.hi <= bounds.hi);
            self.bounds[state] = tighter.unwrap_or(bounds);
            self.exact[state] = exact.filter(|_| tighter.is_some());
        } else if self.floor_work.is_some() {
            let exact = self.try_value(expr, nodes)?;
            if let Some(w) = &self.floor_work {
                crate::event_floor::charge(w, 1024, "floor_source_exact_enclosure")?;
            }
            let tighter = exact
                .as_ref()
                .and_then(enclosure)
                .filter(|v| bounds.lo <= v.lo && v.hi <= bounds.hi);
            self.bounds[state] = tighter.unwrap_or(bounds);
            self.exact[state] = exact.filter(|_| tighter.is_some());
        } else {
            self.assign(state, expr, nodes, bounds);
        }
        Ok(())
    }
    pub(crate) fn assign(&mut self, state: usize, expr: &E, nodes: &[I], bounds: I) {
        let exact = self.value(expr, nodes);
        // A proof is optional. The ordinary interval path still owns finite,
        // domain and resource diagnostics and remains the conservative fallback.
        let tighter = exact
            .as_ref()
            .and_then(enclosure)
            .filter(|v| bounds.lo <= v.lo && v.hi <= bounds.hi);
        self.bounds[state] = tighter.unwrap_or(bounds);
        // A finite singleton certified enclosure is itself the exact binary
        // value, exactly as `new` treats singleton input bounds.
        self.exact[state] = exact
            .filter(|_| tighter.is_some())
            .or_else(|| point(self.bounds[state]));
    }
    pub(crate) fn merge(&mut self, yes: Self, no: &Self) {
        *self = yes;
        for (a, b) in self.exact.iter_mut().zip(&no.exact) {
            #[cfg(test)]
            if let (Some(a), Some(b)) = (a.as_ref(), b.as_ref()) {
                crate::diagnostics::counter(
                    "history_merge_large_pairs",
                    usize::from(
                        a.numer()
                            .bits()
                            .max(a.denom().bits())
                            .max(b.numer().bits())
                            .max(b.denom().bits())
                            > 512,
                    ),
                );
            }
            if *a != *b {
                *a = None;
            }
        }
    }
    pub(crate) fn value(&self, expr: &E, nodes: &[I]) -> Option<R> {
        self.value_with_work(expr, nodes, &mut || Some(()))
            .ok()
            .flatten()
    }
    /// Charge a caller's aggregate allowance before each visited node and
    /// exact arithmetic operation, retaining the evaluator's per-expression
    /// limits. Unknown provenance is distinct from an exhausted allowance.
    pub(crate) fn value_with_work<W: FnMut() -> Option<()>>(
        &self,
        expr: &E,
        nodes: &[I],
        work: &mut W,
    ) -> Result<Option<R>, ()> {
        let mut exhausted = false;
        let result = evaluate(
            expr,
            nodes,
            &self.exact,
            self.nodes.as_deref(),
            &mut Budget(0),
            0,
            &mut 0,
            &mut || {
                let result = work();
                exhausted |= result.is_none();
                result
            },
        );
        if exhausted {
            Err(())
        } else {
            Ok(result)
        }
    }
    /// Ordinary event/time proof retains its existing per-expression allowance.
    pub(crate) fn assign_proof(&mut self, state: usize, expr: &E, nodes: &[I]) {
        self.exact[state] = self.value(expr, nodes);
    }
    /// Replay optional scalar provenance in a private proof frame. Aggregate
    /// exhaustion must stop replay, rather than merely clearing one value.
    pub(crate) fn assign_proof_with_work<W: FnMut() -> Option<()>>(
        &mut self,
        state: usize,
        expr: &E,
        nodes: &[I],
        work: &mut W,
    ) -> Result<(), ()> {
        self.exact[state] = self.value_with_work(expr, nodes, work)?;
        Ok(())
    }
}
fn point(v: I) -> Option<R> {
    (v.lo == v.hi).then(|| binary(v.lo)).flatten()
}
#[allow(clippy::too_many_arguments)]
fn evaluate<W: FnMut() -> Option<()>>(
    e: &E,
    nodes: &[I],
    states: &[Option<R>],
    node_proofs: Option<&[Option<R>]>,
    budget: &mut Budget,
    depth: usize,
    count: &mut usize,
    work: &mut W,
) -> Option<R> {
    work()?;
    *count += 1;
    if depth > 64 || *count > 512 {
        return None;
    }
    match e {
        E::RealBoundary{value,..}=>{
            let value=evaluate(value,nodes,states,node_proofs,budget,depth+1,count,work)?;
            let rounded=crate::real_rounding::round_ratio(&value,false,&mut |n|{
                for _ in 0..n {work().ok_or(())?;} Ok::<_,()>(())
            }).ok()?;
            budget.check(binary(rounded)?)
        },
        E::RealBinary{operation,left,right,..}=>{
            let a=evaluate(left,nodes,states,node_proofs,budget,depth+1,count,work)?;
            let b=evaluate(right,nodes,states,node_proofs,budget,depth+1,count,work)?;
            let mut round=|value:&R|crate::real_rounding::round_ratio(value,false,&mut |n|{
                for _ in 0..n {work().ok_or(())?;} Ok::<_,()>(())
            }).ok();
            let a=round(&a)?;let b=round(&b)?;
            work()?;
            let result=crate::real_expression::point(*operation,a,b).ok()?;
            budget.check(binary(result)?)
        },
        E::Affine { constant, terms } => {
            if terms.len() > 512 {
                return None;
            }
            let mut value = binary(*constant)?;
            for term in terms {
                work()?;
                if term.node == 0 {
                    continue;
                }
                let v = node_proofs
                    .and_then(|p| p.get(term.node))
                    .and_then(|v| v.clone())
                    .or_else(|| point(*nodes.get(term.node)?))?;
                work()?;
                let product = budget.check(binary(term.coefficient)? * v)?;
                work()?;
                value = budget.check(value + product)?;
            }
            Some(value)
        }
        E::IntegerPrimitive {
            function,
            args,
            origin,
        } => {
            use num_traits::ToPrimitive;
            let mut visited = 0usize;
            let value = crate::integer_primitive::evaluate(
                *function,
                args,
                origin,
                &mut |state| {
                    let r = states
                        .get(state)
                        .and_then(|v| v.as_ref())
                        .filter(|r| r.is_integer())
                        .and_then(|r| r.to_integer().to_i32());
                    r.ok_or_else(|| {
                        crate::ir::Error::new("unknown_proof", "integer state proof missing")
                    })
                },
                &mut || {
                    visited += 1;
                    work().ok_or_else(|| {
                        crate::ir::Error::new("resource_budget", "integer proof work exhausted")
                    })?;
                    if *count + visited > 512 || depth + visited > 64 {
                        return Err(crate::ir::Error::new(
                            "unknown_proof",
                            "integer proof expression limit",
                        ));
                    }
                    Ok(())
                },
            )
            .ok()?;
            *count += visited;
            budget.check(binary(f64::from(value))?)
        }
        E::State { state } => budget.check(states.get(*state)?.as_ref()?.clone()),
        E::Add { left, right } | E::Multiply { left, right } | E::Divide { left, right } => {
            let a = evaluate(
                left,
                nodes,
                states,
                node_proofs,
                budget,
                depth + 1,
                count,
                work,
            )?;
            let b = evaluate(
                right,
                nodes,
                states,
                node_proofs,
                budget,
                depth + 1,
                count,
                work,
            )?;
            work()?;
            if matches!(e, E::Add { .. }) {
                budget.check(a + b)
            } else if matches!(e, E::Multiply { .. }) {
                budget.check(a * b)
            } else if b.is_zero() {
                None
            } else {
                budget.check(a / b)
            }
        }
        E::Power { base, exponent } if *exponent <= 32 => {
            let a = evaluate(
                base,
                nodes,
                states,
                node_proofs,
                budget,
                depth + 1,
                count,
                work,
            )?;
            let mut result = binary(1.)?;
            for _ in 0..*exponent {
                work()?;
                result = budget.check(result * &a)?;
            }
            Some(result)
        }
        E::EventMath { function, args, .. } => {
            let a = evaluate(
                args.first()?,
                nodes,
                states,
                node_proofs,
                budget,
                depth + 1,
                count,
                work,
            )?;
            match function {
                F::Floor if args.len() == 1 => {
                    work()?;
                    budget.check(a.floor())
                }
                F::Abs if args.len() == 1 => {
                    work()?;
                    budget.check(a.abs())
                }
                F::Min | F::Max if args.len() == 2 => {
                    let b = evaluate(
                        &args[1],
                        nodes,
                        states,
                        node_proofs,
                        budget,
                        depth + 1,
                        count,
                        work,
                    )?;
                    work()?;
                    budget.check(if matches!(function, F::Min) {
                        a.min(b)
                    } else {
                        a.max(b)
                    })
                }
                _ => None,
            }
        }
        _ => None,
    }
}

/// Meter the source-request variant without changing old optional provenance.
pub(crate) fn apply_charged(
    model: &crate::events::EventModel,
    selection: &crate::event_conditions::Selection,
    inputs: &[I],
    before: &[I],
    after: &[I],
    context: &Context<'_>,
) -> Result<Proofs, crate::ir::Error> {
    if let Some(w) = context.history_work.as_ref() {
        return history::apply(model, selection, inputs, before, after, context, w);
    }
    let Some(w) = context.floor_work.as_ref() else {
        return Ok(apply(model, selection, inputs, before, after, context));
    };
    crate::event_floor::charge(w, model.program.nodes.len() + 1, "floor_source_copy")?;
    let nodes = crate::causal_event::input_nodes(model, inputs);
    let initial = LocalState::try_with_context(before, Some(context))?;
    initial.prepay_copy()?;
    let mut result = initial
        .exact
        .iter()
        .enumerate()
        .filter_map(|(s, v)| Some((s, v.clone()?)))
        .collect::<Proofs>();
    let mut frames=crate::procedure_frames::Frames::new(selection,Some(w))?;
    for (event, indices) in &selection.actions {
        let mut local = match frames.take(*event){Some(v)=>v,None=>initial.try_clone()?};
        let body = &model.program.events[*event].body;
        let size = crate::event_floor::encoded_size(body, w)?;
        crate::event_floor::charge(w, size, "floor_source_copy")?;
        let assignments = model.program.events[*event].assignments();
        for &index in indices {
            let a = &assignments[index];
            let exact = if crate::event_floor::contains_charged(&a.rhs, w)? {
                let resolved = crate::event_floor::resolve(&a.rhs, &nodes, &local)?;
                local.try_value(&resolved, &nodes)?
            } else {
                local.try_value(&a.rhs, &nodes)?
            };
            crate::event_floor::charge(w, 144, "floor_source_copy")?;
            local.exact[a.state] = exact.clone();
            result.remove(&a.state);
            if let Some(value) = exact {
                result.insert(a.state, value);
            }
        }
        frames.put(*event,local);
    }
    crate::event_floor::charge(w, result.len() * 8, "floor_source_copy")?;
    let mut checked = Proofs::new();
    for (state, value) in result {
        crate::event_floor::charge(w, 1024, "floor_source_exact_enclosure")?;
        if after
            .get(state)
            .is_some_and(|b| enclosure(&value).is_some_and(|v| b.lo <= v.lo && v.hi <= b.hi))
        {
            checked.insert(state, value);
        }
    }
    Ok(checked)
}

/// Replay the selected original assignments in a private proof frame. Every
/// block starts from the same old state; unsupported writes clear provenance.
pub(crate) fn apply(
    model: &crate::events::EventModel,
    selection: &crate::event_conditions::Selection,
    inputs: &[I],
    before: &[I],
    after: &[I],
    context: &Context<'_>,
) -> Proofs {
    let nodes = crate::causal_event::input_nodes(model, inputs);
    let initial = LocalState::with_context(before, Some(context));
    let mut result = initial
        .exact
        .iter()
        .enumerate()
        .filter_map(|(s, v)| Some((s, v.clone()?)))
        .collect::<Proofs>();
    let mut frames=crate::procedure_frames::Frames::new(selection,None).expect("unmetered frame construction");
    for (event, indices) in &selection.actions {
        let mut local = frames.take(*event).unwrap_or_else(||initial.clone());
        let assignments = model.program.events[*event].assignments();
        for &index in indices {
            let a = &assignments[index];
            let exact = local.value(&a.rhs, &nodes);
            local.exact[a.state] = exact.clone();
            result.remove(&a.state);
            if let Some(value) = exact {
                result.insert(a.state, value);
            }
        }
        frames.put(*event,local);
    }
    result.retain(|s, value| {
        after
            .get(*s)
            .is_some_and(|b| enclosure(value).is_some_and(|v| b.lo <= v.lo && v.hi <= b.hi))
    });
    result
}

pub(crate) fn valid(proofs: &Proofs, bounds: &[I]) -> bool {
    proofs.iter().all(|(state, value)| {
        bounds
            .get(*state)
            .is_some_and(|b| enclosure(value).is_some_and(|v| b.lo <= v.lo && v.hi <= b.hi))
    })
}

/// exact old valid() semantics, only explicit original Work accounting added.
pub(crate) fn valid_with_work(
    proofs: &Proofs,
    bounds: &[I],
    w: &crate::transition_source_plan::Work,
) -> Result<bool, crate::ir::Error> {
    w.debit(2, 0)?;
    w.debit(
        2,
        (proofs.len() as u64).saturating_mul(16).saturating_add(16),
    )?;
    for (&state, value) in proofs {
        let Some(bound) = bounds.get(state) else {
            return Ok(false);
        };
        if !crate::exact_source::enclosure_with_work(value, w)?
            .is_some_and(|enclosure| bound.lo <= enclosure.lo && enclosure.hi <= bound.hi)
        {
            return Ok(false);
        }
    }
    Ok(true)
}

#[cfg(test)]
mod native_floor_tests {
    use super::*;
    #[test]
    fn negative_rational_floor_charges_existing_work_and_exhaustion_returns_unknown() {
        let local = LocalState {
            bounds: vec![],
            exact: vec![],
            nodes: Some(vec![binary(0.), Some(R::new((-1).into(), 3.into()))]),
            floor_work: None,
            history_work: None,
            floor_bounds: None,
            source_domains:None,
        };
        let node = E::Affine {
            constant: 0.,
            terms: vec![crate::ir::Term {
                node: 1,
                coefficient: 1.,
            }],
        };
        let expr = E::EventMath {
            function: F::Floor,
            args: vec![node],
            origin: crate::ir::Origin {
                source: "floor.va".into(),
                line: 1,
                column: 1,
                instance: "dut".into(),
                expansion: vec![],
            },
        };
        let nodes = [
            I::ZERO,
            I {
                lo: -0.34,
                hi: -0.33,
            },
        ];
        assert_eq!(local.value(&expr, &nodes), binary(-1.));
        assert!(local.value_with_work(&expr, &nodes, &mut || None).is_err());
    }
}

#[cfg(test)]
mod singleton_assignment_tests {
    use super::*;
    fn node(n: usize) -> E {
        E::Affine {
            constant: 0.,
            terms: vec![crate::ir::Term {
                node: n,
                coefficient: 1.,
            }],
        }
    }
    // x = 0.45 + (V(1) - s): exact binary64 inputs give 2^-54, not a tie.
    fn residual() -> E {
        E::Add {
            left: Box::new(E::Affine {
                constant: 0.45,
                terms: vec![crate::ir::Term {
                    node: 2,
                    coefficient: 1.,
                }],
            }),
            right: Box::new(E::Multiply {
                left: Box::new(E::Affine {
                    constant: -1.,
                    terms: vec![],
                }),
                right: Box::new(E::State { state: 0 }),
            }),
        }
    }
    #[test]
    fn certified_singleton_assignment_is_an_exact_value_but_a_box_is_not() {
        // Node 1 is an unsolved electrical node; its certified sample enters
        // only through the assignment's enclosure.
        let nodes = [
            I::ZERO,
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY,
            },
            I::point(0.28),
        ];
        let mut local = LocalState::new(&[I::ZERO]);
        local.assign(0, &node(1), &nodes, I::point(0.73));
        assert_eq!(local.exact[0], binary(0.73));
        let x = local.value(&residual(), &nodes).unwrap();
        assert_eq!(x, R::new(1.into(), (1u64 << 54).into()));
        // A nonsingleton enclosure still carries no exact provenance.
        let mut boxed = LocalState::new(&[I::ZERO]);
        boxed.assign(
            0,
            &node(1),
            &nodes,
            I {
                lo: 0.73,
                hi: 0.73f64.next_up(),
            },
        );
        assert_eq!(boxed.exact[0], None);
        assert_eq!(boxed.value(&residual(), &nodes), None);
    }
}

#[cfg(test)]
mod point_state_reuse_tests{
    use super::*;
    use crate::transition_source_plan::Work;
    fn local(point:f64,w:&Work)->LocalState{
        let proofs=Proofs::new();let context=Context::candidate_frame(&proofs,0,&[point],&[],w).unwrap();
        LocalState::try_with_context(&[I::point(point)],Some(&context)).unwrap()
    }
    #[test]
    fn point_state_reuse_exact_bits_include_subnormals_signs_and_reject_rounded_neighbours(){
        let w=Work::default();
        for point in [0.,-0.,f64::from_bits(1),-f64::from_bits(1),f64::MIN_POSITIVE,0.1,-0.1,1.,-1.,2f64.powi(53),f64::MAX]{
            let value=binary(point).unwrap();assert!(binary_state_identity(&value,point,&w).unwrap());
            assert_eq!(local(point,&w).try_point_state(0,point,I::point(point),&w).unwrap(),Some(value));
        }
        assert!(!binary_state_identity(&R::new(1.into(),10.into()),0.1,&w).unwrap());
        let close=R::from_integer(1.into())+R::new(1.into(),(1u64<<60).into());assert!(!binary_state_identity(&close,1.,&w).unwrap());
        assert!(!binary_state_identity(&binary(-1.).unwrap(),1.,&w).unwrap());
    }
    #[test]
    fn point_state_reuse_is_bound_to_current_frame_native_bits_and_original_owner(){
        let w=Work::default();let first=local(0.1,&w);let mut next=local(0.2,&w);
        assert_eq!(first.try_point_state(0,0.1,I::point(0.1),&w).unwrap(),binary(0.1));
        assert_eq!(next.try_point_state(0,0.2,I::point(0.2),&w).unwrap(),binary(0.2));
        assert!(first.try_point_state(0,0.2,I::point(0.2),&w).unwrap().is_none());
        // Model the legacy sequential mutator whose exact assignment can change
        // without replacing its incoming bounds. A rounded match is insufficient.
        next.exact[0]=Some(R::new(1.into(),5.into()));assert!(next.try_point_state(0,0.2,I::point(0.2),&w).unwrap().is_none());
        let foreign=Work::default();let other=local(0.1,&foreign);let before=foreign.spent();
        assert!(other.try_point_state(0,0.1,I::point(0.1),&w).unwrap().is_none());assert_eq!(foreign.spent(),before);
        assert_eq!(other.try_point_state(0,0.1,I::point(0.1),&foreign).unwrap(),binary(0.1));
        let same_numeric_distinct_context=local(0.1,&w);assert_eq!(same_numeric_distinct_context.try_point_state(0,0.1,I::point(0.1),&w).unwrap(),binary(0.1));
        let mut uncertain=local(1.,&w);let band=I{lo:1f64.next_down(),hi:1f64.next_up()};uncertain.bounds[0]=band;
        assert!(uncertain.try_point_state(0,1.,band,&w).unwrap().is_none());assert!(first.try_point_state(0,0.1,I{lo:0.09,hi:0.11},&w).unwrap().is_none());
        assert!(local(-0.,&w).try_point_state(0,0.,I::point(0.),&w).unwrap().is_none());
        assert!(local(0.,&w).try_point_state(0,0.,I{lo:-0.,hi:0.},&w).unwrap().is_none());
    }
    #[test]
    fn point_state_reuse_natural_helper_exhaustion_keeps_current_frame_and_sticky_spent(){
        let w=Work::limited([128,8192,50_000]);let local=local(0.1,&w);let value=local.exact[0].clone();let mut exhausted=false;
        for _ in 0..10_000{match local.try_point_state(0,0.1,I::point(0.1),&w){Ok(Some(_))=>{},Err(error)=>{assert_eq!(error.kind,"step_budget");exhausted=true;break;},Ok(None)=>panic!("point proof disappeared")}}
        assert!(exhausted);assert!(w.spent()>50_000);let spent=w.spent();let shared=w.clone();assert!(w.same_owner(&shared));
        for _ in 0..2{assert_eq!(local.try_point_state(0,0.1,I::point(0.1),&shared).unwrap_err().kind,"step_budget");assert_eq!(shared.spent(),spent);assert_eq!(local.exact[0],value);assert_eq!(local.bounds,[I::point(0.1)]);}
    }
    #[test]
    fn point_state_reuse_two_actual_evaluations_and_stale_local_fallback_keep_samples(){
        use crate::procedure_operations::{Operation,Domain};
        let w=Work::default();let first=local(0.1,&w);let next=local(0.2,&w);let operation=Operation::State(0);
        let evaluate=|point,local:&LocalState|{let states=[Some(point)];let bounds=[I::point(point)];let domain=Domain{nodes:&[],node_bounds:&[],states:&states,state_bounds:&bounds,operators:&[],operator_bounds:&[],local};operation.evaluate(&[],&domain,&w).unwrap()};
        let a=evaluate(0.1,&first);let b=evaluate(0.2,&next);let stale=evaluate(0.2,&first);
        assert_eq!(**a.mathematical.as_ref().unwrap(),binary(0.1).unwrap());assert_eq!(**b.mathematical.as_ref().unwrap(),binary(0.2).unwrap());assert_eq!(**stale.mathematical.as_ref().unwrap(),binary(0.2).unwrap());
        assert!(!std::sync::Arc::ptr_eq(a.mathematical.as_ref().unwrap(),b.mathematical.as_ref().unwrap()));
        let second_context=local(0.1,&w);let same=evaluate(0.1,&second_context);assert!(!std::sync::Arc::ptr_eq(a.mathematical.as_ref().unwrap(),same.mathematical.as_ref().unwrap()));
        for point in [0.,-0.]{let current=local(point,&w);let value=evaluate(point,&current);assert_eq!(value.point().unwrap().to_bits(),point.to_bits());assert_eq!(value.bound().unwrap().lo.to_bits(),point.to_bits());assert_eq!(value.bound().unwrap().hi.to_bits(),point.to_bits());}
    }
}
