//! The only executable model format for the voltage kernel.
use serde::{Deserialize, Serialize};

pub const SCHEMA_VERSION: u32 = 33;

#[cfg(test)]
mod real_procedure_transport_tests {
    use super::*;
    use serde_json::{json, Value};

    fn request() -> Value {
        let origin = json!({"source":"round.va","line":1,"column":1,"instance":"x"});
        json!({
            "program": {
                "schema_version":33,"nodes":["0"],"contributions":[],
                "events":[{"trigger":{"kind":"timer","start":0.5,"period":0.0,
                    "time_tolerance":1e-12,"enabled":true},"body":[],
                    "origin":origin,"procedure_id":0,"expanded_statement_ordinal":2}],
                "real_bindings":[{"procedure_id":0,"name":"snap","origin":origin,"lifetime":"occurrence"}],
                "procedures":[{"procedure_id":0,"instance":"x","body":[
                    {"expanded_statement_ordinal":1,"action":{"kind":"real_bind","binding":0,"origin":origin,
                        "value":{"op":"real_boundary","kind":"snapshot","origin":origin,
                            "value":{"op":"real_binary","operation":"divide","origin":origin,
                                "left":{"op":"affine","constant":3.0,"terms":[]},
                                "right":{"op":"affine","constant":10.0,"terms":[]}}}}},
                    {"expanded_statement_ordinal":2,"action":{"kind":"event_gate","event":0}},
                    {"expanded_statement_ordinal":3,"action":{"kind":"display","format":"%g",
                        "args":[{"op":"real_local","binding":0}],"origin":origin}}
                ]}]
            },"driven":[],"samples":[[]]
        })
    }

    #[test]
    fn procedure_transport_keeps_bind_before_gate_and_shared_body_reference() {
        let input = request();
        let decoded = parse_request(&input.to_string()).expect("IR33 procedure transport");
        let encoded = serde_json::to_value(decoded).unwrap();
        assert_eq!(
            encoded["program"]["procedures"],
            input["program"]["procedures"]
        );
        assert_eq!(
            encoded["program"]["real_bindings"],
            input["program"]["real_bindings"]
        );
        assert_eq!(encoded["program"]["events"][0]["procedure_id"], 0);
    }

    #[test]
    fn old_ir_must_be_recompiled_before_new_real_semantics() {
        assert_eq!(
            check_schema_version(32).unwrap_err().kind,
            "unsupported_ir_version"
        );
    }

    #[test]
    fn real_transport_rejects_an_unknown_operation() {
        let mut input = request();
        input["program"]["procedures"][0]["body"][0]["action"]["value"]["value"]["operation"] =
            json!("fma");
        let error = parse_request(&input.to_string()).unwrap_err();
        assert_eq!(error.kind, "invalid_request");
    }

    #[test]
    fn recursive_procedure_control_keeps_bind_and_gate_at_their_source_positions() {
        for kind in ["procedure_if", "procedure_loop"] {
            let mut input = request();
            let body = input["program"]["procedures"][0]["body"].take();
            let origin = json!({"source":"round.va","line":1,"column":1,"instance":"x"});
            let mut action = json!({
                "kind":kind,"relation":"gt","origin":origin,
                "left":{"op":"affine","constant":1.0,"terms":[]},
                "right":{"op":"affine","constant":0.0,"terms":[]}
            });
            if kind == "procedure_if" {
                action["then_body"] = body;
                action["else_body"] = json!([]);
            } else {
                action["initialize"] = json!([]);
                action["body"] = body;
                action["update"] = json!([]);
            }
            input["program"]["procedures"][0]["body"] =
                json!([{"expanded_statement_ordinal":0,"action":action}]);
            let decoded =
                parse_request(&input.to_string()).expect("nested IR33 procedure transport");
            let encoded = serde_json::to_value(decoded).unwrap();
            assert_eq!(
                encoded["program"]["procedures"],
                input["program"]["procedures"]
            );
            assert_eq!(
                encoded["program"]["events"][0]["expanded_statement_ordinal"],
                2
            );
        }
    }

