"""Publish the PR271 successor and its evidence archive (fast-forward only) and update the PR body."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
import re
import shutil
import subprocess

D = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fix_r2_task', D / 'prepare_fix_r2.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
load, git, sha, write = task.load, task.git, task.sha, task.write
BRANCH = 'refs/heads/codex/runner-host-comparison'
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
PUB_PREFIX = task.PREFIX + '/final'
TITLE = 'Compare runs across GitHub runner image updates by their full observations'
PR_URL = 'https://github.com/BucketSran/vaEVAS/pull/271'
PRIOR = load(task.R1 / 'publication.json')


def ran(name):
    counts = re.findall(r'^Ran (\d+) tests? in ', (D / name).read_text(), re.M)
    assert len(counts) == 1, name
    return int(counts[0])


def publication_archive(construction):
    if (D / 'publication-archive.json').exists():
        return load(D / 'publication-archive.json')
    dest = D / 'archive-final-files' / PUB_PREFIX
    dest.mkdir(parents=True)
    for name in ('final-candidate.json', 'precheck-acceptance.json', 'generation-acceptance.json', 'maintenance-plan.json',
                 'real-data-checks.json', 'inventory-acceptance.json', 'candidate.patch', 'prepare_fix_r2.py', 'publish_fix_r2.py',
                 'increment-receipt.json'):
        shutil.copyfile(D / name, dest / name)
    shutil.copyfile(task.R1 / 'review-r1-acceptance.json', dest / 'review-r1-acceptance.json')
    shutil.copyfile(task.B / 'night-coordination/runner-host-comparison-astra-r1-20261027/review-report.json', dest / 'review-r1-report.json')
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
    commit = git('commit-tree', tree, '-p', construction['commit'], '-m', 'Archive runner-host comparison fix successor receipts').decode().strip()
    idx.unlink()
    result = {'parent': construction['commit'], 'commit': commit, 'tree': tree, 'prefix': PUB_PREFIX, 'files': files, 'published': False}
    write(D / 'publication-archive.json', result)
    return result


def remote_refs(refs):
    return {ref: oid for oid, ref in (line.split() for line in git('ls-remote', 'origin', *refs).decode().splitlines())}


task.invariant()
assert not (D / 'publication-start.json').exists(), 'Inspect actual refs before resuming any prior publication attempt'
final, pre = load(D / 'final-candidate.json'), load(D / 'precheck-acceptance.json')
inventory, construction = load(D / 'inventory-acceptance.json'), load(D / 'archive.json')
assert inventory['candidate'] == final['commit'] and inventory['summary']['success'] and inventory['summary']['reconciled']
assert all(row['returncode'] == 0 for row in pre['checks'])
assert all(sha((task.S / p).read_bytes()) == digest for p, digest in pre['files'].items())
archive = publication_archive(construction)
refs = [BRANCH, ARCHIVE_REF, 'refs/heads/main']
before = remote_refs(refs)
assert before == {BRANCH: task.PARENT, ARCHIVE_REF: construction['parent'], 'refs/heads/main': task.BASE}, before
assert construction['parent'] == PRIOR['publication_archive'] and PRIOR['candidate'] == task.PARENT
git('merge-base', '--is-ancestor', task.PARENT, final['commit'])
git('merge-base', '--is-ancestor', task.BASE, final['commit'])
git('merge-base', '--is-ancestor', construction['parent'], archive['commit'])
open_prs = json.loads(subprocess.check_output(['gh', 'pr', 'list', '--repo', 'BucketSran/vaEVAS', '--head', BRANCH.removeprefix('refs/heads/'),
                                               '--state', 'open', '--json', 'number,url,headRefOid'], env=task.env()))
assert open_prs == [{'number': 271, 'url': PR_URL, 'headRefOid': task.PARENT}], open_prs
tests = sum(ran(name) for name in ['affected-' + n.removesuffix('.py') + '.txt' for n in task.AFFECTED_TESTS])
values = {'{HEAD}': final['commit'], '{TREE}': final['tree'], '{BASE}': task.BASE,
          '{EVIDENCE}': 'https://github.com/BucketSran/vaEVAS/tree/' + archive['commit'] + '/' + task.PREFIX,
          '{CAPABILITY_TESTS}': str(ran('capability-tests.txt')), '{SCRIPT_TESTS}': str(tests),
          '{SCRIPT_MODULES}': str(len(task.AFFECTED_TESTS))}
body = (task.R1 / 'pr-body.md').read_text()
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
subprocess.run(['gh', 'pr', 'edit', '271', '--repo', 'BucketSran/vaEVAS', '--body-file', str(D / 'pr-body.final.md')],
               env=task.env(), check=True, capture_output=True)
view = json.loads(subprocess.check_output(['gh', 'pr', 'view', '271', '--repo', 'BucketSran/vaEVAS', '--json', 'state,headRefOid,body'], env=task.env()))
assert view['state'] == 'OPEN' and view['headRefOid'] == final['commit'] and view['body'].replace('\r\n', '\n').strip() == body.strip(), view['headRefOid']
url = PR_URL
task.invariant()
write(D / 'publication.json', {'published_at_utc': datetime.now(timezone.utc).isoformat(), 'PR': url, 'title': TITLE,
      'candidate': final['commit'], 'tree': final['tree'], 'base': task.BASE, 'construction_archive': construction['commit'],
      'publication_archive': archive['commit'], 'parent_candidate': task.PARENT, 'refs_before': before, 'refs_after': after, 'body_sha256': sha(body.encode()),
      'public': True, 'pushed': True, 'force_push': False, 'independent_review': 'incremental tcodex r2 pending; r1 (codex) passed on dc8866d3', 'necessary_CI': 'pending',
      'merged': False, 'one_time_red_admission_exception': 'authorized for this PR only after the five recorded conditions',
      'old20_real_HEAD_index_config_preserved': True, 'scientific_qualification': False})
print(json.dumps({'PR': url, 'head': final['commit'], 'tree': final['tree'], 'archive': archive['commit'], 'published': True}), flush=True)
