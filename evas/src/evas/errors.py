"""Versioned diagnostic metadata; original exception text/kernel payload survive.

Only registered reasons have a category/capability. Unknown legacy failures do
not become claims about language validity, numerical accuracy or implementation bugs.
"""

# code -> category, owning stage, capability, actionable scope
RULES = {
    'compile_error': ('unknown', 'compile', None, None),
    'syntax_error': ('unknown', 'parse', 'LANG', 'Check the supported syntax and the source location.'),
    'unsupported_timer_dependency': ('unsupported', 'lowering', 'TIMER', 'Use constant or held-state timer start/period/enable and constant time_tol.'),
    'parameter_type': ('unsupported', 'binding', 'LANG', 'Use an exact signed 32-bit integer parameter value.'),
    'unsupported_integer_arithmetic': ('unsupported', 'binding', 'LANG', 'Use explicit real operands if real arithmetic is intended; typed integer division/overflow are not supported.'),
    'parameter_range': ('invalid_input', 'binding', 'LANG', 'Check the effective instance value and from/exclude constraints.'),
    'vector_declaration': ('invalid_input', 'binding', 'LANG', 'Use matching one-dimensional electrical and port ranges.'),
    'unsupported_vector': ('unsupported', 'binding', 'LANG', 'Use static scalar bit connections and instance-constant indices.'),
    'unsupported_initial_event': ('unsupported', 'parse', 'LANG', 'Use a constant initial_step body with an unqualified initialization leaf.'),
    'scs_input': ('invalid_input', 'netlist', 'LANG', 'Check the netlist statement and its constant values.'),
    'unsupported_scs': ('unsupported', 'netlist', 'LANG', 'Use the documented voltage-testbench subset.'),
    'input_error': ('invalid_input', 'input', None, 'Check the input fields and command arguments.'),
    'input_io': ('infrastructure', 'input', None, 'Check the referenced file path and access.'),
}

_KERNEL_CATEGORIES = {
    'invalid_request': 'invalid_input', 'invalid_ir': 'invalid_input',
    'invalid_inputs': 'invalid_input', 'invalid_config': 'invalid_input',
    'unsupported_ir_version': 'version', 'kernel_process': 'infrastructure',
    'invalid_response': 'protocol', 'kernel_timeout': 'resource',
    'residual_failure': 'numerical', 'waveform_accuracy': 'numerical',
    'event_resolution': 'numerical', 'nonlinear_convergence': 'numerical',
}
_KERNEL_CAPABILITIES = {'unsupported_timer': 'TIMER', 'unsupported_cross': 'CROSS',
                        'unsupported_implicit_dynamics': 'DYNAMICS'}


def diagnostic(code, message, *, token=None, instance=None):
    category, stage, capability, hint = RULES[code]
    result = dict(diagnostic_version=1, kind='compile_error', code=code,
                  category=category, stage=stage, capability=capability,
                  message=message, hint=hint)
    if token is not None:
        result['location'] = dict(source=token.source, line=token.line, column=token.column)
    if instance is not None:
        result['instance'] = instance
    return result


class CompileError(ValueError):
    def __init__(self, message, *, code='compile_error', token=None, instance=None):
        self.diagnostic = diagnostic(code, message, token=token, instance=instance)
        super().__init__(message)


class KernelError(RuntimeError):
    def __init__(self, detail: dict):
        self.detail = detail
        super().__init__(f"{detail['kind']}: {detail['message']}")

    @property
    def diagnostic(self):
        kind = self.detail['kind']
        return dict(self.detail, diagnostic_version=1, code=f'kernel.{kind}',
                    stage='kernel', category=_KERNEL_CATEGORIES.get(
                        kind, 'unsupported' if kind.startswith('unsupported_') else 'unknown'),
                    capability=_KERNEL_CAPABILITIES.get(kind))