    #[test]
    fn step_bound_capture_retains_the_position_of_the_program_environment() {
        let mut input = request();
        let origin = input["program"]["real_bindings"][0]["origin"].clone();
        input["program"]["step_bounds"] = json!([{
            "value":{"op":"real_local","binding":0},
            "active":{"op":"affine","constant":1.0,"terms":[]},
            "origin":origin
        }]);
        input["program"]["procedures"][0]["body"]
            .as_array_mut()
            .unwrap()
            .push(json!({"expanded_statement_ordinal":4,
                   "action":{"kind":"step_bound_capture","step_bound":0}}));
        let decoded = parse_request(&input.to_string()).expect("IR33 bound-step source position");
        let encoded = serde_json::to_value(decoded).unwrap();
        assert_eq!(
            encoded["program"]["procedures"],
            input["program"]["procedures"]
        );
        assert_eq!(
            encoded["program"]["step_bounds"],
            input["program"]["step_bounds"]
        );
    }
}

pub fn check_schema_version(version: u64) -> Result<(), Error> {
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
    #[derive(Deserialize, Serialize)]
    struct Header {
        program: Version,
    }
    #[derive(Deserialize, Serialize)]
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

#[derive(Debug, Clone, Deserialize, Serialize)]
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
    #[serde(default)]
    pub step_bounds: Vec<StepBound>,
    #[serde(default)]
    pub procedures: Vec<AnalogProcedure>,
    #[serde(default)]
    pub real_bindings: Vec<RealBinding>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct StepBound {
    pub value: Expression,
    pub active: Expression,
    pub origin: Origin,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Contribution {
    pub branch: BranchIdentity,
    pub positive: usize,
    pub negative: usize,
    pub rhs: Expression,
    pub origin: Origin,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct BranchIdentity {
    pub instance: String,
    pub local_positive: String,
    pub local_negative: String,
    pub kind: ContributionKind,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ContributionKind {
    Voltage,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
pub enum Expression {
    /// One pure call activation. Body ordinals have their own strict DFS
    /// namespace under this origin, independent of the enclosing procedure.
    RealCall {
        origin: Origin,
        bindings: Vec<usize>,
        body: Vec<ProcedureStep>,
        result: Box<Expression>,
    },
    /// Recognized syntax with no numeric implementation. Static checking is
    /// unconditional; a selected execution fails before publishing any writes.
    UnsupportedSystemCall {
        function: String,
        seed: usize,
        args: Vec<Expression>,
        origin: Origin,
    },
    RealBinary {
        operation: RealOperation,
        left: Box<Expression>,
        right: Box<Expression>,
        origin: Origin,
    },
    RealBoundary {
        value: Box<Expression>,
        kind: RealBoundaryKind,
        origin: Origin,
    },
    RealLocal {
        binding: usize,
    },
    Forcing {
        value: Box<Expression>,
        origin: Origin,
        #[serde(default)]
        checked: Vec<Expression>,
    },
    ArrayRead {
        states: Vec<usize>,
        index: Box<Expression>,
        first: i32,
        last: i32,
        origin: Origin,
    },
    IntegerRound {
        value: Box<Expression>,
        origin: Origin,
    },
    CheckedInteger {
        value: Box<Expression>,
        origin: Origin,
    },
    CheckedIndex {
        index: Box<Expression>,
        first: i32,
        last: i32,
        origin: Origin,
    },
    IntegerPrimitive {
        function: IntegerFunction,
        args: Vec<IntegerOperand>,
        origin: Origin,
    },
    EventMath {
        function: EventMathFunction,
        args: Vec<Expression>,
        origin: Origin,
    },
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
    Divide {
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

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EventMathFunction {
    // Private numerical layout nodes. Raw transport must use the existing
    // source-owned Math/Sin specs and cannot deserialize these entry points.
    #[serde(skip_deserializing)]
    InternalSin,
    #[serde(skip_deserializing)]
    InternalCos,
    #[serde(skip_deserializing)]
    InternalExp,
    #[serde(skip_deserializing)]
    InternalLn,
    #[serde(skip_deserializing)]
    InternalSqrt,
    #[serde(skip_deserializing)]
    InternalTanh,
    Floor,
    Sqrt,
    Abs,
    Min,
    Max,
    /// Natural logarithm; physical sampled events only. The kernel proves a
    /// strictly positive argument enclosure before evaluation.
    Ln,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum IntegerFunction {
    Add,
    Subtract,
    Remainder,
    ShiftRight,
    BitAnd,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
pub enum IntegerOperand {
    IntegerLiteral {
        value: i32,
    },
    IntegerState {
        state: usize,
    },
    IntegerPrimitive {
        function: IntegerFunction,
        args: Vec<IntegerOperand>,
        origin: Origin,
    },
}

#[derive(Debug, Clone, Copy, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MathFunction {
    Cos,
    Exp,
    Ln,
    Sqrt,
    Tanh,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum OperatorSpec {
    Ddt {
        input: Expression,
        origin: Origin,
    },
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
    Math {
        function: MathFunction,
        input: Expression,
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
    pub fn origin(&self) -> &Origin {
        match self {
            Self::Ddt { origin, .. }
            | Self::Transition { origin, .. }
            | Self::AbsDelay { origin, .. }
            | Self::Idt { origin, .. }
            | Self::Slew { origin, .. }
            | Self::LaplaceNd { origin, .. }
            | Self::IdtMod { origin, .. }
            | Self::Sin { origin, .. }
            | Self::Math { origin, .. } => origin,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Term {
    pub node: usize,
    pub coefficient: f64,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Origin {
    pub source: String,
    pub line: usize,
    pub column: usize,
    pub instance: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub expansion: Vec<(String, i32)>,
}

impl Origin {
    pub fn valid_expansion(&self) -> bool {
        self.expansion.len() <= 64
            && self.expansion.iter().all(|(name, _)| {
                let mut bytes = name.bytes();
                bytes
                    .next()
                    .is_some_and(|c| c == b'_' || c.is_ascii_alphabetic())
                    && bytes.all(|c| c == b'_' || c.is_ascii_alphanumeric())
            })
    }

    pub fn label(&self) -> String {
        format!(
            "{}:{}:{} ({})",
            self.source, self.line, self.column, self.instance
        )
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
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

#[derive(Debug, Clone, Deserialize, Serialize)]
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
    /// Internal certificate transport; exposed only by ObservationEvidence.
    #[serde(skip)]
    pub certified_voltage_bounds: Option<Vec<[f64; 2]>>,
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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub strobe_evidence: Option<StrobeEvidence>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub portability_advisories: Option<PortabilityAdvisories>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub observation_evidence: Option<ObservationEvidence>,
    pub engine: String,
    pub schema_version: u32,
    pub nodes: Vec<String>,
    pub solutions: Vec<Solution>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transient: Option<TransientTrace>,
}

/// Optional, versioned evidence for the returned transient observation rows.
/// Bounds and origins index solutions/transient.times; nodes binds column order.
#[derive(Debug, Serialize)]
pub struct ObservationEvidence {
    pub schema_version: u32,
    pub nodes: Vec<String>,
    pub effective_controls: EffectiveObservationControls,
    pub sample_origins: Vec<&'static str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub initial_settled: Option<bool>,
    #[serde(rename = "voltage_bounds_V")]
    pub voltage_bounds_v: Vec<Option<Vec<[f64; 2]>>>,
}

#[derive(Debug, Serialize)]
pub struct EffectiveObservationControls {
    #[serde(rename = "absolute_V")]
    pub absolute_v: f64,
    pub relative: f64,
    pub stop_s: f64,
    pub max_step_s: f64,
    pub max_step_applied: bool,
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

#[derive(Debug, Clone, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StateKind {
    Real,
    Integer,
}

/// IR18 keeps the constant wire shape and adds a structurally checked predicate.
/// An expression must resolve to exact 0/1 before constructing an event model.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(untagged)]
pub enum StateInitial {
    Constant(f64),
    Predicate(Expression),
}

impl From<f64> for StateInitial {
    fn from(value: f64) -> Self {
        Self::Constant(value)
    }
}

impl StateInitial {
    pub fn constant(&self) -> Result<f64, Error> {
        match self {
            Self::Constant(value) => Ok(*value),
            Self::Predicate(_) => Err(Error::new(
                "unsupported_initialization",
                "initial predicate requires driven-input resolution",
            )),
        }
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct State {
    pub instance: String,
    pub name: String,
    pub kind: StateKind,
    pub initial: StateInitial,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Assignment {
    pub state: usize,
    pub rhs: Expression,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Event {
    pub trigger: EventTrigger,
    pub body: Vec<Statement>,
    pub origin: Origin,
    #[serde(default)]
    pub procedure_id: Option<usize>,
    #[serde(default)]
    pub expanded_statement_ordinal: Option<u64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RealOperation {
    Add,
    Subtract,
    Multiply,
    Divide,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RealBoundaryKind {
    Store,
    Sample,
    Snapshot,
    Argument,
    Return,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RealBindingLifetime {
    Occurrence,
    Call,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct RealBinding {
    pub procedure_id: usize,
    pub name: String,
    pub origin: Origin,
    pub lifetime: RealBindingLifetime,
}

/// Executable source order within one elaborated analog block. Event bodies
/// remain owned by Program.events; a gate never carries a second body copy.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct AnalogProcedure {
    pub procedure_id: usize,
    pub instance: String,
    pub body: Vec<ProcedureStep>,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct ProcedureStep {
    /// Unique within the procedure, in elaborated depth-first source order.
    /// Runtime loop iterations reuse this source identity.
    pub expanded_statement_ordinal: u64,
    pub action: ProcedureAction,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(untagged)]
pub enum ProcedureAction {
    Statement(Statement),
    Control(ProcedureControl),
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum ProcedureControl {
    ProcedureIf {
        relation: Relation,
        left: Box<Expression>,
        right: Box<Expression>,
        then_body: Vec<ProcedureStep>,
        else_body: Vec<ProcedureStep>,
        origin: Origin,
    },
    ProcedureLoop {
        initialize: Vec<ProcedureStep>,
        relation: Relation,
        left: Box<Expression>,
        right: Box<Expression>,
        body: Vec<ProcedureStep>,
        update: Vec<ProcedureStep>,
        origin: Origin,
    },
    RealBind {
        binding: usize,
        value: Expression,
        origin: Origin,
    },
    EventGate {
        event: usize,
    },
    ContributionCapture {
        contribution: usize,
    },
    StepBoundCapture {
        step_bound: usize,
    },
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Statement {
    ArrayWrite {
        states: Vec<usize>,
        index: Box<Expression>,
        rhs: Expression,
        first: i32,
        last: i32,
        origin: Origin,
    },
    Loop {
        initialize: Vec<Statement>,
        relation: Relation,
        left: Box<Expression>,
        right: Box<Expression>,
        body: Vec<Statement>,
        update: Vec<Statement>,
        origin: Origin,
    },
    Assign(Assignment),
    Display {
        format: String,
        args: Vec<Expression>,
        origin: Origin,
    },
    If {
        relation: Relation,
        left: Box<Expression>,
        right: Box<Expression>,
        then_body: Vec<Statement>,
        else_body: Vec<Statement>,
        origin: Origin,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Relation {
    Lt,
    Le,
    Gt,
    Ge,
}

impl Event {
    /// Static validation visits both arms; execution uses only the selected arm.
    pub fn assignments(&self) -> Vec<Assignment> {
        fn visit(body: &[Statement], out: &mut Vec<Assignment>) {
            for statement in body {
                match statement {
                    Statement::ArrayWrite { states, rhs, .. } => {
                        out.extend(states.iter().map(|&state| Assignment {
                            state,
                            rhs: rhs.clone(),
                        }));
                    }
                    Statement::Loop {
                        initialize,
                        body,
                        update,
                        ..
                    } => {
                        visit(initialize, out);
                        visit(body, out);
                        visit(update, out);
                    }
                    Statement::Assign(a) => out.push(a.clone()),
                    Statement::Display { .. } => {}
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

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum EventTrigger {
    FinalStep {},
    InitialStep {},
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
    HeldTimer {
        start: Box<Expression>,
        period: Box<Expression>,
        time_tolerance: f64,
        enabled: Box<Expression>,
    },
}

impl EventTrigger {
    /// OR groups share a body but retain independent trigger call identities.
    pub fn leaves(&self) -> Result<Vec<&Self>, Error> {
        match self {
            Self::Or { triggers } => {
                if triggers.len() < 2 || triggers.iter().any(|t| matches!(t, Self::Or { .. })) {
                    return Err(Error::new(
                        "invalid_ir",
                        "event OR requires at least two cross/timer leaves",
                    ));
                }
                Ok(triggers.iter().collect())
            }
            _ => Ok(vec![self]),
        }
    }
}

/// A voltage band alone permits arbitrary time variation. An exact original
/// curve additionally defines shape; the kernel verifies it lies in the band.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(untagged)]
pub enum SourceError {
    Voltage(f64),
    Shaped(ShapedSourceError),
}

impl SourceError {
    pub fn bound(&self) -> f64 {
        match self {
            Self::Voltage(value) => *value,
            Self::Shaped(shape) => shape.voltage_error_bound_v,
        }
    }

    pub fn shape(&self) -> Option<&ShapedSourceError> {
        match self {
            Self::Voltage(_) => None,
            Self::Shaped(shape) => Some(shape),
        }
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ShapedSourceError {
    #[serde(rename = "voltage_error_bound_V")]
    pub voltage_error_bound_v: f64,
    pub exact_knots: Vec<ExactSourceKnot>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ExactSourceKnot {
    pub time_numerator: String,
    pub time_denominator: String,
    #[serde(rename = "value_V")]
    pub value_v: f64,
}

fn source_errors<'de, D: serde::Deserializer<'de>>(
    deserializer: D,
) -> Result<Option<Vec<SourceError>>, D::Error> {
    Vec::<SourceError>::deserialize(deserializer).map(Some)
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct TransientInputs {
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub analytic_sources: Vec<Option<AnalyticSource>>,
    #[serde(
        default,
        rename = "pwl_errors_V",
        deserialize_with = "source_errors",
        skip_serializing_if = "Option::is_none"
    )]
    pub pwl_errors_v: Option<Vec<SourceError>>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub strobetimes: Vec<f64>,
    pub pwl: Vec<Vec<[f64; 2]>>,
    pub output_times: Vec<f64>,
    pub stop: f64,
    pub max_step: f64,
}

/// Computed forced points, independent of the saved output grid.
#[derive(Debug, Serialize)]
pub struct StrobeEvidence {
    pub schema_version: u32,
    pub times: Vec<f64>,
    pub sample_origins: Vec<&'static str>,
    #[serde(rename = "voltages_V")]
    pub voltages_v: Vec<Vec<f64>>,
}

#[derive(Debug, Serialize)]
pub struct EventRecord {
    // Representative storage time; a nonpoint actual observation is enclosed
    // separately, rather than falsely reporting the representative as exact.
    pub time: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub observation_time_bounds: Option<[f64; 2]>,
    pub event: usize,
    pub origin: String,
    pub kind: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub guard_value: Option<f64>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub fired_triggers: Vec<FiredTrigger>,
    pub before: Vec<f64>,
    pub after: Vec<f64>,
    #[serde(skip)]
    pub display_records: Vec<DisplayRecord>,
}

#[derive(Debug, Serialize)]
pub struct FiredTrigger {
    pub trigger: usize,
    pub kind: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub guard_value: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub time_bounds: Option<[f64; 2]>,
}

#[derive(Debug, Clone, Serialize)]
pub struct DisplayRecord {
    pub time: f64,
    pub event: usize,
    pub origin: String,
    pub text: String,
}

#[derive(Debug, Serialize)]
pub struct TransientTrace {
    pub times: Vec<f64>,
    pub state_names: Vec<String>,
    pub states: Vec<Vec<f64>>,
    pub events: Vec<EventRecord>,
    pub display_records: Vec<DisplayRecord>,
    pub accepted_steps: usize,
    pub discarded_trials: usize,
}

/// Bounded, nonblocking local portability notices, independent of IR versions.
#[derive(Debug, Serialize)]
pub struct PortabilityAdvisories {
    pub schema_version: u32,
    pub record_limit: usize,
    pub records: Vec<PortabilityAdvisory>,
    pub model_records: Vec<ModelPortabilityAdvisory>,
    pub dropped_records: usize,
    pub truncated: bool,
}

#[derive(Debug, Serialize)]
pub struct PortabilityAdvisory {
    pub code: &'static str,
    pub nonblocking: bool,
    pub message: &'static str,
    pub event_record: usize,
    pub event: usize,
    pub trigger: usize,
    pub origin: String,
    pub query_source: &'static str,
    pub query_index: usize,
    pub query_time_s: f64,
    pub time_bounds_s: [f64; 2],
}

/// A source-level risk notice, not an observed wrap or a time certificate.
#[derive(Debug, Serialize)]
pub struct ModelPortabilityAdvisory {
    pub code: &'static str,
    pub nonblocking: bool,
    pub message: &'static str,
    pub operator: usize,
    pub origin: String,
}

/// Explicit finite source-value contract; no vendor default is inferred.
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum AnalyticSource {
    Sine {
        sinedc: f64,
        ampl: f64,
        freq: f64,
        sinephase: f64,
        source_name: String,
        terminals: [String; 2],
        polarity: i8,
        parameter_origin: String,
    },
}
