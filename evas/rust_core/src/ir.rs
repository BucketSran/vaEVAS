//! The only executable model format for the voltage kernel.
use serde::{Deserialize, Serialize};

pub const SCHEMA_VERSION: u32 = 15;

pub(crate) fn check_schema_version(version: u64) -> Result<(), Error> {
    if version != u64::from(SCHEMA_VERSION) {
        return Err(Error::new(
            "unsupported_ir_version",
            format!("expected voltage/event IR version {SCHEMA_VERSION}, got {version}; recompile the original VA"),
        ));
    }
    Ok(())
}

/// Check the version before decoding version-specific contribution fields.
pub fn parse_request(input: &str) -> Result<Request, Error> {
    #[derive(Deserialize)]
    struct Header {
        program: Version,
    }
    #[derive(Deserialize)]
    struct Version {
        schema_version: u64,
    }
    let header: Header =
        serde_json::from_str(input).map_err(|e| Error::new("invalid_request", e.to_string()))?;
    check_schema_version(header.program.schema_version)?;
    // Decode the original bytes so duplicate fields remain errors. The header
    // skips samples instead of storing a second copy of the full request.
    serde_json::from_str(input).map_err(|e| Error::new("invalid_request", e.to_string()))
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Program {
    pub schema_version: u32,
    pub nodes: Vec<String>,
    pub contributions: Vec<Contribution>,
    #[serde(default)]
    pub states: Vec<State>,
    #[serde(default)]
    pub events: Vec<Event>,
    #[serde(default)]
    pub operators: Vec<OperatorSpec>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Contribution {
    pub branch: BranchIdentity,
    pub positive: usize,
    pub negative: usize,
    pub rhs: Expression,
    pub origin: Origin,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BranchIdentity {
    pub instance: String,
    pub local_positive: String,
    pub local_negative: String,
    pub kind: ContributionKind,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ContributionKind {
    Voltage,
}

#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
pub enum Expression {
    Operator {
        operator: usize,
    },
    State {
        state: usize,
    },
    Affine {
        constant: f64,
        terms: Vec<Term>,
    },
    Add {
        left: Box<Expression>,
        right: Box<Expression>,
    },
    Multiply {
        left: Box<Expression>,
        right: Box<Expression>,
    },
    Power {
        base: Box<Expression>,
        exponent: u32,
    },
    Select {
        relation: Relation,
        left: Box<Expression>,
        right: Box<Expression>,
        then_value: Box<Expression>,
        else_value: Box<Expression>,
        origin: Origin,
    },
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum OperatorSpec {
    Idt {
        input: Expression,
        ic: f64,
        #[serde(default)]
        reset: Option<Expression>,
        origin: Origin,
    },
    IdtMod {
        input: Expression,
        ic: f64,
        modulus: f64,
        offset: f64,
        origin: Origin,
    },
    Sin {
        input: Expression,
        origin: Origin,
    },
    AbsDelay {
        input: Expression,
        delay: f64,
        origin: Origin,
    },
    Transition {
        input: Expression,
        delay: f64,
        rise: f64,
        fall: f64,
        origin: Origin,
    },
    Slew {
        input: Expression,
        rise: f64,
        fall: f64,
        origin: Origin,
    },
    LaplaceNd {
        input: Expression,
        numerator: Vec<f64>,
        denominator: Vec<f64>,
        origin: Origin,
    },
}

impl OperatorSpec {
    pub(crate) fn origin(&self) -> &Origin {
        match self {
            Self::Transition { origin, .. }
            | Self::AbsDelay { origin, .. }
            | Self::Idt { origin, .. }
            | Self::Slew { origin, .. }
            | Self::LaplaceNd { origin, .. }
            | Self::IdtMod { origin, .. }
            | Self::Sin { origin, .. } => origin,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Term {
    pub node: usize,
    pub coefficient: f64,
}

#[derive(Debug, Clone, PartialEq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Origin {
    pub source: String,
    pub line: usize,
    pub column: usize,
    pub instance: String,
}

impl Origin {
    pub fn label(&self) -> String {
        format!(
            "{}:{}:{} ({})",
            self.source, self.line, self.column, self.instance
        )
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields, default)]
pub struct Tolerances {
    #[serde(alias = "vabstol")]
    pub absolute: f64,
    #[serde(alias = "reltol")]
    pub relative: f64,
}

impl Default for Tolerances {
    fn default() -> Self {
        Self {
            absolute: 1e-12,
            relative: 1e-10,
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub program: Program,
    pub driven: Vec<String>,
    pub samples: Vec<Vec<f64>>,
    #[serde(default)]
    pub transient: Option<TransientInputs>,
    #[serde(default)]
    pub tolerances: Tolerances,
}

#[derive(Debug, Clone, Serialize)]
pub struct Solution {
    /// Same node order as Program.nodes; ground is always exactly zero.
    pub voltages: Vec<f64>,
    pub max_residual_v: f64,
    pub max_residual_ratio: f64,
    /// Nonlinear-only diagnostics; absent on the unchanged affine path.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_scaled_residual_ratio: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_voltage_correction_v: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_voltage_correction_ratio: Option<f64>,
}

#[derive(Debug, Serialize)]
pub struct Response {
    pub engine: String,
    pub schema_version: u32,
    pub nodes: Vec<String>,
    pub solutions: Vec<Solution>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transient: Option<TransientTrace>,
}

#[derive(Debug, Serialize)]
pub struct Error {
    pub kind: &'static str,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sample: Option<usize>,
}

impl Error {
    pub fn new(kind: &'static str, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
            sample: None,
        }
    }
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum StateKind {
    Real,
    Integer,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct State {
    pub instance: String,
    pub name: String,
    pub kind: StateKind,
    pub initial: f64,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Assignment {
    pub state: usize,
    pub rhs: Expression,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Event {
    pub trigger: EventTrigger,
    pub body: Vec<Statement>,
    pub origin: Origin,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Statement {
    Assign(Assignment),
    If {
        relation: Relation,
        left: Box<Expression>,
        right: Box<Expression>,
        then_body: Vec<Statement>,
        else_body: Vec<Statement>,
        origin: Origin,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Relation {
    Lt,
    Le,
    Gt,
    Ge,
}

impl Event {
    /// Static validation visits both arms; execution uses only the selected arm.
    pub(crate) fn assignments(&self) -> Vec<&Assignment> {
        fn visit<'a>(body: &'a [Statement], out: &mut Vec<&'a Assignment>) {
            for statement in body {
                match statement {
                    Statement::Assign(a) => out.push(a),
                    Statement::If {
                        then_body,
                        else_body,
                        ..
                    } => {
                        visit(then_body, out);
                        visit(else_body, out);
                    }
                }
            }
        }
        let mut out = Vec::new();
        visit(&self.body, &mut out);
        out
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum EventTrigger {
    Or {
        triggers: Vec<EventTrigger>,
    },
    Cross {
        guard: Expression,
        direction: i8,
        time_tolerance: f64,
        expression_tolerance: f64,
    },
    Timer {
        start: f64,
        period: f64,
        time_tolerance: f64,
        enabled: bool,
    },
}

impl EventTrigger {
    /// OR groups share a body but retain independent cross call identities.
    pub(crate) fn leaves(&self) -> Result<Vec<&Self>, Error> {
        match self {
            Self::Or { triggers } => {
                if triggers.len() < 2 || triggers.iter().any(|t| !matches!(t, Self::Cross { .. })) {
                    return Err(Error::new(
                        "invalid_ir",
                        "event OR requires at least two cross leaves",
                    ));
                }
                Ok(triggers.iter().collect())
            }
            _ => Ok(vec![self]),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TransientInputs {
    pub pwl: Vec<Vec<[f64; 2]>>,
    pub output_times: Vec<f64>,
    pub stop: f64,
    pub max_step: f64,
}

#[derive(Debug, Serialize)]
pub struct EventRecord {
    pub time: f64,
    pub event: usize,
    pub origin: String,
    pub kind: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub guard_value: Option<f64>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub fired_triggers: Vec<FiredTrigger>,
    pub before: Vec<f64>,
    pub after: Vec<f64>,
}

#[derive(Debug, Serialize)]
pub struct FiredTrigger {
    pub trigger: usize,
    pub guard_value: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub time_bounds: Option<[f64; 2]>,
}

#[derive(Debug, Serialize)]
pub struct TransientTrace {
    pub times: Vec<f64>,
    pub state_names: Vec<String>,
    pub states: Vec<Vec<f64>>,
    pub events: Vec<EventRecord>,
    pub accepted_steps: usize,
    pub discarded_trials: usize,
}
