//! Event-body conditions may observe certified, unchanged external voltage forcing.
//! This is a pre-write physical sample, never an iterative event-feedback solve.
use crate::event_conditions::Selection;
use crate::events::{AffineState, EventModel};
use crate::interval::Interval as I;
use crate::ir::{Error, OperatorSpec};
use std::collections::BTreeSet;

impl EventModel {
    pub(crate) fn condition_node_states(
        &self,
        rhs: &[AffineState],
        groups: &[Vec<usize>],
        assembled: &crate::assembly::AssembledCircuit,
    ) -> Result<Vec<BTreeSet<usize>>, Error> {
        let n = self.program.nodes.len();
        let mut reads = vec![BTreeSet::new(); n + self.program.operators.len()];
        let mut edges = vec![BTreeSet::new(); reads.len()];
        for (group, equation) in groups.iter().zip(&assembled.equations) {
            for &node in group {
                edges[node].extend(group);
                for (contribution, value) in self
                    .program
                    .contributions
                    .iter()
                    .zip(rhs)
                    .filter(|(c, _)| c.branch == equation.branch)
                {
                    let _ = contribution;
                    reads[node].extend(&value.state_dependencies);
                    edges[node].extend(value.operator_dependencies.iter().map(|i| n + i));
                }
            }
        }
        for (i, operator) in self.program.operators.iter().enumerate() {
            let input = match operator {
                OperatorSpec::Ddt { input, .. }
                | OperatorSpec::Idt { input, .. }
                | OperatorSpec::Transition { input, .. }
                | OperatorSpec::AbsDelay { input, .. }
                | OperatorSpec::Slew { input, .. }
                | OperatorSpec::LaplaceNd { input, .. }
                | OperatorSpec::IdtMod { input, .. }
                | OperatorSpec::Sin { input, .. }
                | OperatorSpec::Math { input, .. } => input,
            };
            let mut expressions = vec![input];
            if let OperatorSpec::Idt {
                reset: Some(reset), ..
            } = operator
            {
                expressions.push(reset);
            }
            for expression in expressions {
                let (nodes, states, operators) = crate::continuous::integral_dependency_edges(
                    expression,
                    &self.program,
                    &operator.origin().instance,
                )?;
                reads[n + i].extend(states);
                edges[n + i].extend(nodes);
                edges[n + i].extend(operators.into_iter().map(|j| n + j));
            }
        }
        loop {
            let mut changed = false;
            for i in 0..reads.len() {
                let inherited: BTreeSet<_> = edges[i]
                    .iter()
                    .flat_map(|&j| reads[j].iter().copied())
                    .collect();
                let old = reads[i].len();
                reads[i].extend(inherited);
                changed |= old != reads[i].len();
            }
            if !changed {
                break;
            }
        }
        reads.truncate(n);
        Ok(reads)
    }

    pub(crate) fn select_conditions(
        &self,
        events: &[usize],
        inputs: &[I],
        fired: &[usize],
        before: &[I],
        operators: &[I],
    ) -> Result<Selection, Error> {
        self.select_conditions_on_source_side(events, inputs, fired, before, operators, &[])
    }

    pub(crate) fn select_conditions_on_source_side(
        &self,
        events: &[usize],
        inputs: &[I],
        fired: &[usize],
        before: &[I],
        operators: &[I],
        sides: &[(usize, i8)],
    ) -> Result<Selection, Error> {
        let mut selection = self
            .conditions
            .select_with_source_sides(events, inputs, fired, before, sides)?;
        if self.node_conditions.has_active_event(events) {
            let program = self.selected_program_at_roots(before, inputs, fired)?;
            let map = crate::settlement_bounds::Bounds::for_program_with_operators(
                self,
                &Selection::default(),
                &program,
                operators,
            )?;
            let nodes = map.node_enclosures(inputs, before, operators)?;
            let observed = self.node_conditions.select_with_source_sides(
                events,
                &nodes[1..],
                fired,
                before,
                sides,
            )?;
            selection.actions.extend(observed.actions);
            selection.ordered_steps.extend(observed.ordered_steps);
            selection.decisions.extend(observed.decisions);
        }
        Ok(selection)
    }
}
