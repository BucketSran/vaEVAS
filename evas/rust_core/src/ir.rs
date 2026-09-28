//! The only executable model format for the first migration slice.
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Program {
    pub schema_version: u32,
    pub nodes: Vec<String>,
    pub contributions: Vec<Contribution>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Contribution {
    pub branch: String,
    pub positive: usize,
    pub negative: usize,
    pub rhs: Affine,
    pub origin: Origin,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Affine {
    pub constant: f64,
    pub terms: Vec<Term>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Term {
    pub node: usize,
    pub coefficient: f64,
}

#[derive(Debug, Deserialize)]
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

#[derive(Debug, Deserialize)]
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

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub program: Program,
    pub driven: Vec<String>,
    pub samples: Vec<Vec<f64>>,
    #[serde(default)]
    pub tolerances: Tolerances,
}

#[derive(Debug, Serialize)]
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
