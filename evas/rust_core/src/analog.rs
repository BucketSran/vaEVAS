//! Stateless voltage relations with explicit affine/polynomial certification.
//! Resolve any conditions from original PWL enclosures, then certify the output.
use crate::event_conditions::Selection;
use crate::events::EventModel;
use crate::expression::resolve_selects;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, Program, Solution, Tolerances};
use crate::solver::Circuit;

struct Prepared {
    expressions: Vec<Expression>,
    model: Option<EventModel>,
    circuit: Circuit,
}

pub(crate) struct Analog {
    program: Program,
    driven: Vec<String>,
    input_nodes: Vec<usize>,
    tolerances: Tolerances,
    // Only the last branch's equations and error map are cached. Input values,
    // solutions and physical history are never cached or committed here.
    prepared: Option<Prepared>,
    has_select: bool,
}

pub(crate) fn has_select(expr: &Expression) -> bool {
    match expr {
        Expression::Select { .. } => true,
        Expression::Add { left, right } | Expression::Multiply { left, right } => {
            has_select(left) || has_select(right)
        }
        Expression::Power { base, .. } => has_select(base),
        _ => false,
    }
}

impl Analog {
    pub(crate) fn new(
        program: Program,
        driven: Vec<String>,
        tolerances: Tolerances,
    ) -> Result<Self, Error> {
        // Validate the entire original IR, including unreachable arms and
        // predicates, before resolving any sample-dependent branch.
        Circuit::new(program.clone(), &driven, tolerances.clone())?;
        let input_nodes = driven
            .iter()
            .map(|name| program.nodes.iter().position(|n| n == name).unwrap())
            .collect();
        let has_select = program.contributions.iter().any(|c| has_select(&c.rhs));
        Ok(Self {
            program,
            driven,
            input_nodes,
            tolerances,
            prepared: None,
            has_select,
        })
    }

    pub(crate) fn solve(
        &mut self,
        inputs: &[f64],
        input_bounds: &[I],
        initial: Option<&[f64]>,
    ) -> Result<Solution, Error> {
        let mut nodes = vec![I::ZERO; self.program.nodes.len()];
        for (&node, &bounds) in self.input_nodes.iter().zip(input_bounds) {
            nodes[node] = bounds;
        }
        let expressions = self
            .program
            .contributions
            .iter()
            .map(|c| resolve_selects(&c.rhs, &nodes))
            .collect::<Result<Vec<_>, _>>()?;
        if !self
            .prepared
            .as_ref()
            .is_some_and(|p| p.expressions == expressions)
        {
            let mut frozen = self.program.clone();
            for (c, rhs) in frozen.contributions.iter_mut().zip(&expressions) {
                c.rhs = rhs.clone();
            }
            // Affine systems retain the existing original-IR forward-error
            // map, including merged contributions and redundant constraints.
            // The stateless polynomial extension uses Newton and a Krawczyk
            // certificate. Input-selected polynomial leaves remain outside
            // the ordinary-condition contract; no unsupported IR is dropped.
            let (model, circuit) =
                match EventModel::new(frozen.clone(), self.driven.clone(), self.tolerances.clone())
                {
                    Ok(model) => {
                        let circuit = model.circuit(&[])?;
                        (Some(model), circuit)
                    }
                    Err(error) if error.kind == "unsupported_transient" && !self.has_select => (
                        None,
                        Circuit::new(frozen, &self.driven, self.tolerances.clone())?,
                    ),
                    Err(error) => return Err(error),
                };
            self.prepared = Some(Prepared {
                expressions,
                model,
                circuit,
            });
        }
        let prepared = self.prepared.as_ref().unwrap();
        let solution = prepared.circuit.solve_with_initial(inputs, initial)?;
        if let Some(model) = &prepared.model {
            model
                .certify(
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
        } else {
            prepared
                .circuit
                .check_waveform_accuracy(&solution, input_bounds)?;
        }
        Ok(solution)
    }
}
