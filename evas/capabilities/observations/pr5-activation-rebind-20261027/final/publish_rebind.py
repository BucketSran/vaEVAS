"""Publish the frozen PR266 rebind and its evidence archive without force; update the original PR266."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
import shutil
import subprocess

D = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('rebind_task', D / 'prepare_rebind.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
load, git, sha, write = task.load, task.git, task.sha, task.write
BRANCH = 'refs/heads/codex/trusted-context-registration'
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
PUB_PREFIX = task.PREFIX + '/final'


def publication_archive(construction):
    if (D / 'publication-archive.json').exists():
        return load(D / 'publication-archive.json')
    dest = D / 'archive-final-files' / PUB_PREFIX
    dest.mkdir(parents=True)
    for name in ('final-candidate.json', 'precheck-acceptance.json', 'activation-workflow-acceptance.json',
                 'generation-acceptance.json', 'review-reuse-acceptance.json', 'maintenance-plan.json', 'candidate.patch'):
        shutil.copyfile(D / name, dest / name)
    for name in ('accept_review_reuse.py', 'publish_rebind.py'):
        shutil.copyfile(D / name, dest / name)
    idx = D / 'archive-final.index'
    assert not idx.exists()
    git('read-tree', construction['commit'], index=idx)
    files = []
    for p in sorted((D / 'archive-final-files').rglob('*')):
        if not p.is_file():
            continue
        raw = p.read_bytes()
        assert len(raw) < 104857600
        path = p.relative_to(D / 'archive-final-files').as_posix()
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + path, index=idx)
        files.append({'path': path, 'sha256': sha(raw), 'bytes': len(raw)})
    tree = git('write-tree', index=idx).decode().strip()
    commit = git('commit-tree', tree, '-p', construction['commit'], '-m', 'Archive consumer-migration activation rebind receipts').decode().strip()
    idx.unlink()
    result = {'parent': construction['commit'], 'commit': commit, 'tree': tree, 'prefix': PUB_PREFIX, 'files': files, 'published': False}
    write(D / 'publication-archive.json', result)
    return result


task.invariant()
assert not (D / 'publication-start.json').exists(), 'Inspect actual refs before resuming any prior publication attempt'
final = load(D / 'final-candidate.json')
pre = load(D / 'precheck-acceptance.json')
review = load(D / 'review-reuse-acceptance.json')
construction = load(D / 'archive.json')
assert review['candidate'] == final['commit'] and review['tree'] == final['tree'] and not review['remaining_actionable_findings']
assert all(row['returncode'] == 0 for row in pre['checks'])
assert all(sha((task.S / p).read_bytes()) == digest for p, digest in pre['files'].items())
archive = publication_archive(construction)
refs = [BRANCH, ARCHIVE_REF, 'refs/heads/main']
before = {ref: oid for oid, ref in (line.split() for line in git('ls-remote', 'origin', *refs).decode().splitlines())}
assert before == {BRANCH: task.OLD_PR, ARCHIVE_REF: construction['parent'], 'refs/heads/main': task.BASE}, before
git('merge-base', '--is-ancestor', task.OLD_PR, final['commit'])
git('merge-base', '--is-ancestor', task.BASE, final['commit'])
git('merge-base', '--is-ancestor', construction['parent'], archive['commit'])
gen = load(D / 'generation-acceptance.json')
body = '''Current paper, comparison and precision runners now call EVAS execution workers owned by `evas/validation/adapters/`, while their existing commands remain compatible. Production manifests bind the adapters. Historical checks use the frozen source contract: original execution dependencies stay in `STARTED`, and later analysis dependencies are bound separately in `CONTINUATION` to the exact old `STARTED` bytes. Old receipts are preserved.

The comparison discover command, literal CI inventory and path selection move together. The fixed collection has 31 Python entries and five Rust entries, containing 637 maintenance methods, 849 validation methods and the unchanged 3257 primary regression methods.

The migration changes the criteria identity, so its observation context had to be registered first. #267 installed the exact independently reviewed authority and bundle pointer on accepted main, and #268 appended that context to the trusted baseline. This head merges main into the reviewed `983b1ef6` without changing any reviewed source byte: all 22 source paths equal `983b1ef6`, and main had not changed them. Only the catalog is regenerated; it retains all {old} prior object versions of the merged main catalog.

Validation on this frozen head: the complete `scripts/ci_lint.py --plan` gate, 82 generated-view checks, and the catalog-history, CI-inventory and selector test modules pass. The unchanged production admission shell accepts the registered CI 40454789703 report against the merged baseline without requesting a registration bundle. All 31 collection receipts are reused by exact workflow, collector and owner-module hashes; no scientific test bodies ran locally. The fresh Astra review of `983b1ef6` (no Standards or Spec findings) and the exact-context review of #267 are reused; this delta adds only deterministic metadata and already reviewed main content. Necessary CI for this head is pending.

The registered observations have 3257 methods and 7737 conditions: 2617 passed, 423 failed, 214 errored and 3 expected failures. These results do not grant scientific qualification. The old 20 local scientific candidates are excluded.

Head: `{head}`. Tree: `{tree}`. Merged main base: `{base}`.

[Rebind construction and receipts]({evidence}) · [Batch5 acceptance plan](https://github.com/BucketSran/vaEVAS/blob/{head}/evas/docs/development/validation-restructure-plan.md#pr5按职责迁移当前维护资产每批保持执行与历史可读)
'''.format(old='{:,}'.format(gen['old_versions_retained']), head=final['commit'], tree=final['tree'], base=task.BASE,
           evidence='https://github.com/BucketSran/vaEVAS/tree/' + archive['commit'] + '/' + task.PREFIX)
(D / 'pr-body.md').write_text(body)
write(D / 'publication-start.json', {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'candidate': final['commit'],
      'tree': final['tree'], 'archive': archive['commit'], 'refs_before': before, 'same_original_PR': 266, 'force_push': False})
argv = ['/usr/bin/git', '--git-dir=' + str(task.task.GD), '--work-tree=' + str(task.task.W), 'push', '--atomic', '--porcelain',
        'origin', final['commit'] + ':' + BRANCH, archive['commit'] + ':' + ARCHIVE_REF]
with (D / 'push.stdout').open('xb') as out, (D / 'push.stderr').open('xb') as err:
    run = subprocess.run(argv, env=task.env(), stdout=out, stderr=err)
assert run.returncode == 0, 'Inspect retained push output and actual refs; do not blindly repeat'
after = {ref: oid for oid, ref in (line.split() for line in git('ls-remote', 'origin', *refs).decode().splitlines())}
assert after == {BRANCH: final['commit'], ARCHIVE_REF: archive['commit'], 'refs/heads/main': task.BASE}, after
task.invariant()
write(D / 'publication.json', {'published_at_utc': datetime.now(timezone.utc).isoformat(), 'PR': 266,
      'candidate': final['commit'], 'tree': final['tree'], 'base': task.BASE, 'construction_archive': construction['commit'],
      'publication_archive': archive['commit'], 'refs_after': after, 'public': True, 'pushed': True, 'force_push': False,
      'review_acceptance': str(D / 'review-reuse-acceptance.json'), 'necessary_CI': 'pending', 'merged': False,
      'old20_real_HEAD_index_config_preserved': True, 'scientific_qualification': False})
result = subprocess.run(['gh', 'pr', 'edit', '266', '--repo', 'BucketSran/vaEVAS', '--body-file', str(D / 'pr-body.md')],
                        env=task.env(), capture_output=True)
(D / 'pr-edit.stdout').write_bytes(result.stdout)
(D / 'pr-edit.stderr').write_bytes(result.stderr)
assert result.returncode == 0, result.stderr.decode()
print(json.dumps({'PR': 266, 'head': final['commit'], 'tree': final['tree'], 'archive': archive['commit'],
                  'published': True, 'force_push': False, 'CI': 'pending'}), flush=True)
