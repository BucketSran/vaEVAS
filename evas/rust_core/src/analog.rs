//! Stateless voltage relations with explicit affine/polynomial certification.
//! Resolve any conditions from original PWL enclosures, then certify the output.
use crate::event_conditions::Selection;
use crate::events::EventModel;
use crate::expression::{input_rational_tree, resolve_selects_with_sources};
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, Program, Solution, Tolerances};
use crate::solver::Circuit;
use std::collections::HashSet;

struct Prepared {
    expressions: Vec<Expression>,
    model: Option<EventModel>,
    circuit: Circuit,
}

pub(crate) struct Analog {
    procedure_work: Option<crate::transition_source_plan::Work>,
    program: Program,
    driven: Vec<String>,
    input_nodes: Vec<usize>,
    tolerances: Tolerances,
    // Only the last branch's equations and error map are cached. Input values,
    // solutions and physical history are never cached or committed here.
    prepared: Option<Prepared>,
    has_select: bool,
    source_rational: bool,
}

pub(crate) fn has_select(expr: &Expression) -> bool {
    match expr {
        Expression::Select { .. } => true,
        Expression::Add { left, right }
        | Expression::Multiply { left, right }
        | Expression::Divide { left, right } => has_select(left) || has_select(right),
        Expression::Power { base, .. } => has_select(base),
        _ => false,
    }
}

impl Analog {
    #[cfg(test)]
    pub(crate) fn source_trial_has_cache(&self) -> bool {
        self.prepared.is_some()
    }

    /// A selected stateless math query never commits a failed solver cache.
    pub(crate) fn fresh_source_trial(&self) -> Result<Self, Error> {
        self.charge_procedure_copy(1)?;
        if let Some(work) = &self.procedure_work {
            work.debit(2,16)?;
            return Self::new_with_procedure_work(self.program.clone(),self.driven.clone(),self.tolerances.clone(),work.clone());
        }
        Self::new(
            self.program.clone(),
            self.driven.clone(),
            self.tolerances.clone(),
        )
    }

    pub(crate) fn new(
        program: Program,
        driven: Vec<String>,
        tolerances: Tolerances,
    ) -> Result<Self, Error> {
        // Validate the entire original IR, including unreachable arms and
        // predicates, before resolving any sample-dependent branch.
        Circuit::new(program.clone(), &driven, tolerances.clone())?;
        let input_nodes: Vec<_> = driven
            .iter()
            .map(|name| program.nodes.iter().position(|n| n == name).unwrap())
            .collect();
        let has_select = program.contributions.iter().any(|c| has_select(&c.rhs));
        let source_nodes: HashSet<_> = input_nodes.iter().copied().chain([0]).collect();
        let source_rational = program
            .contributions
            .iter()
            .all(|c| input_rational_tree(&c.rhs, &source_nodes).is_some());
        Ok(Self {
            procedure_work: None,
            program,
            driven,
            input_nodes,
            tolerances,
            prepared: None,
            has_select,
            source_rational,
        })
    }

