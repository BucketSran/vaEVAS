"""Publish the catalog part split as a new maintenance PR against main (new branch, evidence archive, PR body)."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
import re
import shutil
import subprocess

D = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('split_task', D / 'prepare_split.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
load, git, sha, write = task.load, task.git, task.sha, task.write
BRANCH = 'refs/heads/codex/catalog-part-split'
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
PUB_PREFIX = task.PREFIX + '/final'
REPO = 'BucketSran/vaEVAS'
TITLE = 'Split the catalog method and history indexes into fixed part files'


def publication_archive(construction):
    if (D / 'publication-archive.json').exists():
        return load(D / 'publication-archive.json')
    dest = D / 'archive-final-files' / PUB_PREFIX
    dest.mkdir(parents=True)
    for name in ('final-candidate.json', 'derive-acceptance.json', 'generation-acceptance.json', 'equivalence.json',
                 'bridge-consumer-remap.json', 'prepare_split.py', 'publish_split.py'):
        shutil.copyfile(D / name, dest / name)
    # The full candidate diff carries the whole regenerated catalog (over 200 MB); Git objects reproduce it, so only
    # its identity is archived. attempt-r1-* keeps the first try that hit the file size guard.
    patch = (D / 'candidate.patch').read_bytes()
    (dest / 'candidate-patch-identity.json').write_text(json.dumps({'base': task.BASE, 'head': load(D / 'final-candidate.json')['commit'],
        'command': 'git diff --binary <base> <head>', 'bytes': len(patch), 'sha256': sha(patch)}, indent=2) + '\n')
    idx = D / 'archive-final.index'
    assert not idx.exists()
    git('read-tree', construction['commit'], index=idx)
    files = []
    for p in sorted((D / 'archive-final-files').rglob('*')):
        if not p.is_file():
            continue
        raw = p.read_bytes()
        assert len(raw) < 50 * 1024 * 1024, (p, len(raw))
        path = p.relative_to(D / 'archive-final-files').as_posix()
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + path, index=idx)
        files.append({'path': path, 'sha256': sha(raw), 'bytes': len(raw)})
    tree = git('write-tree', index=idx).decode().strip()
    commit = git('commit-tree', tree, '-p', construction['commit'], '-m', 'Archive catalog part split receipts').decode().strip()
    idx.unlink()
    result = {'parent': construction['commit'], 'commit': commit, 'tree': tree, 'prefix': PUB_PREFIX, 'files': files, 'published': False}
    write(D / 'publication-archive.json', result)
    return result


def remote_refs(refs):
    return {ref: oid for oid, ref in (line.split() for line in git('ls-remote', 'origin', *refs).decode().splitlines())}


task.invariant()
assert not (D / 'publication-start.json').exists(), 'Inspect actual refs before resuming any prior publication attempt'
final, der = load(D / 'final-candidate.json'), load(D / 'derive-acceptance.json')
construction = load(D / 'archive.json')
assert all(row['returncode'] == 0 for row in der['checks'])
assert all(sha((task.S / p).read_bytes()) == digest for p, digest in der['files'].items())
assert task.git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
assert load(D / 'equivalence.json')['ok'] is True
for path, size in load(D / 'generation-acceptance.json')['data_file_sizes'].items():
    assert size < 52428800, (path, size)
archive = publication_archive(construction)
refs = [BRANCH, ARCHIVE_REF, 'refs/heads/main']
before = remote_refs(refs)
assert before == {ARCHIVE_REF: construction['parent'], 'refs/heads/main': task.BASE}, before
git('merge-base', '--is-ancestor', task.BASE, final['commit'])
git('merge-base', '--is-ancestor', construction['parent'], archive['commit'])
open_prs = json.loads(subprocess.check_output(['gh', 'pr', 'list', '--repo', REPO, '--head', BRANCH.removeprefix('refs/heads/'),
                                               '--state', 'all', '--json', 'number,url,state'], env=task.env()))
assert open_prs == [], open_prs
values = {'{HEAD}': final['commit'], '{TREE}': final['tree'], '{BASE}': task.BASE,
          '{EVIDENCE}': 'https://github.com/BucketSran/vaEVAS/tree/' + archive['commit'] + '/' + task.PREFIX}
body = (D / 'pr-body.md').read_text()
for token, value in values.items():
    assert token in body, token
    body = body.replace(token, value)
assert not re.search(r'\{[A-Z_]+\}', body)
(D / 'pr-body.final.md').write_text(body)
write(D / 'publication-start.json', {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'candidate': final['commit'],
      'tree': final['tree'], 'archive': archive['commit'], 'refs_before': before, 'force_push': False})
argv = ['/usr/bin/git', '--git-dir=' + str(task.task.GD), '--work-tree=' + str(task.task.W), 'push', '--atomic', '--porcelain',
        'origin', final['commit'] + ':' + BRANCH, archive['commit'] + ':' + ARCHIVE_REF]
with (D / 'push.stdout').open('xb') as out, (D / 'push.stderr').open('xb') as err:
    run = subprocess.run(argv, env=task.env(), stdout=out, stderr=err)
assert run.returncode == 0, 'Inspect retained push output and actual refs; do not blindly repeat'
after = remote_refs(refs)
assert after == {BRANCH: final['commit'], ARCHIVE_REF: archive['commit'], 'refs/heads/main': task.BASE}, after
created = subprocess.run(['gh', 'pr', 'create', '--repo', REPO, '--base', 'main', '--head', BRANCH.removeprefix('refs/heads/'),
                          '--title', TITLE, '--body-file', str(D / 'pr-body.final.md')], env=task.env(), capture_output=True, text=True)
(D / 'pr-create.stdout').write_text(created.stdout)
(D / 'pr-create.stderr').write_text(created.stderr)
assert created.returncode == 0, 'Inspect pr-create output and open PRs; do not blindly repeat'
url = created.stdout.strip().splitlines()[-1]
view = json.loads(subprocess.check_output(['gh', 'pr', 'view', url, '--repo', REPO, '--json', 'number,state,headRefOid,baseRefName,body,title,url'], env=task.env()))
assert view['state'] == 'OPEN' and view['headRefOid'] == final['commit'] and view['baseRefName'] == 'main', view['headRefOid']
assert view['body'].replace('\r\n', '\n').strip() == body.strip()
task.invariant()
write(D / 'publication.json', {'published_at_utc': datetime.now(timezone.utc).isoformat(), 'PR': view['url'], 'number': view['number'],
      'title': view['title'], 'candidate': final['commit'], 'tree': final['tree'], 'base': task.BASE,
      'construction_archive': construction['commit'], 'publication_archive': archive['commit'], 'refs_before': before, 'refs_after': after,
      'body_sha256': sha(body.encode()), 'public': True, 'pushed': True, 'force_push': False, 'independent_review': 'pending (priority)',
      'necessary_CI': 'pending', 'merged': False, 'merge_order': 'after PR #269; then rebase and regenerate',
      'local_checks': 'precheck and inventory run against this head in parallel with CI',
      'old20_real_HEAD_index_config_preserved': True, 'scientific_qualification': False})
print(json.dumps({'PR': view['url'], 'number': view['number'], 'head': final['commit'], 'tree': final['tree'], 'archive': archive['commit']}), flush=True)
