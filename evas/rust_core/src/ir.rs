//! The only executable model format for the voltage kernel.
use serde::{Deserialize, Serialize};

pub const SCHEMA_VERSION: u32 = 4;

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
    pub events: Vec<CrossEvent>,
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

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
pub enum Expression {
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
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Term {
    pub node: usize,
    pub coefficient: f64,
}

#[derive(Debug, Clone, Deserialize)]
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
    pub absolute: f64,
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
pub struct CrossEvent {
    pub guard: Expression,
    pub direction: i8,
    pub time_tolerance: f64,
    pub expression_tolerance: f64,
    pub assignments: Vec<Assignment>,
    pub origin: Origin,
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
    pub guard_value: f64,
    pub before: Vec<f64>,
    pub after: Vec<f64>,
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
