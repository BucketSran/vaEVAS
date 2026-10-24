"""Restricted EVAS event IR -> XSPICE backend. No model-specific physical body."""

import hashlib
import json
import math
from pathlib import Path
import re
import importlib.resources

from ..frontend import Instance, compile_sources, parse_sources
from ..parameters import bind_parameters
from ..errors import CompileError
from ..ir import SCHEMA_VERSION
from .timer_plan import plan as timer_plan

BACKEND_VERSION = 2


class Unsupported(CompileError):
    def __init__(self, message):
        super().__init__(message, code="xspice_unsupported")


def identifier(name):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise Unsupported("XSPICE identifier outside this slice: " + name)
    return name


def number(value):
    value = float(value)
    if not math.isfinite(value):
        raise Unsupported("nonfinite numeric value")
    return repr(value)


class Emitter:
    def __init__(self, ir, inputs):
        self.ir, self.inputs = ir, inputs
        self.transition_slots = {index: slot for slot, index in enumerate(
            i for i, op in enumerate(ir["operators"]) if op["kind"] == "transition")}
        self.bind_values = {}
        self.bind_order = []
        self.ready_bindings = set()
        self.needs_div = False
        self.local_code = ""
        self.nlocal = 0
        for procedure in ir.get("procedures") or []:
            for statement in procedure["body"]:
                action = statement["action"]
                if action["kind"] != "real_bind":
                    continue
                index = action["binding"]
                if index in self.bind_values:
                    raise Unsupported("duplicate real binding")
                self.bind_values[index] = action["value"]
                self.bind_order.append(index)

    def expr(self, expr):
        op = expr["op"]
        if op == "affine":
            result = "ad_const(" + number(expr["constant"]) + ")"
            for term in expr["terms"]:
                name = self.ir["nodes"][term["node"]]
                if name == "0":
                    value = "ad_const(0.0)"
                elif name == "$abstime":
                    value = "ad_const(TIME)"
                elif name in self.inputs:
                    value = "inputs[" + str(self.inputs.index(name)) + "]"
                else:
                    raise Unsupported(
                        "expression reads an output or internal node: " + name
                    )
                result = (
                    "ad_add("
                    + result
                    + ", ad_mul(ad_const("
                    + number(term["coefficient"])
                    + "), "
                    + value
                    + "))"
                )
            return result
        if op == "operator":
            index = expr["operator"]
            if not 0 <= index < len(self.ir["operators"]):
                raise Unsupported("invalid operator index")
            operator = self.ir["operators"][index]
            if operator["kind"] == "math" and operator["function"] == "tanh":
                return "ad_tanh(" + self.expr(operator["input"]) + ")"
            if index not in self.transition_slots:
                raise Unsupported("operator outside transition/tanh slice")
            return "ad_const(transition_value(&cur->tr[" + str(self.transition_slots[index]) + "], TIME))"
        if op == "state":
            index = expr["state"]
            if not 0 <= index < len(self.ir["states"]):
                raise Unsupported("invalid state index")
            return "states[" + str(index) + "]"
        if op in ("add", "multiply"):
            return (
                ("ad_add" if op == "add" else "ad_mul")
                + "("
                + self.expr(expr["left"])
                + ", "
                + self.expr(expr["right"])
                + ")"
            )
        if op == "real_binary":
            # One source operation, rounded before its parent. Same Dual
            # helpers as the legacy add/multiply forms; do not reassociate.
            # Division is the constant-denominator threshold used by the
            # admitted alias guards. Subtraction stays rejected.
            operation = expr.get("operation")
            if operation == "divide":
                self.needs_div = True
                function = "ad_div"
            else:
                function = {"add": "ad_add", "multiply": "ad_mul"}.get(operation)
            if function is None:
                raise Unsupported(
                    "real operation outside this slice: " + str(operation)
                )
            return (
                function
                + "("
                + self.expr(expr["left"])
                + ", "
                + self.expr(expr["right"])
                + ")"
            )
        if op == "real_local":
            index = expr["binding"]
            if index not in self.ready_bindings:
                raise Unsupported("real binding is used before it is defined")
            return "locals[" + str(index) + "]"
        if op == "real_boundary":
            # store/sample/snapshot/argument/return name the rounding point.
            # The generated value is the inner expression.
            if expr.get("kind") not in ("store", "sample", "snapshot", "argument", "return"):
                raise Unsupported(
                    "real boundary outside this slice: " + str(expr.get("kind"))
                )
            return self.expr(expr["value"])
        if op == "select":
            return ("(" + self.condition(expr) + " ? "
                    + self.expr(expr["then_value"]) + " : "
                    + self.expr(expr["else_value"]) + ")")
        raise Unsupported("IR expression operation outside this slice: " + op)

    def condition(self, expr):
        relations = {"lt": 0, "le": 1, "gt": 2, "ge": 3}
        if expr["relation"] not in relations:
            raise Unsupported("unsupported conditional relation")
        return ("ad_predicate(" + self.expr(expr["left"]) + ", "
                + self.expr(expr["right"]) + ", "
                + str(relations[expr["relation"]]) + ")")

    def _walk(self, node, visit):
        if isinstance(node, dict):
            visit(node)
            for value in node.values():
                self._walk(value, visit)
        elif isinstance(node, (list, tuple)):
            for value in node:
                self._walk(value, visit)

    def _require_binding(self, index):
        bindings = self.ir.get("real_bindings") or []
        if not isinstance(index, int) or not 0 <= index < len(bindings):
            raise Unsupported("invalid real binding")
        if index not in self.bind_values:
            raise Unsupported("real binding is not defined in this procedure")
        if bindings[index].get("lifetime") != "occurrence":
            raise Unsupported("only occurrence-lifetime input bindings are supported")
        return index

    def prepare_locals(self, initial_events, events):
        """Evaluate occurrence bindings once per call, in procedure order.

        Only bindings reachable from a guard, event body, contribution, or
        operator are emitted. Unreferenced event-argument bindings stay out
        of the generated model.
        """
        roots = [self.ir.get("contributions"), self.ir.get("operators")]
        for event in [*initial_events, *events]:
            roots.append(event["body"])
            if event["trigger"]["kind"] == "cross":
                roots.append(event["trigger"]["guard"])
        seen = set()

        def visit(node):
            if node.get("op") != "real_local":
                return
            index = self._require_binding(node["binding"])
            if index in seen:
                return
            seen.add(index)
            self._walk(self.bind_values[index], visit)

        for root in roots:
            self._walk(root, visit)
        self.ready_bindings = set()
        lines = []
        for index in self.bind_order:
            if index not in seen:
                continue
            lines.append(
                "locals[" + str(index) + "] = " + self.expr(self.bind_values[index]) + ";"
            )
            self.ready_bindings.add(index)
        if seen - self.ready_bindings:
            raise Unsupported("real binding is used before it is defined")
        self.local_code = "\n".join(lines)
        self.nlocal = max(seen) + 1 if seen else 0

    def pure_constant(self, expr, stack):
        op = expr["op"]
        if op == "real_boundary":
            return self.pure_constant(expr["value"], stack)
        if op == "affine":
            total = float(expr["constant"])
            for term in expr["terms"]:
                if term["coefficient"] == 0:
                    continue
                if self.ir["nodes"][term["node"]] != "0":
                    return None
            if not math.isfinite(total):
                return None
            return total
        if op == "real_local":
            index = self._require_binding(expr["binding"])
            if index in stack:
                return None
            stack.add(index)
            try:
                return self.pure_constant(self.bind_values[index], stack)
            finally:
                stack.remove(index)
        return None

    def affine_guard(self, expr, stack=None):
        """Admission only. Runtime expression retains IR operation ordering."""
        if stack is None:
            stack = set()
        if expr["op"] == "real_boundary":
            return self.affine_guard(expr["value"], stack)
        if expr["op"] == "real_local":
            index = self._require_binding(expr["binding"])
            if index in stack:
                raise Unsupported("cyclic input binding")
            stack.add(index)
            try:
                return self.affine_guard(self.bind_values[index], stack)
            finally:
                stack.remove(index)
        if expr["op"] == "affine":
            for term in expr["terms"]:
                if self.ir["nodes"][term["node"]] not in ["0", *self.inputs]:
                    raise Unsupported("cross guard must read input voltages only")
            return any(
                self.ir["nodes"][term["node"]] in self.inputs
                and term["coefficient"] != 0
                for term in expr["terms"]
            )
        if expr["op"] == "add" or (
            expr["op"] == "real_binary" and expr.get("operation") == "add"
        ):
            left = self.affine_guard(expr["left"], stack)
            right = self.affine_guard(expr["right"], stack)
            return left or right
        if expr["op"] in ("multiply", "real_binary") and (
            expr["op"] == "multiply" or expr.get("operation") == "multiply"
        ):
            left = self.affine_guard(expr["left"], stack)
            right = self.affine_guard(expr["right"], stack)
            if left and right:
                raise Unsupported("nonlinear cross guard is outside this slice")
            return left or right
        if expr["op"] == "real_binary" and expr.get("operation") == "divide":
            # A constant denominator keeps the guard affine. Input-dependent
            # or zero divisors are a different operation and stay outside.
            denominator = self.pure_constant(expr["right"], stack)
            if (
                denominator is None
                or not math.isfinite(denominator)
                or denominator == 0.0
            ):
                raise Unsupported("nonlinear cross guard is outside this slice")
            return self.affine_guard(expr["left"], stack)
        raise Unsupported("cross guard must be affine in input voltages")


