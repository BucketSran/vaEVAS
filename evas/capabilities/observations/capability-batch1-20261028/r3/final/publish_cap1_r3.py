"""Publish capability batch 1 round 3: fast-forward the PR branch from the round 2 head eb26e5b1 to the round 3
catalog commit, publish the construction and publication archives, replace the body, mark the PR ready, and dispatch the
delivery-stage CI run (a synchronize run selects only the iteration, CI 40663200958).
Usage: python3 -I -B publish_cap1_r3.py phase2
"""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import time

D = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('cap1r3_task_publish', D / 'prepare_cap1_r3.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
load, git, sha, write = task.load, task.git, task.sha, task.write
BRANCH = 'refs/heads/codex/evas-capability-batch1'
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
WORKFLOW_FILE = 'numerical-assurance.yml'


def remote_refs(refs):
    out = git('ls-remote', 'origin', *refs).decode().splitlines()
    return {ref: oid for oid, ref in (line.split() for line in out)}


def gh(*args):
    return subprocess.check_output(['gh', *args], env=task.env())


def publication_archive(construction):
    if (D / 'publication-archive.json').exists():
        return load(D / 'publication-archive.json')
    dest = D / 'archive-final-files' / (task.PREFIX3 + '/final')
    dest.mkdir(parents=True)
    for name in ('final-candidate.json', 'derive-acceptance.json', 'generation-acceptance.json', 'rust-listing-change.json',
                 'precheck-acceptance.json', 'inventory-acceptance.json', 'prepare_cap1_r3.py', 'publish_cap1_r3.py'):
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
    commit = git('commit-tree', tree, '-p', construction['commit'], '-m', 'Archive the capability batch 1 round 3 receipts').decode().strip()
    idx.unlink()
    result = {'parent': construction['commit'], 'commit': commit, 'tree': tree, 'files': files, 'published': False}
    write(D / 'publication-archive.json', result)
    return result


def phase2():
    task.invariant()
    assert not (D / 'publication-start.json').exists(), 'Inspect actual refs before resuming any prior publication attempt'
    final, der = load(D / 'final-candidate.json'), load(D / 'derive-acceptance.json')
    pre, inv = load(D / 'precheck-acceptance.json'), load(D / 'inventory-acceptance.json')
    p1 = load(task.P1 / 'publication-phase1.json')
    r2pub = load(task.R2 / 'publication.json')
    assert r2pub['candidate'] == task.PREV
    construction = load(D / 'archive.json')
    assert all(row['returncode'] == 0 for row in der['checks'] + pre['checks'] + inv['checks'])
    assert pre['candidate'] == inv['candidate'] == final['commit']
    assert all(sha((task.S / p).read_bytes()) == digest for p, digest in der['files'].items())
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
    archive = publication_archive(construction)
    refs = [BRANCH, ARCHIVE_REF, 'refs/heads/main']
    before = remote_refs(refs)
    assert before == {BRANCH: task.PREV, ARCHIVE_REF: construction['parent'], 'refs/heads/main': task.BASE}, before
    git('merge-base', '--is-ancestor', task.PREV, final['commit'])
    git('merge-base', '--is-ancestor', construction['parent'], archive['commit'])
    values = {'{HEAD}': final['commit'], '{TREE}': final['tree'], '{BASE}': task.BASE,
              '{EVIDENCE}': 'https://github.com/BucketSran/vaEVAS/tree/' + archive['commit'] + '/' + task.PREFIX}
    body = (D / 'pr-body.md').read_text()
    for token, value in values.items():
        assert token in body, token
        body = body.replace(token, value)
    assert not re.search(r'\{[A-Z0-9_]+\}', body)
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
    number = str(p1['number'])
    subprocess.run(['gh', 'pr', 'edit', number, '--repo', task.REPO, '--body-file', str(D / 'pr-body.final.md')], env=task.env(), check=True, capture_output=True)
    subprocess.run(['gh', 'pr', 'ready', number, '--repo', task.REPO], env=task.env(), check=True, capture_output=True)
    view = json.loads(gh('pr', 'view', number, '--repo', task.REPO, '--json', 'state,isDraft,headRefOid,body,title,url'))
    assert view['state'] == 'OPEN' and not view['isDraft'] and view['headRefOid'] == final['commit']
    assert view['body'].replace('\r\n', '\n').strip() == body.strip()
    dispatched_at = datetime.now(timezone.utc)
    r = subprocess.run(['gh', 'workflow', 'run', WORKFLOW_FILE, '--repo', task.REPO, '--ref', BRANCH.removeprefix('refs/heads/'),
                        '-f', 'stage=delivery'], env=task.env(), capture_output=True)
    (D / 'dispatch.stdout').write_bytes(r.stdout)
    (D / 'dispatch.stderr').write_bytes(r.stderr)
    assert r.returncode == 0, 'workflow dispatch failed; read dispatch.stderr'
    run_id = None
    for _ in range(20):
        runs = json.loads(gh('run', 'list', '--repo', task.REPO, '--commit', final['commit'], '--workflow', WORKFLOW_FILE,
                             '--json', 'databaseId,headSha,event,createdAt'))
        runs = [x for x in runs if x['event'] == 'workflow_dispatch' and x['headSha'] == final['commit']]
        if len(runs) == 1:
            run_id = runs[0]['databaseId']
            break
        time.sleep(15)
    task.invariant()
    write(D / 'publication.json', {'published_at_utc': datetime.now(timezone.utc).isoformat(), 'PR': view['url'], 'title': view['title'],
          'candidate': final['commit'], 'tree': final['tree'], 'base': task.BASE, 'parent_published_head': task.PREV,
          'construction_archive': construction['commit'], 'publication_archive': archive['commit'], 'refs_before': before,
          'refs_after': after, 'body_sha256': sha(body.encode()), 'public': True, 'pushed': True, 'force_push': False, 'draft': False,
          'delivery_dispatch': {'at_utc': dispatched_at.isoformat(), 'run': run_id, 'stage': 'delivery'},
          'independent_review': 'pending (strict tier, priority Astra)', 'standards_check': 'pending',
          'necessary_CI': 'pending', 'merged': False, 'registration': 'required before merge (criteria and DUT change)',
          'old20_real_HEAD_index_config_preserved': True, 'scientific_qualification': False})
    print(json.dumps({'PR': view['url'], 'head': final['commit'], 'tree': final['tree'], 'archive': archive['commit'], 'ready': True,
                      'delivery_run': run_id}), flush=True)


if __name__ == '__main__':
    {'phase2': phase2}[sys.argv[1]]()
