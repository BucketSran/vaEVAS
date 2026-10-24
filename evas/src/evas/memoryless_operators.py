"""Same occurrence and exact immutable input reuse, under the request's audit.

Interning describes IR; it never rewrites arithmetic or creates a value proof.
Shallow integer keys avoid recursive dataclass hashing and its repeated DAG walks.
RealLocal binding IDs, StateRef IDs, all boundaries and origins remain in keys.
"""
from dataclasses import fields, is_dataclass


class Registry:
    def __init__(self, owner):
        self.owner = owner
        self.identities = {}  # strong references, scoped to one Compilation
        self.shapes = {}
        self.operators = {}

    def identity(self, value):
        owner = self.owner
        pending = [(value, None)]
        while pending:
            item, prepared = pending.pop()
            owner.debit('memoryless_identity_visit', item=item)
            known = self.identities.get(id(item))
            if known is not None:
                continue
            if prepared is not None:
                # Reuse the immutable source fields read on entry. Repeating
                # fields()/getattr and cloning children on postorder exit did
                # no new identity work; keep these references on the frame.
                kind, children = prepared
            elif is_dataclass(item) and getattr(type(item), '__dataclass_params__').frozen:
                owner.debit('memoryless_identity_fields', len(fields(item)), item)
                children = tuple(getattr(item, f.name) for f in fields(item))
                kind = type(item)
            elif isinstance(item, tuple):
                owner.debit('memoryless_identity_elements', len(item), item)
                children, kind = item, tuple
            else:
                children, kind = (), type(item)
                if isinstance(item, str):
                    owner.debit('memoryless_identity_atom', 1+len(item), item)
                    atom = item
                elif isinstance(item, float):
                    owner.debit('memoryless_identity_atom', 2, item)
                    atom = item.hex()  # preserve -0.0
                elif item is None or type(item) in (int, bool):
                    owner.debit('memoryless_identity_atom', 1+(item.bit_length()//32 if item is not None else 0), item)
                    atom = item
                else:
                    raise TypeError('memoryless operator identity requires immutable IR')
            if children and prepared is None:
                owner.debit('memoryless_identity_prepared_frame', 2, item)
                owner.debit('memoryless_identity_schedule', 1+len(children), item)
                pending.append((item, (kind, children)))
                pending.extend((child, None) for child in children)
                continue
            owner.debit('memoryless_identity_key', 2+len(children), item)
            key = (kind, tuple(self.identities[id(child)][1] for child in children)) if is_dataclass(item) or isinstance(item, tuple) else (kind, atom)
            owner.debit('memoryless_identity_intern', 2+len(children), item)
            identity = self.shapes.get(key)
            if identity is None:
                identity = len(self.shapes)+1
                self.shapes[key] = identity
            self.identities[id(item)] = (item, identity)
        return self.identities[id(value)][1]

    def register(self, spec, operators):
        identity = self.identity(spec)
        self.owner.debit('memoryless_operator_lookup', item=spec)
        if identity in self.operators:
            return self.operators[identity]
        self.owner.debit('memoryless_operator_insert', 2, spec)
        index = len(operators)
        operators.append(spec)
        self.operators[identity] = index
        return index
