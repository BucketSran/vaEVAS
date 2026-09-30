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

fn full_range(modulus: f64, offset: f64) -> Result<I, Error> {
    let hi = (I::point(offset) + I::point(modulus)).hi;
    let result = I { lo: offset, hi };
    if !result.finite() || result.lo > result.hi {
        return Err(Error::new(
            "waveform_accuracy",
            "idtmod declared range is not a finite representable interval",
        ));
    }
    Ok(result)
}

fn intersect(a: I, b: I) -> I {
    I {
        lo: a.lo.max(b.lo),
        hi: a.hi.min(b.hi),
    }
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

    pub(crate) fn value_bounds_segments(&self, time: f64) -> Result<Vec<I>, Error> {
        let raw = self.raw_value_bounds(time)?;
        if !raw.finite() {
            return Err(Error::new(
                "waveform_accuracy",
                "nonfinite idtmod query enclosure",
            ));
        }
        let declared = full_range(self.modulus, self.offset)?;
        if raw.hi - raw.lo >= self.modulus {
            return Ok(vec![declared]);
        }
        let normalized = (raw - I::point(self.offset)) / I::point(self.modulus);
        if !normalized.finite() {
            return Err(Error::new(
                "waveform_accuracy",
                "cannot certify idtmod turn for nonfinite normalized phase",
            ));
        }
        let lo_turn = normalized.lo.floor();
        let hi_turn = normalized.hi.floor();
        if lo_turn.abs().max(hi_turn.abs()) > 4_503_599_627_370_496.0 {
            return Err(Error::new(
                "waveform_accuracy",
                "cannot certify idtmod wrap after a non-representable turn count",
            ));
        }
        let wrap_for_turn = |turn: f64| -> Result<I, Error> {
            let wrapped = intersect(raw - I::point(turn) * I::point(self.modulus), declared);
            if !wrapped.finite() || wrapped.lo > wrapped.hi {
                return Err(Error::new(
                    "waveform_accuracy",
                    "nonfinite idtmod wrapped enclosure",
                ));
            }
            Ok(wrapped)
        };
        if lo_turn == hi_turn {
            return Ok(vec![wrap_for_turn(lo_turn)?]);
        }
        if hi_turn - lo_turn != 1.0 {
            return Ok(vec![declared]);
        }
        Ok(vec![wrap_for_turn(lo_turn)?, wrap_for_turn(hi_turn)?])
    }

    pub(crate) fn value_bounds(&self, time: f64) -> Result<I, Error> {
        let segments = self.value_bounds_segments(time)?;
        if segments.len() == 1 {
            Ok(segments[0])
        } else {
            full_range(self.modulus, self.offset)
        }
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

    #[test]
    fn tiny_uncertain_wrap_does_not_drop_the_opposite_side() {
        let h = IdtMod::enclosed(
            vec![(0.0, 0.0), (1.0, 0.0)],
            vec![
                I {
                    lo: -f64::EPSILON,
                    hi: f64::EPSILON,
                };
                2
            ],
            1.0,
            1.0,
            0.0,
        )
        .unwrap();
        assert_eq!(h.value_bounds(1.0).unwrap(), I { lo: 0.0, hi: 1.0 });
    }

    #[test]
    fn huge_offset_nonbinary_modulus_keeps_an_outward_declared_range() {
        let declared = full_range(0.1, 1.0e16).unwrap();
        assert_eq!(declared.lo, 1.0e16);
        assert!(declared.hi > 1.0e16);
        let h = IdtMod::enclosed(
            vec![(0.0, 0.0), (1.0, 0.0)],
            vec![I { lo: -0.2, hi: 0.2 }; 2],
            1.0e16,
            0.1,
            1.0e16,
        )
        .unwrap();
        assert_eq!(h.value_bounds(1.0).unwrap(), declared);
    }

    #[test]
    fn huge_turn_bounds_are_rejected_when_turn_count_is_not_exact() {
        let h = IdtMod::enclosed(
            vec![(0.0, 0.0), (1.0, 0.0)],
            vec![I::point(0.0); 2],
            9_007_199_254_740_992.0,
            1.0,
            0.0,
        )
        .unwrap();
        assert_eq!(h.value_bounds(0.0).unwrap_err().kind, "waveform_accuracy");
    }
}
