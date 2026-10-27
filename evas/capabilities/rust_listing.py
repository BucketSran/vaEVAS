"""Whole owned-target listing reconciliation over the existing Registry graph.

This compares observations, never native test execution or semantic qualification.
Historical and current binary bytes are separate facts; cross-run reproducibility
is not assumed. Only published immutable Git source receipts authorize require.
"""
import hashlib
import json
import re

TARGET = ('package', 'version', 'target_kind', 'name')
IDENTITY = ('src_path', 'src_sha256', 'manifest', 'source_tree_sha256', 'lockfile_sha256', 'cargo_profile')
# Same runner-host rule as scripts/regression_gate.py: a runner image update may change
# only the kernel release inside platform.platform(); glibc and architecture stay exact.
HOST_PLATFORM = r'Linux-([0-9][0-9A-Za-z.+_~-]*?)-{machine}-with-(glibc[0-9]+\.[0-9]+)'

def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def sha(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('invalid Rust receipt SHA256')

def target(binary):
    value = {key: binary[key] for key in TARGET}
    if (any(not isinstance(value[key], str) or not value[key] for key in ('package','version','name'))
            or value['target_kind'] not in (['bin'], ['lib'], ['test'])):
        raise ValueError('unknown Rust target identity')
    return canonical(value)

def checked(receipt):
    if (type(receipt.get('schema_version')) is not int or receipt.get('schema_version') != 1 or receipt.get('observation_kind') != 'rust-test-binary-listing'
            or receipt.get('complete') is not True or receipt.get('errors') != []
            or receipt.get('listing_only') is not True
            or receipt.get('test_body_execution') != 'not_observed_by_this_helper'):
        raise ValueError('incomplete or unknown whole Rust listing')
    source = receipt['source']
    sha(source['sha256'])
    if hashlib.sha256(json.dumps(source['files'], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() != source['sha256']:
        raise ValueError('Rust source manifest identity changed')
    files = {row['path']: row for row in source['files']}
    if len(files) != len(source['files']):
        raise ValueError('duplicate Rust source path')
    for row in files.values():sha(row['sha256'])
    sha(receipt['observer']['sha256'])
    if receipt['build']['exit'] != 0:raise ValueError('failed Rust build')
    sha(receipt['build']['sha256'])
    # Receipts observed before CI fixed RUSTUP_TOOLCHAIN named the stable channel on the command line.
    for name, argvs in [('rustc',(['rustc','-vV'],['rustc','+stable','-vV'])), ('cargo',(['cargo','--version'],['cargo','+stable','--version']))]:
        tool = receipt['toolchain'][name]
        if tool['argv'] not in argvs or tool['returncode'] != 0 or not tool['stdout'].strip():
            raise ValueError('missing actual Rust toolchain identity')
        if hashlib.sha256(tool['stdout'].encode()).hexdigest() != tool['stdout_sha256']:
            raise ValueError('Rust tool identity output hash mismatch')
    binaries, paths, rows = {}, set(), {}
    if not isinstance(receipt['binaries'], list) or not receipt['binaries']:
        raise ValueError('missing complete owned Rust targets')
    for index, binary in enumerate(receipt['binaries']):
        key = target(binary)
        if key in binaries or binary['binary_path'] in paths:
            raise ValueError('duplicate Rust target/executable')
        paths.add(binary['binary_path']);binaries[key]=(binary, [])
        sha(binary['binary_sha256'])
        if binary['listing_complete'] is not True or binary['source_tree_sha256'] != source['sha256']:
            raise ValueError('incomplete or inconsistent binary source identity')
        if (binary['src_sha256'] != files[binary['src_path']]['sha256']
                or binary['manifest']['sha256'] != files[binary['manifest']['path']]['sha256']
                or binary['lockfile_sha256'] != files['evas/rust_core/Cargo.lock']['sha256']):
            raise ValueError('binary Rust input identity mismatch')
        if binary['observer_sha256'] != receipt['observer']['sha256'] or binary['source_commit'] != source['commit']:
            raise ValueError('binary observation context mismatch')
        if (binary['cargo_profile'].get('test') is not True
                or type(binary['tests_discovered']) is not int
                or type(binary['ignored_tests_discovered']) is not int):
            raise ValueError('not an actual Cargo test profile')
        for label, flags in [('all',['--list']),('ignored',['--list','--ignored'])]:
            command = binary['listing'][label]
            if command['returncode'] != 0 or command['argv'] != [binary['binary_path'],*flags]:
                raise ValueError('failed or unknown actual harness invocation')
            sha(command['stdout_sha256']);sha(command['stderr_sha256'])
    for row in receipt['tests']:
        index=row['binary_index']
        if type(index) is not int or not 0 <= index < len(receipt['binaries']):
            raise ValueError('invalid Rust binary index')
        binary=receipt['binaries'][index]
        if (row['kind'] not in ('test','benchmark') or type(row['ignored']) is not bool
                or not isinstance(row['local_id'],str) or not row['local_id']):
            raise ValueError('invalid Rust test row')
        identity='rust:'+binary['package']+'@'+binary['version']+'/'+binary['target_kind'][0]+'/'+binary['name']+'::'+row['local_id']
        if row['id'] != identity or identity in rows:
            raise ValueError('duplicate or inconsistent qualified Rust ID')
        rows[identity]=row
        binaries[target(binary)][1].append({k:row[k] for k in ('id','local_id','kind','ignored')})
    tests=sum(row['kind']=='test' for row in rows.values())
    ignored=sum(row['kind']=='test' and row['ignored'] for row in rows.values())
    benchmarks=sum(row['kind']=='benchmark' for row in rows.values())
    if not tests or any(type(receipt[k]) is not int or receipt[k] != v for k,v in
            [('tests_discovered',tests),('ignored_tests_discovered',ignored),('benchmarks_discovered',benchmarks)]):
        raise ValueError('zero or inconsistent whole Rust denominator')
    for binary, local in binaries.values():
        if (binary['tests_discovered'] != sum(r['kind']=='test' for r in local)
                or binary['ignored_tests_discovered'] != sum(r['kind']=='test' and r['ignored'] for r in local)):
            raise ValueError('inconsistent per-binary denominator')
        local.sort(key=lambda row:row['id'])
    return binaries

def profile_identity(receipt):
    return {'source':receipt['source']['sha256'],
            'toolchain':{name:receipt['toolchain'][name]['stdout'] for name in ('cargo','rustc')},
            'environment':{key:receipt['environment'][key] for key in ('platform','machine','variables')}}

def host_neutral(identity):
    """Return the profile identity without the kernel release, or None if not in the fixed form."""
    environment=identity['environment']
    machine,platform=environment.get('machine'),environment.get('platform')
    if not isinstance(machine,str) or not re.fullmatch('[A-Za-z0-9_]+',machine) or not isinstance(platform,str):
        return None
    match=re.fullmatch(HOST_PLATFORM.format(machine=re.escape(machine)),platform)
    if not match:
        return None
    return dict(identity,environment=dict(environment,platform='Linux-'+machine+'-with-'+match.group(2)))

def reconcile(catalog, receipt, profile):
    """Require exact coverage of one explicitly registered profile's targets."""
    try:
        actual=checked(receipt)
        entries=[entry for entry in catalog.current('entrypoint')
                 if entry.get('collector')=='binary-listing' and entry.get('namespace')=='rust-tests'
                 and entry.get('listing_profile')==profile]
        if not isinstance(profile,str) or not profile or not entries:
            raise ValueError('unknown Rust listing profile')
        registered={}
        for entry in entries:
            if entry.get('status') != 'active':raise ValueError('inactive Rust entrypoint')
            if set(entry['rust_target']) != set(TARGET):raise ValueError('unknown registered Rust target fields')
            key=target(entry['rust_target'])
            if key in registered:raise ValueError('duplicate registered Rust target')
            registered[key]=entry
        if set(registered) != set(actual):raise ValueError('missing/extra owned Rust targets versus Registry')
        facts=[];hosts=[]
        for key,entry in registered.items():
            source=catalog.bound(entry['listing_source'],'source')
            if source.get('status') != 'active' or source.get('availability') != 'published-archive' or source.get('locator',{}).get('kind') != 'git-object':
                raise ValueError('Rust require needs a published immutable original receipt')
            expected_receipt=json.loads(catalog.registry.read_source(source))
            expected=checked(expected_receipt)
            if set(expected) != set(actual):raise ValueError('original receipt owned-target set differs')
            expected_identity,actual_identity=profile_identity(expected_receipt),profile_identity(receipt)
            if expected_identity != actual_identity:
                neutral=host_neutral(expected_identity),host_neutral(actual_identity)
                if None in neutral or neutral[0] != neutral[1]:
                    raise ValueError('Rust source/toolchain/profile drift')
                hosts.append(dict(expected_platform=expected_identity['environment']['platform'],
                                  actual_platform=actual_identity['environment']['platform']))
            old,old_rows=expected[key]
            new,new_rows=actual[key]
            if any(old[field] != new[field] for field in IDENTITY) or old_rows != new_rows:
                raise ValueError('Rust target/source/profile/IDs/ignored drift')
            facts.append(dict(entrypoint_id=entry['id'],rust_target=entry['rust_target'],
                listing_source=entry['listing_source'],expected_binary_sha256=old['binary_sha256'],
                actual_binary_sha256=new['binary_sha256'],binary_sha256_equal=old['binary_sha256']==new['binary_sha256'],
                expected_source_commit=expected_receipt['source']['commit'],actual_source_commit=receipt['source']['commit'],
                expected_observer_sha256=expected_receipt['observer']['sha256'],actual_observer_sha256=receipt['observer']['sha256']))
        host={} if not hosts else {'host_platform_difference':hosts[0]}
        if any(item != hosts[0] for item in hosts):
            raise ValueError('inconsistent Rust runner-host difference')
        return dict(reconciled=True,profile=profile,listing_only=True,**host,
                    test_body_execution='not_observed_by_this_helper',
                    binary_sha256_policy='separate-observations-no-cross-run-reproducibility-assumption',
                    tests_discovered=receipt['tests_discovered'],ignored_tests_discovered=receipt['ignored_tests_discovered'],
                    benchmarks_discovered=receipt['benchmarks_discovered'],binaries=facts)
    except (KeyError,TypeError,IndexError,AttributeError) as error:
        raise ValueError('incomplete or unknown Rust listing structure: '+str(error)) from error
