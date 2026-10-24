//! Immutable source-position history inputs. This exports the executed graph,
//! including each RN boundary; guards delimit the epoch in which it is valid.
use super::*;

impl Plan {
    pub(crate) fn input_cell(&self, operator: usize, work: &Work) -> Result<Cell, Error> {
        work.debit(2, 1)?;
        let view = self
            .operators
            .get(operator)
            .and_then(Option::as_ref)
            .ok_or_else(|| invalid("history input lacks its source-position capture"))?;
        self.captured
            .get(view.input)
            .ok_or_else(|| invalid("history input capture is outside its graph"))?
            .copy(work)
    }
    pub(crate) fn input_expression(&self, operator: usize, work: &Work) -> Result<E, Error> {
        work.debit(2, 1)?;
        let view = self
            .operators
            .get(operator)
            .and_then(Option::as_ref)
            .ok_or_else(|| invalid("history input lacks its source-position capture"))?;
        self.history_expression(view.input, work)
    }
    pub(crate) fn history_expression(&self, root: Id, work: &Work) -> Result<E, Error> {
        work.debit(2, 0)?;
        if !self.work.same_owner(work) {
            return Err(invalid("history input cannot replace its request owner"));
        }
        let mut result = arena(self.graph.evaluate(
            &[root],
            &mut |operation, args: &[E]| {
                let child = |index: usize| -> Result<Box<E>, Error> {
                    let e = args
                        .get(index)
                        .ok_or_else(|| invalid("history input operand absent"))?;
                    crate::history_admission::charge_expression_copy(e, work)?;
                    Ok(Box::new(e.clone()))
                };
                work.debit(2, 128)?;
                Ok(match operation {
                    O::Literal(value) => crate::real_expression::literal(*value),
                    O::Affine { constant, terms } => {
                        work.debit(
                            2,
                            (terms.len() * std::mem::size_of::<ir::Term>() + 32) as u64,
                        )?;
                        E::Affine {
                            constant: *constant,
                            terms: terms.to_vec(),
                        }
                    }
                    O::State(state) => E::State { state: *state },
                    O::Operator(operator) => E::Operator {
                        operator: *operator,
                    },
                    O::Add => E::Add {
                        left: child(0)?,
                        right: child(1)?,
                    },
                    O::Multiply => E::Multiply {
                        left: child(0)?,
                        right: child(1)?,
                    },
                    O::Divide => E::Divide {
                        left: child(0)?,
                        right: child(1)?,
                    },
                    O::Power(exponent) => E::Power {
                        base: child(0)?,
                        exponent: *exponent,
                    },
                    O::Real(operation, origin) => E::RealBinary {
                        operation: *operation,
                        left: child(0)?,
                        right: child(1)?,
                        origin: origin_copy(origin, work)?,
                    },
                    O::Boundary(kind, origin) => E::RealBoundary {
                        kind: *kind,
                        value: child(0)?,
                        origin: origin_copy(origin, work)?,
                    },
                    _ => {
                        return Err(Error::new(
                            "unsupported_history_input",
                            "history input graph requires supported source real arithmetic",
                        ))
                    }
                })
            },
            &mut |e: &E| {
                crate::history_admission::charge_expression_copy(e, work)?;
                Ok(e.clone())
            },
            &mut |n| work.debit(2, n),
        ))?;
        result
            .pop()
            .ok_or_else(|| invalid("history input graph produced no root"))
    }
}
impl Plan {
    pub(crate) fn history_ranges(
        &self,
        roots: &[Id],
        nodes: &[I],
        states: &[I],
        context: &Context<'_>,
        w: &Work,
    ) -> Result<Vec<I>, Error> {
        w.debit(
            2,
            ((nodes.len() + states.len() + self.operators.len()) * 32 + 128) as u64,
        )?;
        let points = nodes
            .iter()
            .map(|b| (b.lo.to_bits() == b.hi.to_bits()).then_some(b.lo))
            .collect::<Vec<_>>();
        let state_points = states
            .iter()
            .map(|b| (b.lo.to_bits() == b.hi.to_bits()).then_some(b.lo))
            .collect::<Vec<_>>();
        let ops = vec![None; self.operators.len()];
        let bounds = vec![
            I {
                lo: f64::NEG_INFINITY,
                hi: f64::INFINITY
            };
            ops.len()
        ];
        self.evaluate(
            false,
            roots,
            &points,
            nodes,
            &state_points,
            states,
            &ops,
            &bounds,
            Some(context),
            w,
        )?
        .iter()
        .map(Cell::bound)
        .collect()
    }
}
