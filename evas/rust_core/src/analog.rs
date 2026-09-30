//! Stateless affine and input-selected piecewise-affine voltage relations.
//! Resolve any conditions from original PWL enclosures, then certify the output.
use crate::event_conditions::Selection;
use crate::events::EventModel;
use crate::expression::resolve_selects;
use crate::interval::Interval as I;
use crate::ir::{Error, Expression, Program, Solution, Tolerances};
use crate::solver::Circuit;

struct Prepared {
    expressions: Vec<Expression>,
    model: EventModel,
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
        Ok(Self {
            program,
            driven,
            input_nodes,
            tolerances,
            prepared: None,
        })
    }

    pub(crate) fn solve(&mut self, inputs: &[f64], input_bounds: &[I]) -> Result<Solution, Error> {
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
            // This slice requires affine leaves. EventModel's existing affine
            // binding and original-IR error certificate provide that contract.
            let model = EventModel::new(frozen, self.driven.clone(), self.tolerances.clone())?;
            let circuit = model.circuit(&[])?;
            self.prepared = Some(Prepared {
                expressions,
                model,
                circuit,
            });
        }
        let prepared = self.prepared.as_ref().unwrap();
        let solution = prepared.circuit.solve(inputs)?;
        prepared
            .model
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
        Ok(solution)
    }
}
