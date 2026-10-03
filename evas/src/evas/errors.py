"""Public compilation diagnostics shared by syntax, binding and IR guards."""


class CompileError(ValueError):
    pass


class KernelError(RuntimeError):
    def __init__(self, detail: dict):
        self.detail = detail
        super().__init__(f"{detail['kind']}: {detail['message']}")