def make_ifs(ports, directions, parameters, model_name, output_references):
    count = len(ports)

    def row(key, values):
        return key + ": " + " ".join(values) + "\n"

    result = (
        "NAME_TABLE:\nC_Function_Name: cm_evas_ir\nSpice_Model_Name: "
        + model_name
        + '\nDescription: "Generated EVAS voltage-event model"\n\nPORT_TABLE:\n'
    )
    result += row("Port_Name", ports)
    result += row("Description", ['"' + p + '"' for p in ports])
    result += row(
        "Direction", ["in" if directions[p] == "input" else "out" for p in ports]
    )
    types = ["vd" if output_references.get(p, "0") != "0" else "v" for p in ports]
    result += row("Default_Type", types)
    result += row("Allowed_Types", ["[" + t + "]" for t in types])
    for key, value in [
        ("Vector", "no"),
        ("Vector_Bounds", "-"),
        ("Null_Allowed", "no"),
    ]:
        result += row(key, [value] * count)
    names = [
        *parameters,
        "evas_inject",
        "evas_bad_state",
        "evas_inject_time",
        "evas_trace",
        "evas_trace_dc",
        "evas_inject_dc",
    ]
    columns = {
        "Parameter_Name": names,
        "Description": ['"specialized ' + n + '"' for n in parameters] + [
            '"test-only backtrack"',
            '"test-only leaked history"',
            '"earliest injected event time"',
            '"optional per-instance CSV trace path"',
            '"include DC candidate diagnostics"',
            '"test-only rejected DC candidate"',
        ],
        "Data_Type": ["real"] * len(parameters) + ["boolean", "boolean", "real", "string", "boolean", "boolean"],
        "Default_Value": [number(parameters[n]) for n in parameters] + ["FALSE", "FALSE", "0.0", '"-"', "FALSE", "FALSE"],
    }
    for key, value in [
        ("Limits", "-"),
        ("Vector", "no"),
        ("Vector_Bounds", "-"),
        ("Null_Allowed", "yes"),
    ]:
        columns[key] = [value] * len(names)
    # ngspice cmpp limits one table to20 items; multiple parameter tables
    # retain the original parameter order and specialization identity.
    for start in range(0, len(names), 16):
        result += "\nPARAMETER_TABLE:\n"
        result += "".join(row(key, values[start:start + 16]) for key, values in columns.items())
    return (
        result
        + '\nSTATIC_VAR_TABLE:\nStatic_Var_Name: diagnostics\nDescription: "diagnostics only"\nData_Type: pointer\n'
    )


