#!/usr/bin/env python3
"""Verify a real wheel in a fresh venv outside the checkout, without PYTHONPATH."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import shutil
import struct
import tempfile
import tarfile
import venv
import zipfile

# This program runs under the installed interpreter. Its answers are independent
# equations, rather than snapshots of a development-kernel response.
CHECK = r'''
import csv
import hashlib
from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys
from evas import Instance, compile_sources, solve, transient
import evas
from evas.results import run

root = Path.cwd()
package = Path(evas.__file__).resolve().parent
assert Path(sys.prefix) in package.parents, package
assert metadata.version('evas-rebuild')

def command(*args, success=True):
    result = subprocess.run(args, text=True, capture_output=True, timeout=30)
    assert result.returncode == (0 if success else 2), (args, result.stdout, result.stderr)
    return json.loads(result.stdout if success else result.stderr)

identity = command(sys.executable, '-m', 'evas', 'version', '--json', '--bundled-kernel')
selected = Path(identity['kernel']['path'])
assert package in selected.parents
assert identity['kernel']['sha256'] == hashlib.sha256(selected.read_bytes()).hexdigest()
assert identity['compatibility']['status'] == 'ir_matched'
assert identity['compatibility']['request_protocol_version'] is None
assert identity['kernel']['reported']['request_protocol_version'] is None
assert identity['package']['metadata_source'] == 'distribution'
cli = str(Path(sys.executable).parent / 'evas-rebuild')
source = '`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; analog begin V(y)<+2*V(u)+0.25; end endmodule'
(root/'m.va').write_text(source)
data = dict(models=['m.va'], instances=[dict(name='dut', module='m', connections=dict(u='u', y='y'))], driven=['u'], samples=[[-.5],[0],[.75]])
(root/'static.json').write_text(json.dumps(data))
program = compile_sources({'m.va':source}, [Instance(**data['instances'][0])])

def verify(response, answers):
    column = response['nodes'].index('y')
    assert len(response['solutions']) == len(answers)
    for row, answer in zip(response['solutions'], answers):
        assert abs(row['voltages'][column]-answer) <= 1e-9, row

answers = [-.75,.25,1.75]
verify(solve(program, ['u'], data['samples']), answers)
verify(solve(program, ['u'], data['samples'], kernel=selected), answers)
verify(command(cli, 'solve', 'static.json'), answers)
verify(command(sys.executable, '-m', 'evas', 'solve', 'static.json'), answers)

source = '`include "disciplines.vams"\nmodule m(y); output y; electrical y; analog begin V(y)<+idt(1,0.25); end endmodule'
(root/'integral.va').write_text(source)
dynamic = dict(models=['integral.va'], instances=[dict(name='dut', module='m', connections=dict(y='y'))], transient=dict(sources={},output_times=[0,.25,.5],stop=.5,max_step=.5), tolerances=dict(reltol=0,vabstol=1e-9))
(root/'transient.json').write_text(json.dumps(dynamic))
program = compile_sources({'integral.va':source}, [Instance(**dynamic['instances'][0])])
answers = [.25,.5,.75]
verify(transient(program, **dynamic['transient'], reltol=0, vabstol=1e-9), answers)
verify(command(cli, 'transient', 'transient.json'), answers)

for mode, expected in [('static',[-.75,.25,1.75]),('transient',[.25,.5,.75])]:
    command(sys.executable, '-m', 'evas.results', 'run', mode+'.json', '--out', mode+'-bundle')
    folder = root/(mode+'-bundle')
    marker = json.loads((folder/'manifest.json').read_text())
    assert marker['status'] == 'complete'
    response = json.loads((folder/'result.json').read_text())
    verify(response, expected)
    with (folder/'observations.csv').open(newline='') as stream:
        rows = list(csv.reader(stream))
    assert rows[0][0] == ('sample_index' if mode=='static' else 'time_s')
    assert rows[0][1:] == [node+'_V' for node in response['nodes']]
    assert len(rows) == 4
    col = response['nodes'].index('y')+1
    for row, answer in zip(rows[1:], expected):
        assert abs(float(row[col])-answer) <= 1e-9
    assert [float(row[0]) for row in rows[1:]] == ([0,1,2] if mode=='static' else [0,.25,.5])
    assert marker['columns'][col]['unit'] == 'V'
    for item in marker['files']:
        content = (folder/item['path']).read_bytes()
        assert len(content) == item['bytes']
        assert hashlib.sha256(content).hexdigest() == item['sha256']
run('static.json', out='api-bundle')
# Installed SCS API and CLI also resolve the bundled kernel.
(root/'tb.scs').write_text('ahdl_include "m.va"\nDUT (u y) m\nU (u 0) vsource dc=0.5\ntran tran stop=0.5 maxstep=0.25\n')
from evas.scs import simulate_scs
verify(simulate_scs('tb.scs'), [1.25,1.25,1.25])
verify(command(cli, 'simulate', 'tb.scs'), [1.25,1.25,1.25])
print(json.dumps(dict(package_path=str(package), identity=identity, checks='API/CLI/static/transient/CSV/SCS')))
'''

NEGATIVES = r'''
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import evas
import shutil
import os

folder = Path(evas.__file__).resolve().parent/'_bin'
kernel = folder/'evas-kernel'
receipt = folder/'kernel.json'
original = kernel.read_bytes()
original_mode = kernel.stat().st_mode
raw_receipt = receipt.read_bytes()

def cli(*args, success=False):
    result = subprocess.run([sys.executable, '-m', 'evas', *args], text=True, capture_output=True, timeout=30)
    assert result.returncode == (0 if success else 2), (args, result.stdout, result.stderr)
    return json.loads(result.stdout if success else result.stderr)

def rejection(message):
    error = cli('solve', 'static.json')
    assert message in error['message'], error
    return error

try:
    kernel.unlink()
    rejection('missing')
    cli('compile', 'static.json', success=True)
    cli('lint', 'static.json', success=True)
    cli('version', '--json', success=True)
    result = subprocess.run([sys.executable,'-m','evas.results','run','static.json','--out','failed-bundle'],text=True,capture_output=True)
    assert result.returncode == 2
    assert json.loads(Path('failed-bundle/manifest.json').read_text())['status'] == 'failed'
    kernel.write_bytes(original)
    kernel.chmod(original_mode)
    # A failed explicit selection cannot use the working bundle.
    error = cli('solve','static.json','--kernel',str(Path.cwd()/'absent-kernel'))
    assert 'absent-kernel' in error['message'], error
    kernel.write_bytes(original+b'corrupt')
    rejection('receipt')
    kernel.write_bytes(original)
    kernel.chmod(0o644)
    rejection('Permission denied')
    kernel.chmod(original_mode)
    data = json.loads(raw_receipt)
    data['platform']['arch'] = 'wrong-architecture'
    receipt.write_text(json.dumps(data))
    rejection('architecture')
    receipt.write_bytes(raw_receipt)
    # This executable is a protocol-boundary fixture, not an architecture test.
    data = json.loads(raw_receipt)
    report = dict(data['reported'], ir_schema_version=16)
    kernel.write_text('#!/bin/sh\nprintf \'%s\\n\' \''+json.dumps(report)+'\'\n')
    kernel.chmod(0o755)
    data['reported'] = report
    data['sha256'] = hashlib.sha256(kernel.read_bytes()).hexdigest()
    receipt.write_text(json.dumps(data))
    error = rejection('IR version')
    assert error['kind'] == 'unsupported_ir_version', error
    # Corrupt executable with matching receipt exercises the actual OS launch.
    kernel.write_bytes(b'not an executable\n')
    data['sha256'] = hashlib.sha256(kernel.read_bytes()).hexdigest()
    receipt.write_text(json.dumps(data))
    rejection('Exec format')
    kernel.write_bytes(original)
    kernel.chmod(original_mode)
    receipt.write_bytes(raw_receipt)
    # A copied/damaged installation may retain package files but lose metadata.
    metadata_folder = next(folder.parent.parent.glob('evas_rebuild-*.dist-info'))
    displaced = Path.cwd()/'displaced-distribution-metadata'
    shutil.move(str(metadata_folder), displaced)
    try:
        rejection('metadata')
    finally:
        shutil.move(str(displaced), metadata_folder)
    copied = Path.cwd()/'copied-package'
    shutil.copytree(folder.parent, copied/'evas')
    copied_environment = dict(os.environ, PYTHONPATH=str(copied))
    copied_environment.pop('PYTHONHOME', None)
    result = subprocess.run([sys.executable,'-S','-m','evas','solve','static.json'],
                            env=copied_environment,text=True,capture_output=True,timeout=30)
    assert result.returncode == 2 and 'Traceback' not in result.stderr, result.stderr
    assert 'metadata' in json.loads(result.stderr)['message'], result.stderr
finally:
    kernel.write_bytes(original)
    kernel.chmod(original_mode)
    receipt.write_bytes(raw_receipt)
print(json.dumps(dict(checks='missing/corrupt/nonexecutable/platform/IR/explicit-no-fallback/missing-metadata/copied-package')))
'''



def check_wheel_payload(wheel):
    """Check distribution tags against executable bytes, independently of setup.py."""
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_file = next(name for name in names if name.endswith('.dist-info/WHEEL'))
        metadata = archive.read(metadata_file).decode()
        assert 'Root-Is-Purelib: false' in metadata, metadata
        tags = [line.removeprefix('Tag: ') for line in metadata.splitlines() if line.startswith('Tag: ')]
        filename_tag = '-'.join(Path(wheel).stem.split('-')[-3:])
        assert tags == [filename_tag], 'WHEEL tags do not match filename tags'
        prefix = 'py3-none-'
        assert filename_tag.startswith(prefix) and filename_tag != prefix+'any', filename_tag
        tag = filename_tag[len(prefix):]
        executable_name = next(name for name in names if name.endswith('evas/_bin/evas-kernel'))
        receipt_name = next(name for name in names if name.endswith('evas/_bin/kernel.json'))
        binary = archive.read(executable_name)
        receipt = json.loads(archive.read(receipt_name))
        assert __import__('hashlib').sha256(binary).hexdigest() == receipt['sha256'], 'kernel receipt hash mismatch'
        if binary[:4] == b'\xcf\xfa\xed\xfe':
            # Apple mach-o/loader.h: thin mach_header_64 and LC_BUILD_VERSION.
            assert len(binary) >= 32, 'truncated Mach-O header'
            cpu = struct.unpack_from('<I', binary, 4)[0]
            architecture = {0x0100000c: 'arm64', 0x01000007: 'x86_64'}.get(cpu)
            assert architecture == 'arm64', 'only native arm64 macOS wheels are supported'
            count, size = struct.unpack_from('<II', binary, 16)
            assert size <= len(binary)-32, 'truncated Mach-O load commands'
            offset = 32
            minimum = None
            for _ in range(count):
                assert offset+8 <= 32+size, 'truncated Mach-O command'
                command, length = struct.unpack_from('<II', binary, offset)
                assert length >= 8 and offset+length <= 32+size, 'invalid Mach-O command size'
                if command == 0x32:
                    assert length >= 24, 'truncated LC_BUILD_VERSION'
                    system, version = struct.unpack_from('<II', binary, offset+8)
                    assert system == 1, 'kernel was not linked for macOS'
                    assert minimum is None, 'duplicate macOS build version'
                    minimum = (version >> 16, (version >> 8) & 255, version & 255)
                offset += length
            assert offset == 32+size and minimum is not None, 'missing Mach-O macOS build version'
            parts = tag.split('_')
            assert len(parts) == 4 and parts[0] == 'macosx' and parts[3] == architecture, 'wheel architecture does not match thin Mach-O kernel'
            declared = (int(parts[1]), int(parts[2]), 0)
            assert declared >= minimum, f'wheel minimum macOS {declared} is older than linked kernel {minimum}'
            assert receipt.get('macos_deployment_target') == f'{declared[0]}.{declared[1]}' and declared == minimum, 'receipt deployment target does not match linked macOS minimum/tag'
            expected_rust_target = 'aarch64-apple-darwin'
            actual_platform = dict(os='macos', arch='aarch64')
            facts = dict(architecture=architecture, minimum_macos=list(minimum))
        elif binary[:6] == b'\x7fELF\x02\x01':
            assert len(binary) >= 64, 'truncated ELF64 header'
            assert struct.unpack_from('<H', binary, 18)[0] == 62, 'kernel is not ELF x86_64'
            assert tag == 'linux_x86_64', 'Linux wheel tag does not match ELF x86_64 kernel'
            expected_rust_target = 'x86_64-unknown-linux-gnu'
            actual_platform = dict(os='linux', arch='x86_64')
            facts = dict(architecture='x86_64')
        else:
            raise AssertionError('unsupported executable architecture/format; universal binaries are not supported')
        assert receipt['platform'] == actual_platform, 'kernel receipt platform does not match executable'
        assert receipt['reported']['platform'] == actual_platform, 'reported kernel platform does not match executable'
        assert receipt.get('wheel_platform') == tag, 'kernel receipt wheel platform does not match tags'
        assert receipt.get('rust_target') == expected_rust_target, 'kernel Rust target does not match executable'
        assert not any('rust_core/target/' in name for name in names)
        return dict(filename_tag=filename_tag, executable=facts, receipt=receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--sdist', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    with tarfile.open(args.sdist) as archive:
        names = archive.getnames()
        for required in ('setup.py', 'pyproject.toml', 'rust_core/Cargo.toml',
                         'rust_core/Cargo.lock', 'rust_core/src/main.rs',
                         'rust_core/ir/Cargo.toml', 'rust_core/ir/src/lib.rs',
                         'rust_core/fuzz/seeds/static.json'):
            assert any(name.endswith('/'+required) for name in names), required
        assert not any('/target/' in name or '/_bin/' in name or '/build/' in name for name in names), names
    args.out.mkdir(parents=True, exist_ok=False)
    facts = check_wheel_payload(wheel)
    (args.out/'wheel-payload.json').write_text(json.dumps(facts, indent=2)+'\n')
    environment = {key:value for key,value in os.environ.items() if key not in ('PYTHONPATH','PYTHONHOME')}
    with tempfile.TemporaryDirectory(prefix='evas-installed-') as directory:
        directory = Path(directory)
        home = directory/'venv'
        venv.EnvBuilder(with_pip=True).create(home)
        python = home/'bin/python'
        def invoke(*command, cwd=directory):
            result = subprocess.run(command, cwd=cwd, env=environment, text=True, capture_output=True, timeout=300)
            with (args.out/'commands.log').open('a') as log:
                log.write(str(command[:2])+(' [installed check program]' if '-c' in command else ' '+str(command[2:]))+'\n'+result.stdout+result.stderr)
            if result.returncode:
                raise RuntimeError(f'{command} exited {result.returncode}; see {args.out}/commands.log')
            return result.stdout
        source_folder = directory/'source'
        source_folder.mkdir()
        with tarfile.open(args.sdist.resolve()) as archive:
            for member in archive.getmembers():
                destination = (source_folder/member.name).resolve()
                if not destination.is_relative_to(source_folder.resolve()) or not (member.isfile() or member.isdir()):
                    raise ValueError('sdist contains an unsafe path or nonregular input')
            archive.extractall(source_folder)
        source_manifest = next(source_folder.glob('*/rust_core/Cargo.toml'))
        # Compile test-only include_str inputs too. No numerical test is run.
        invoke('cargo', 'test', '--locked', '--no-run', '--manifest-path', str(source_manifest))
        invoke(str(python), '-m','pip','install','--no-index','--no-deps',str(wheel))
        for round_name in ('initial','reinstalled'):
            work = directory/round_name
            work.mkdir()
            output = invoke(str(python),'-c',CHECK,cwd=work)
            (args.out/(round_name+'.json')).write_text(output)
            for bundle in ('static-bundle', 'transient-bundle', 'api-bundle'):
                shutil.copytree(work/bundle, args.out/(round_name+'-'+bundle))
            if round_name == 'initial':
                output = invoke(str(python),'-c',NEGATIVES,cwd=work)
                (args.out/'negatives.json').write_text(output)
                shutil.copytree(work/'failed-bundle', args.out/'failed-bundle')
                package = Path(json.loads((args.out/'initial.json').read_text())['package_path'])
                invoke(str(python),'-m','pip','uninstall','-y','evas-rebuild')
                assert not package.exists(), package
                assert not (home/'bin/evas-rebuild').exists()
                invoke(str(python),'-c',"import importlib.util; from importlib import metadata; assert importlib.util.find_spec('evas') is None; assert not [d for d in metadata.distributions() if d.metadata['Name']=='evas-rebuild']")
                invoke(str(python),'-m','pip','install','--no-index','--no-deps',str(wheel))
    (args.out/'complete.json').write_text(json.dumps(dict(status='complete',wheel=wheel.name,sha256=__import__('hashlib').sha256(wheel.read_bytes()).hexdigest())))
    print(f'Installed wheel checks passed: {args.out}')


if __name__ == '__main__':
    main()