    /// The early physical-math consumer retains one execution owner through
    /// its private algebraic reduction and all later source queries.
    pub(crate) fn new_with_procedure_work(program: Program, driven: Vec<String>, tolerances: Tolerances, work: crate::transition_source_plan::Work) -> Result<Self, Error> {
        work.debit(2, 16)?;
        let bytes = crate::event_floor::encoded_size(&program, &work)?;
        // Circuit::new below borrows one complete owned validation copy.
        work.debit(2, (bytes as u64).saturating_mul(8))?;
        let mut analog = Self::new(program, driven, tolerances)?;
        analog.procedure_work = Some(work);
        Ok(analog)
    }
    #[cfg(test)]
    pub(crate) fn prepared_uses_procedure_owner(&self, work: &crate::transition_source_plan::Work) -> bool {
        self.procedure_work.as_ref().is_some_and(|w| w.same_owner(work)) &&
        self.prepared.as_ref().and_then(|p|p.model.as_ref()).is_some_and(|model|crate::real_expression::work(model).same_owner(work))
    }
    pub(crate) fn charge_procedure_query(&self, values: usize) -> Result<(), Error> {
        if let Some(work) = &self.procedure_work { work.debit(2,(values as u64).saturating_mul(64).saturating_add(32))?; }
        Ok(())
    }
    fn charge_procedure_copy(&self, copies: u64) -> Result<(), Error> {
        if let Some(work) = &self.procedure_work {
            let bytes = crate::event_floor::encoded_size(&self.program, work)?;
            work.debit(2, (bytes as u64).saturating_mul(8).saturating_mul(copies))?;
        }
        Ok(())
    }
    pub(crate) fn solve(
        &mut self,
        inputs: &[f64],
        input_bounds: &[I],
        initial: Option<&[f64]>,
        time: f64,
        exact_sources: &[Option<crate::exact_source::Curve>],
    ) -> Result<Solution, Error> {
        self.charge_procedure_copy(2)?;
        self.charge_procedure_query(self.program.nodes.len().saturating_add(self.input_nodes.len()))?;
        let mut nodes = vec![I::ZERO; self.program.nodes.len()];
        for (&node, &bounds) in self.input_nodes.iter().zip(input_bounds) {
            nodes[node] = bounds;
        }
        let expressions = self
            .program
            .contributions
            .iter()
            .map(|c| {
                resolve_selects_with_sources(&c.rhs, &nodes, &self.input_nodes, exact_sources, time)
            })
            .collect::<Result<Vec<_>, _>>()?;
        if !self
            .prepared
            .as_ref()
            .is_some_and(|p| p.expressions == expressions)
        {
            self.charge_procedure_copy(2)?;
            let mut frozen = self.program.clone();
            for (c, rhs) in frozen.contributions.iter_mut().zip(&expressions) {
                c.rhs = rhs.clone();
            }
            // Affine systems retain the existing original-IR forward-error
            // map, including merged contributions and redundant constraints.
            // The stateless polynomial extension uses Newton and a Krawczyk
            // certificate. Input-selected polynomial leaves remain outside
            // the ordinary-condition contract. A fully source-driven rational
            // tree can reuse the same original-expression certificate after
            // its input predicates resolve; no nominal input is substituted.
            let (model, circuit) =
                match if let Some(work) = &self.procedure_work {
                    work.debit(2, 16)?;
                    EventModel::new_with_procedure_work(frozen.clone(), self.driven.clone(), self.tolerances.clone(), work.clone())
                } else {
                    EventModel::new(frozen.clone(), self.driven.clone(), self.tolerances.clone())
                } {
                    Ok(model) => {
                        let circuit = model.circuit(&[])?;
                        (Some(model), circuit)
                    }
                    Err(error)
                        if error.kind == "unsupported_transient"
                            && (!self.has_select || self.source_rational) =>
                    {
                        (
                            None,
                            Circuit::new(frozen, &self.driven, self.tolerances.clone())?,
                        )
                    }
                    Err(error) => return Err(error),
                };
            self.prepared = Some(Prepared {
                expressions,
                model,
                circuit,
            });
        }
        let prepared = self.prepared.as_ref().unwrap();
        let mut solution = prepared.circuit.solve_with_initial(inputs, initial)?;
        if let Some(model) = &prepared.model {
            let (_, bounds) = model
                .certify_observation(
                    &Selection::default(),
                    input_bounds,
                    &[],
                    &[],
                    &solution.voltages,
                    &[],
                )
                .map_err(|mut error| {
                    if error.kind == "event_accuracy" {
                        error.kind = "waveform_accuracy";
                    }
                    error
                })?;
            crate::observation::retain_bounds(&mut solution, bounds);
        } else {
            let bounds = prepared.circuit.waveform_bounds(&solution, input_bounds)?;
            crate::observation::retain_bounds(&mut solution, bounds);
        }
        Ok(solution)
    }
}