def compile_model(
    sources, output, *, parameters=None, module=None, model_name=None, test_hooks=False
):
    """Write a new, self-contained source artifact after full subset admission.

    ``sources`` follows ``evas.compile_sources``'s explicit source/include map.
    Parameters are specialized at compilation. Existing output is never replaced.
    No kernel, C compiler or ngspice process is invoked by this operation.
    """
    if (
        not isinstance(sources, dict)
        or not sources
        or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in sources.items()
        )
    ):
        raise CompileError(
            "sources must be a nonempty path-to-text dictionary", code="input_error"
        )
    if not isinstance(test_hooks, bool):
        raise CompileError("test_hooks must be boolean", code="input_error")
    output = Path(output)
    models = parse_sources(sources)
    if module is None:
        if len(models) != 1:
            raise Unsupported("select one source module")
        module = next(iter(models))
    if module not in models:
        raise CompileError(
            "source module not found: " + str(module), code="input_error"
        )
    model = models[module]
    bound = bind_parameters(model, parameters or {}, "dut")
    for name in [*model.ports, *bound]:
        identifier(name)
    if any(n.startswith("evas_") for n in bound):
        raise Unsupported("source parameters conflict with diagnostic parameters")
    if not model.ports or any(
        model.directions.get(p) not in ("input", "output") for p in model.ports
    ):
        raise Unsupported("only explicit input and output voltage ports are supported")
    inputs = [p for p in model.ports if model.directions[p] == "input"]
    outputs = [p for p in model.ports if model.directions[p] == "output"]
    if not outputs or model.children or model.arrays:
        raise Unsupported("flat scalar voltage ports are required")
    program = compile_sources(
        sources,
        [Instance("dut", module, {p: p for p in model.ports}, parameters or {})],
        external_nodes=inputs,
    )
    ir = program.to_dict()
    if ir["schema_version"] != SCHEMA_VERSION:
        raise Unsupported("frontend IR schema does not match this package")
    if ir["step_bounds"]:
        raise Unsupported("bound_step is outside this backend slice")
    # IR33 emits initial_step as an event and keeps declaration seeds in
    # State.initial. The body runs once at DC initialization. It is not a
    # timer and does not consume a scheduled-event slot.
    initial_events = [
        event for event in ir["events"] if event["trigger"]["kind"] == "initial_step"
    ]
    ir["events"] = [
        event for event in ir["events"] if event["trigger"]["kind"] != "initial_step"
    ]
    events = ir["events"]
    crosses = [i for i, e in enumerate(events) if e["trigger"]["kind"] == "cross"]
    independent_clock = not crosses and not inputs
    if len(crosses) > 1 or len(events) > (64 if independent_clock else 8):
        raise Unsupported(
            "at most64 pure clock timers, or one rising cross and eight total mixed events supported"
        )
    cross_index = crosses[0] if crosses else -1
    trigger = events[cross_index]["trigger"] if crosses else None
    ttol, vtol = 1e-12, 1e-9
    emitter = Emitter(ir, inputs)
    emitter.prepare_locals(initial_events, events)
    if trigger:
        if trigger["direction"] != 1:
            raise Unsupported("only rising cross is supported")
        ttol, vtol = trigger["time_tolerance"], trigger["expression_tolerance"]
        if not (math.isfinite(ttol) and ttol > 0 and math.isfinite(vtol) and vtol > 0):
            raise Unsupported("finite positive event tolerances required")
        if not emitter.affine_guard(trigger["guard"]):
            raise Unsupported("cross must monitor an input voltage")

    def held_only(expr):
        if expr["op"] == "state":
            return True
        if expr["op"] == "real_boundary":
            return held_only(expr["value"])
        if expr["op"] == "affine":
            return all(ir["nodes"][t["node"]] == "0" for t in expr["terms"])
        if expr["op"] == "select":
            return all(held_only(expr[k]) for k in ("left", "right", "then_value", "else_value"))
        if expr["op"] == "real_binary" and expr.get("operation") not in ("add", "multiply"):
            return False
        return (
            expr["op"] in ("add", "multiply", "real_binary")
            and held_only(expr["left"])
            and held_only(expr["right"])
        )

    op_setup, op_updates = [], []
    for index, op in enumerate(ir["operators"]):
        if op["kind"] == "math" and op["function"] == "tanh":
            emitter.expr(op["input"])
            continue
        if op["kind"] != "transition" or not held_only(op["input"]):
            raise Unsupported("only event-held transition inputs supported")
        i = emitter.transition_slots[index]
        if not (
            op["delay"] >= 0
            and op["rise"] > 0
            and op["fall"] > 0
            and all(math.isfinite(op[k]) for k in ("delay", "rise", "fall"))
        ):
            raise Unsupported("transition requires finite delay >= 0 and rise/fall > 0")
        value = emitter.expr(op["input"])
        op_setup.append(f"cur->tr[{i}].settled = cur->tr[{i}].input = ({value}).v;")
        op_updates.append(
            f"transition_push(&cur->tr[{i}], TIME, ({value}).v, {number(op['delay'])});"
        )
        op_updates.append(
            f"transition_advance(&cur->tr[{i}], TIME, {number(op['rise'])}, {number(op['fall'])});"
        )
    # Fixed timer cursors belong to the accepted/candidate frame, like VA state.
    timer_find, timer_future, timer_nominal, future_nominal = [], [], [], []
    for i, e in enumerate(events):
        t = e["trigger"]
        if i == cross_index:
            continue
        if (
            t["kind"] != "timer"
            or not t["enabled"]
            or not (t["start"] >= 0 and t["period"] > 0 and t["time_tolerance"] > 0)
        ):
            raise Unsupported(
                "only enabled fixed nonnegative-start periodic timer supported"
            )
        if not all(math.isfinite(t[k]) for k in ("start", "period", "time_tolerance")):
            raise Unsupported("finite timer constants required")
        start, period, tol = map(number, (t["start"], t["period"], t["time_tolerance"]))
        timer_nominal.append(f"nominal[{i}] = {start} + prev->ticks[{i}]*{period};")
        future_nominal.append(f"nominal[{i}] = {start} + cur->ticks[{i}]*{period};")
        timer_find.append(f"deadline = nominal[{i}];")
        timer_find.append(
            f'if (2*minbreak > {tol}) fail("timer tolerance below host resolution");'
        )
        timer_find.append(
            f"if (TIME > deadline+{tol}) {{ request(targets[{i}], TIME, minbreak); refine=1; }}"
        )
        # The default timer point is at or after its deadline. A tolerance is
        # not permission to consume the already scheduled breakpoint early.
        timer_find.append(f"else if (TIME>=targets[{i}]) due[{i}]=1;")
        timer_future.append(
            f"deadline=targets[{i}]; if(deadline>TIME) request(deadline>TIME+minbreak?deadline:nextafter(TIME+minbreak,INFINITY),TIME,minbreak);"
        )
    if not independent_clock and any(e["trigger"]["kind"] == "timer" and e["trigger"]["start"] == 0 for e in events):
        raise Unsupported("zero periodic timers require the independent pure-clock slice")
    footprints = timer_plan(events, ir["nodes"], Unsupported) if independent_clock else None
    state_names = [s["name"] for s in ir["states"]]
    if len(set(state_names)) != len(state_names):
        raise Unsupported("unique scalar state names required")
    initial, checks = [], []
    for i, state in enumerate(ir["states"]):
        if not isinstance(state["initial"], (int, float)):
            raise Unsupported("constant initial state required")
        initial.append(
            "cur->values[" + str(i) + "] = " + number(state["initial"]) + ";"
        )
        if state["kind"] == "integer":
            value = "states[" + str(i) + "].v"
            checks.append(
                "if ("
                + value
                + " != trunc("
                + value
                + ") || "
                + value
                + " < -2147483648.0 || "
                + value
                + ' > 2147483647.0) fail("integer state range");'
            )
    def statements(items):
        body = []
        for stmt in items:
            if stmt["kind"] == "assign":
                si = stmt["state"]
                if not 0 <= si < len(state_names):
                    raise Unsupported("invalid assignment state")
                body.append(
                    "states[" + str(si) + "] = " + emitter.expr(stmt["rhs"]) + ";"
                )
                if ir["states"][si]["kind"] == "integer":
                    body.append(
                        f'if (states[{si}].v != trunc(states[{si}].v) || states[{si}].v < -2147483648.0 || states[{si}].v > 2147483647.0) fail("integer assignment range");'
                    )
            elif stmt["kind"] == "if":
                body.append("if (" + emitter.condition(stmt) + ") {\n"
                            + statements(stmt["then_body"]) + "\n} else {\n"
                            + statements(stmt["else_body"]) + "\n}")
            else:
                raise Unsupported(
                    "event body requires scalar assignments/conditionals; display/strobe are not supported by this backend"
                )
        return "\n".join(body)

    bodies = []
    for ei, event in enumerate(events):
        suffix = "cur->armed=0;" if ei == cross_index else f"++cur->ticks[{ei}];"
        bodies.append(
            f"if (due[{ei}]) {{\n"
            + statements(event["body"])
            + suffix
            + f" event_mask |= (UINT64_C(1) << {ei}); }}"
        )
    by_output = {}
    for c in ir["contributions"]:
        a, b = ir["nodes"][c["positive"]], ir["nodes"][c["negative"]]
        if a in ["0", *inputs] and b in outputs:
            port, sign, reference = b, -1, a
        elif b in ["0", *inputs] and a in outputs:
            port, sign, reference = a, 1, b
        else:
            raise Unsupported(
                "output voltage reference must be ground or an input port"
            )
        if port in by_output:
            raise Unsupported(
                "multiple contributions to one output are outside this slice"
            )
        by_output[port] = (c["rhs"], sign, reference)
    if set(by_output) != set(outputs):
        raise Unsupported("each output requires one voltage contribution")
    out_lines = []
    for i, port in enumerate(outputs):
        expr, sign, reference = by_output[port]
        out_lines.append(
            "Dual y"
            + str(i)
            + " = ad_mul(ad_const("
            + number(sign)
            + "), "
            + emitter.expr(expr)
            + ");"
        )
        out_lines.append("OUTPUT(" + port + ") = y" + str(i) + ".v;")
        out_lines.append(f'if (!isfinite(y{i}.v)) fail("nonfinite output voltage");')
        for j, inp in enumerate(inputs):
            out_lines.append(f'if (!isfinite(y{i}.d[{j}])) fail("nonfinite output derivative");')
            out_lines.append(
                "PARTIAL("
                + port
                + ", "
                + inp
                + ") = y"
                + str(i)
                + ".d["
                + str(j)
                + "];"
            )
    params = {name: float(value) for name, value in bound.items()}
    param_checks = [
        "if (!isfinite(PARAM("
        + name
        + ")) || fabs(PARAM("
        + name
        + ") - "
        + number(value)
        + ") > 8*DBL_EPSILON*fmax(fabs(PARAM("
        + name
        + ")), fabs("
        + number(value)
        + '))) fail("parameter specialization mismatch: '
        + name
        + '");'
        for name, value in params.items()
    ]
    replacements = {
        "NSTATE": str(len(state_names)),
        "NINPUT": str(len(inputs)),
        "TEST_HOOKS": "1" if test_hooks else "0",
        "TTOL": number(ttol),
        "VTOL": number(vtol),
        "INITIAL": "\n        ".join(initial),
        "INITIAL_STEP": "\n".join(statements(event["body"]) for event in initial_events),
        "PARAM_CHECKS": "\n        ".join(param_checks),
        "GUARD": emitter.expr(trigger["guard"]) if trigger else "ad_const(0.0)",
        "INPUTS": "\n    ".join(
            "inputs[" + str(i) + "] = ad_input(INPUT(" + p + "), " + str(i) + ");"
            for i, p in enumerate(inputs)
        ),
        "BODY": "\n".join(bodies),
        "ZERO_BODY": "\n".join(
            f"due[{i}]=1;" for i, e in enumerate(events)
            if e["trigger"]["kind"] == "timer" and e["trigger"]["start"] == 0
        ) + "\n" + "\n".join(bodies),
        "NEVENT": str(len(events)),
        "NOP": str(len(emitter.transition_slots)),
        "CROSS_INDEX": str(cross_index),
        "INDEPENDENT_CLOCK": "1" if independent_clock else "0",
        "OP_SETUP": "\n".join(op_setup),
        "OP_UPDATES": "\n".join(op_updates),
        "TIMER_FIND": "\n".join(timer_find),
        "TIMER_DEADLINES": "\n".join(timer_nominal) + "\nclock_targets(nominal,targets,minbreak);",
        "TIMER_FUTURE": "\n".join(future_nominal) + "\nclock_targets(nominal,targets,minbreak);\n" + "\n".join(timer_future),
        "INTEGER_CHECKS": "\n        ".join(checks),
        "OUTPUTS": "\n    ".join(out_lines),
        "TRACE_HEADER": "\n".join(
            f'fprintf(d->trace,",input{i}");' for i in range(len(inputs))) + "\n" + "\n".join(
            f'fprintf(d->trace,",output{i}' + "".join(f",partial{i}_{j}" for j in range(len(inputs))) + '");'
            for i in range(len(outputs))),
        "AD_HELPERS": (
            "static Dual ad_div(Dual a,Dual b) { Dual r;int j;"
            "if(!isfinite(a.v)||!isfinite(b.v)||b.v==0.0)fail(\"real division is not finite\");"
            "r.v=a.v/b.v;for(j=0;j<NI;++j)r.d[j]=(a.d[j]*b.v-a.v*b.d[j])/(b.v*b.v);return r; }\n"
            if emitter.needs_div else ""
        ),
        "LOCAL_DECL": ("Dual locals[" + str(emitter.nlocal) + "];" if emitter.nlocal else ""),
        "LOCALS": emitter.local_code,
        "TRACE_OUTPUTS": "\n".join(
            f'fprintf(d->trace,",%.17g",inputs[{i}].v);' for i in range(len(inputs))) + "\n" + "\n".join(
            f'fprintf(d->trace,",%.17g",y{i}.v);' + "".join(
                f'fprintf(d->trace,",%.17g",y{i}.d[{j}]);' for j in range(len(inputs)))
            for i in range(len(outputs))),
    }
    template = (
        importlib.resources.files(__package__)
        .joinpath("runtime.c.in")
        .read_text(encoding="utf-8")
    )
    text = template
    for key, value in replacements.items():
        text = text.replace("@" + key + "@", value)
    if re.search(r"@[A-Z_]+@", text):
        raise RuntimeError("unresolved code generation placeholder")
    source_hashes = {
        name: hashlib.sha256(value.encode()).hexdigest()
        for name, value in sources.items()
    }
    compiler_hash = hashlib.sha256(
        importlib.resources.files(__package__).joinpath("compiler.py").read_bytes()
    ).hexdigest()
    plan_hash = hashlib.sha256(importlib.resources.files(__package__).joinpath("timer_plan.py").read_bytes()).hexdigest()
    identity = hashlib.sha256(
        json.dumps(
            {
                "ir": ir,
                "sources": source_hashes,
                "test_hooks": test_hooks,
                "compiler": compiler_hash,
                "timer_plan": plan_hash,
                "template": hashlib.sha256(template.encode()).hexdigest(),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    if model_name is None:
        model_name = "evas_" + module.lower() + "_" + identity[:12]
    if not isinstance(model_name, str) or not re.fullmatch(
        r"[a-z][a-z0-9_]{0,62}", model_name
    ):
        raise CompileError(
            "model_name must be a lower-case SPICE identifier of at most63 characters",
            code="input_error",
        )
    metadata = {
        "artifact_version": 1,
        "backend_version": BACKEND_VERSION,
        "module": module,
        "model_name": model_name,
        "ports": list(model.ports),
        "directions": model.directions,
        "input_ports": inputs,
        "output_ports": outputs,
        "output_references": {p: by_output[p][2] for p in outputs},
        "instance_connections": [
            "%vd(" + p + " " + by_output[p][2] + ")"
            if p in by_output and by_output[p][2] != "0" else p
            for p in model.ports
        ],
        "parameters": params,
        "ir_schema_version": SCHEMA_VERSION,
        "test_hooks": test_hooks,
        "compiler_sha256": compiler_hash,
        "timer_plan_sha256": plan_hash,
        "state_names": state_names,
        "timer_batch_plan": footprints,
        "source_sha256": source_hashes,
        "compilation_id": identity,
        "scope": "up to64 independent pure-clock periodic timers with nonnegative starts and final DC seeds; mixed input/cross slice retains one rising cross and eight fixed events; scalar conditionals/select; event-held transition; continuous tanh with derivatives; scalar voltage ports with explicit references",
    }
    content = {
        "cfunc.mod": text,
        "ifspec.ifs": make_ifs(list(model.ports), model.directions, params, model_name, metadata["output_references"]),
        "ir.json": json.dumps(ir, indent=2, allow_nan=False) + "\n",
        "source-inputs.json": json.dumps(sources, indent=2, ensure_ascii=False) + "\n",
        "metadata.json": json.dumps(metadata, indent=2, allow_nan=False) + "\n",
        "model.inc": "* Specialized VA parameters are fixed in this model.\n.model "
        + model_name
        + " "
        + model_name
        + "(" + " ".join(n + "=" + number(v) for n, v in params.items()) + ")\n",
        "instance.cir": "* Port order from the VA declaration: "
        + " ".join(model.ports)
        + "\n"
        + "a_dut "
        + " ".join(metadata["instance_connections"])
        + " "
        + model_name
        + "\n",
    }
    hashes = {
        name: hashlib.sha256(value.encode()).hexdigest()
        for name, value in content.items()
    }
    content["manifest.json"] = (
        json.dumps({"artifact_version": 1, "files": hashes}, indent=2) + "\n"
    )
    # All language/backend validation precedes the only filesystem mutation.
    output.mkdir(parents=True, exist_ok=False)
    for name, value in content.items():
        (output / name).write_text(value, encoding="utf-8")
    return metadata
