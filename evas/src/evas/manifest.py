"""The shared manifest schema for the CLI and source-based IR migration."""
import json
import math

MANIFEST_FIELDS = {'models', 'instances', 'driven', 'samples', 'tolerances', 'transient'}
INSTANCE_FIELDS = {'name', 'module', 'connections', 'parameters'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON field {key!r}')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f'nonfinite JSON constant {value!r}')


def finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f'nonfinite JSON number {text!r}')
    return value


def parse_manifest(text):
    try:
        manifest = json.loads(text, object_pairs_hook=unique_object,
                              parse_constant=reject_constant, parse_float=finite_float)
    except RecursionError as exc:
        raise ValueError('manifest JSON nesting limit exceeded') from exc
    if not isinstance(manifest, dict):
        raise ValueError('manifest root must be a JSON object')
    unknown = set(manifest) - MANIFEST_FIELDS
    if unknown:
        raise ValueError(f'unknown manifest fields: {sorted(unknown)}')
    if 'models' not in manifest or 'instances' not in manifest:
        raise KeyError('models and instances are required')
    models = manifest['models']
    if not isinstance(models, list) or not models or any(not isinstance(p, str) or not p for p in models):
        raise ValueError('models must be a nonempty array of nonempty path strings')
    instances = manifest['instances']
    if not isinstance(instances, list) or not instances:
        raise ValueError('instances must be a nonempty array of objects')
    for index, instance in enumerate(instances):
        label = f'instances[{index}]'
        if not isinstance(instance, dict):
            raise ValueError(f'{label} must be an object')
        if set(instance) - INSTANCE_FIELDS or not {'name', 'module', 'connections'} <= instance.keys():
            raise ValueError(f'{label} requires name/module/connections and only optional parameters')
        for field in ('name', 'module'):
            if not isinstance(instance[field], str) or not instance[field]:
                raise ValueError(f'{label}.{field} must be a nonempty string')
        connections = instance['connections']
        if not isinstance(connections, dict) or any(not isinstance(v, str) or not v for v in connections.values()):
            raise ValueError(f'{label}.connections must map port names to nonempty net strings')
        if not isinstance(instance.get('parameters', {}), dict):
            raise ValueError(f'{label}.parameters must be an object')
    for field in ('tolerances', 'transient'):
        if field in manifest and not isinstance(manifest[field], dict):
            raise ValueError(f'{field} must be an object')
    for field in ('driven', 'samples'):
        if field in manifest and not isinstance(manifest[field], list):
            raise ValueError(f'{field} must be an array')
    return manifest
