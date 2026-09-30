//! Explicit-modulus phase integral for bounded voltage-domain phase models.
use crate::idt::Idt;
use crate::interval::Interval as I;
use crate::ir::Error;

#[derive(Clone)]
pub(crate) struct IdtMod {
    integral: Idt,
    modulus: f64,
    offset: f64,
}

fn wrap(value: f64, modulus: f64, offset: f64) -> f64 {
    (value - offset).rem_euclid(modulus) + offset
}

impl IdtMod {
    pub(crate) fn enclosed(
        points: Vec<(f64, f64)>,
        bounds: Vec<I>,
        ic: f64,
        modulus: f64,
        offset: f64,
    ) -> Result<Self, Error> {
        if !modulus.is_finite() || modulus <= 0.0 || !offset.is_finite() {
            return Err(Error::new(
                "unsupported_operator",
                "idtmod requires finite offset and explicit positive finite modulus",
            ));
        }
        Ok(Self {
            integral: Idt::enclosed(points, bounds, ic)?,
            modulus,
            offset,
        })
    }

    pub(crate) fn value(&self, time: f64) -> Result<f64, Error> {
        let raw = self.integral.value(time)?;
        let value = wrap(raw, self.modulus, self.offset);
        if !value.is_finite() {
            return Err(Error::new("numerical_failure", "nonfinite idtmod query"));
        }
        Ok(value)
    }

    pub(crate) fn raw_value_bounds(&self, time: f64) -> Result<I, Error> {
        self.integral.value_bounds(time)
    }

    pub(crate) fn value_bounds(&self, time: f64) -> Result<I, Error> {
        let raw = self.raw_value_bounds(time)?;
        if !raw.finite() {
            return Err(Error::new(
                "waveform_accuracy",
                "nonfinite idtmod query enclosure",
            ));
        }
        if raw.hi - raw.lo >= self.modulus {
            return Ok(I {
                lo: self.offset,
                hi: self.offset + self.modulus,
            });
        }
        let nominal = self.integral.value(time)?;
        let nominal_wrapped = wrap(nominal, self.modulus, self.offset);
        let lo_turn = ((raw.lo - self.offset) / self.modulus).floor();
        let hi_turn = ((raw.hi - self.offset) / self.modulus).floor();
        if lo_turn == hi_turn {
            let lo = wrap(raw.lo, self.modulus, self.offset);
            let hi = wrap(raw.hi, self.modulus, self.offset);
            return Ok(I { lo, hi });
        }
        let width = raw.hi - raw.lo;
        let edge_distance = (nominal_wrapped - self.offset)
            .abs()
            .min((self.offset + self.modulus - nominal_wrapped).abs());
        if width <= 1e-9 * self.modulus.max(1.0) && edge_distance <= width.max(f64::EPSILON) {
            return Ok(I {
                lo: (nominal_wrapped - width).max(self.offset),
                hi: (nominal_wrapped + width).min(self.offset + self.modulus),
            });
        }
        Ok(I {
            lo: self.offset,
            hi: self.offset + self.modulus,
        })
    }

    pub(crate) fn next_breakpoint(&self, after: f64) -> Option<f64> {
        self.integral.next_breakpoint(after)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn history() -> IdtMod {
        IdtMod::enclosed(
            vec![(0.0, -0.25), (4.0, 0.75)],
            vec![I::point(-0.25), I::point(0.75)],
            0.875,
            1.0,
            0.0,
        )
        .unwrap()
    }

    #[test]
    fn wraps_negative_and_positive_phase_without_mutating_history() {
        let h = history();
        assert_eq!(h.value(0.0).unwrap(), 0.875);
        assert_eq!(h.value(1.0).unwrap(), 0.75);
        assert_eq!(h.value(2.0).unwrap(), 0.875);
        assert_eq!(h.value(4.0).unwrap(), 0.875);
        let retry = h.clone();
        assert_eq!(retry.value(4.0).unwrap(), h.value(4.0).unwrap());
    }

    #[test]
    fn uncertain_wrap_returns_the_declared_range() {
        let h = IdtMod::enclosed(
            vec![(0.0, 1.0), (1.0, 1.0)],
            vec![I { lo: 0.75, hi: 1.25 }; 2],
            0.4,
            1.0,
            -0.5,
        )
        .unwrap();
        assert_eq!(h.value_bounds(1.0).unwrap(), I { lo: -0.5, hi: 0.5 });
    }
}
