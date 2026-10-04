"""Bind an instance tree into flat, private identities for the shared kernel."""
from .errors import CompileError
from .ir import Affine
from .lowering import lower
from .parameters import bind_parameters
from .node_elaboration import scalarize_nodes
from .integer_constants import check_integer_expression

INSTANCE_BUDGET = 4096
DEPTH_BUDGET = 64


def bind_hierarchy(models, instances, instance_type):
    bindings, identities = [], set()

    def visit(instance, ancestry=(), port_nets=None):
        if instance.name in identities:
            raise CompileError(f'duplicate hierarchical instance identity {instance.name!r}')
        identities.add(instance.name)
        if len(identities) > INSTANCE_BUDGET or len(ancestry) >= DEPTH_BUDGET:
            raise CompileError('hierarchical instance count/depth budget exceeded')
        if instance.module not in models:
            raise CompileError(f'{instance.name}: unknown module {instance.module!r}')
        if instance.module in ancestry:
            raise CompileError(f'{instance.name}: recursive module hierarchy is unsupported')
        model = models[instance.module]
        parameters = bind_parameters(model, instance.parameters, instance.name)
        model, groups = scalarize_nodes(model, parameters)
        if set(instance.connections) != set(model.ports):
            raise CompileError(f'{instance.name}: connections must exactly match {model.ports}')
        if port_nets is None:
            if any(not isinstance(n,str) or not n or ':' in n for n in instance.connections.values()):
                raise CompileError("net names must be nonempty strings without ':' (reserved for internal nodes)")
            if ':' in instance.name:
                raise CompileError("instance names cannot contain ':'")
            port_nets = instance.connections
        nets = {n: port_nets.get(n, f'{instance.name}:{n}') for n in model.nodes}
        nets['0'] = '0'
        bindings.append((instance, model, nets))
        if not model.children:
            return

        def parameter(name):
            if name not in parameters:
                raise CompileError(f'{model.source}: unknown parent parameter {name!r}')
            return parameters[name]

        for child in model.children:
            if child.module not in models:
                raise CompileError(f'{model.source}:{child.token.line}: unknown child module {child.module!r}')
            target = models[child.module]
            requested = child.parameters
            if isinstance(requested,tuple):
                if len(requested) > len(target.parameters):
                    raise CompileError(f'{model.source}:{child.token.line}: too many ordered parameter overrides')
                requested = dict(zip(target.parameters, requested))
            overrides = {}
            for name, expr in requested.items():
                check_integer_expression(expr, model, parameters,
                                         check_literals=target.parameter_types.get(name) == 'integer')
                value = lower(expr, parameter, {}, model.source)
                if not isinstance(value,Affine) or value.terms:
                    raise CompileError(f'{model.source}:{expr.token.line}: child parameter override must be an instance constant')
                overrides[name] = value.constant
            target_parameters = bind_parameters(target, overrides, f'{instance.name}/{child.name}')
            _, target_groups = scalarize_nodes(target, target_parameters)
            ports = child.connections
            if isinstance(ports,tuple):
                if len(ports) != len(target.ports):
                    raise CompileError(f'{model.source}:{child.token.line}: child port count mismatch')
                ports = dict(zip(target.ports, ports))
            if set(ports) != set(target.ports) or not set(ports.values()) <= groups.keys():
                raise CompileError(f'{model.source}:{child.token.line}: child connections must name every port and declared electrical nets')
            expanded = {}
            for port, net in ports.items():
                if len(target_groups[port]) != len(groups[net]):
                    raise CompileError(f'{model.source}:{child.token.line}: child electrical vector width mismatch', code='vector_declaration', token=child.token)
                expanded.update(zip(target_groups[port], groups[net]))
            ports = expanded
            connections = {port: nets[node] for port,node in ports.items()}
            bound = instance_type(f'{instance.name}/{child.name}',child.module,connections,overrides)
            visit(bound, (*ancestry, instance.module), connections)

    for instance in instances:
        if not instance.name or not instance.module:
            raise CompileError(f'empty instance identity: {instance}')
        visit(instance)
    return bindings
