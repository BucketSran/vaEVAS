"""Publish the PR6 C0 authority: one atomic fast-forward push of the evidence archive and the C0 branch, then the PR.

The archive tip is a publication archive (final receipts) whose ancestors are the construction archive and the bundle
archive, so the bundle the authority points to is public in the same push. The branch reuses the merged PR267
auxiliary ref codex/pr4-context-authority (76d2152e is an ancestor of main 4d6ebc71). No force push.
"""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
import re
import shutil
import subprocess

D = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pr6_c0_task', D / 'prepare_c0.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
load, git, sha, write = c.load, c.git, c.sha, c.write
BRANCH = 'refs/heads/codex/pr4-context-authority'
PRIOR = '76d2152e478fee4c2108c4d33280df211da7b8a3'
PUB_PREFIX = c.PREFIX_C0 + '/final'
TITLE = 'Authorize the exact PR6 support-view observation context'
REPO = 'BucketSran/vaEVAS'


def gh(*args): return subprocess.check_output(['gh', *args], env=c.env())


def remote_refs(refs):
    return {ref: oid for oid, ref in (line.split() for line in git('ls-remote', 'origin', *refs).decode().splitlines())}


def publication_archive(construction):
    if (D / 'publication-archive.json').exists():
        return load(D / 'publication-archive.json')
    dest = D / 'archive-final-files' / PUB_PREFIX
    dest.mkdir(parents=True)
    (D / 'candidate.patch.identity.json').write_text(json.dumps({'base': c.BASE, 'head': load(D / 'final-candidate.json')['commit'],
        'command': 'git diff --binary <base> <head>', 'sha256': sha((D / 'candidate.patch').read_bytes())}, indent=2) + '\n')
    for name in ('final-candidate.json', 'derive-acceptance.json', 'generation-acceptance.json', 'candidate.patch.identity.json',
                 'prepare_c0.py', 'publish_c0.py'):
        shutil.copyfile(D / name, dest / name)
    idx = D / 'archive-final.index'
    assert not idx.exists()
    git('read-tree', construction['commit'], index=idx)
    files = []
    for p in sorted((D / 'archive-final-files').rglob('*')):
        if not p.is_file():
            continue
        raw = p.read_bytes()
        assert len(raw) < c.WARNING_BYTES, (p, len(raw))
        path = p.relative_to(D / 'archive-final-files').as_posix()
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + path, index=idx)
        files.append({'path': path, 'sha256': sha(raw), 'bytes': len(raw)})
    tree = git('write-tree', index=idx).decode().strip()
    commit = git('commit-tree', tree, '-p', construction['commit'], '-m', 'Archive PR6 C0 authority receipts').decode().strip()
    idx.unlink()
    result = {'parent': construction['commit'], 'commit': commit, 'tree': tree, 'prefix': PUB_PREFIX, 'files': files, 'published': False}
    write(D / 'publication-archive.json', result)
    return result


c.invariant()
assert not (D / 'publication-start.json').exists(), 'Inspect actual refs before resuming any prior publication attempt'
final, der, cap = load(D / 'final-candidate.json'), load(D / 'derive-acceptance.json'), load(D / 'capture.json')
construction, bundle = load(D / 'archive.json'), load(D / 'bundle-archive.json')
assert all(row['returncode'] == 0 for row in der['checks'])
assert all(sha((c.S / p).read_bytes()) == digest for p, digest in der['files'].items())
assert git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
assert git('rev-parse', final['commit'] + '^').decode().strip() == cap['commit']
assert git('rev-parse', cap['commit'] + '^').decode().strip() == c.BASE
pointer = json.loads((c.S / c.POINTER_PATH).read_text())
assert pointer == bundle['pointer'] and pointer['commit'] == bundle['commit']
archive = publication_archive(construction)
for anc in (c.ARCHIVE_TIP, bundle['commit'], construction['commit']):
    git('merge-base', '--is-ancestor', anc, archive['commit'])
git('merge-base', '--is-ancestor', PRIOR, final['commit'])
git('merge-base', '--is-ancestor', c.BASE, final['commit'])
refs = [BRANCH, c.ARCHIVE_REF, 'refs/heads/main']
before = remote_refs(refs)
assert before == {BRANCH: PRIOR, c.ARCHIVE_REF: c.ARCHIVE_TIP, 'refs/heads/main': c.BASE}, before
open_prs = json.loads(gh('pr', 'list', '--repo', REPO, '--head', BRANCH.removeprefix('refs/heads/'), '--state', 'open', '--json', 'number,url,headRefOid'))
assert open_prs == [], open_prs
values = {'{HEAD}': final['commit'], '{TREE}': final['tree'], '{BASE}': c.BASE, '{BUNDLE_SHORT}': bundle['commit'][:8],
          '{EVIDENCE}': 'https://github.com/BucketSran/vaEVAS/tree/' + archive['commit'] + '/' + c.PREFIX_C0,
          '{BUNDLE_URL}': 'https://github.com/BucketSran/vaEVAS/tree/' + bundle['commit'] + '/' + c.PREFIX_BUNDLE}
body = (D / 'pr-body.md').read_text()
for token, value in values.items():
    assert token in body, token
    body = body.replace(token, value)
assert not re.search(r'\{[A-Z_]+\}', body)
(D / 'pr-body.final.md').write_text(body)
write(D / 'publication-start.json', {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'candidate': final['commit'],
      'tree': final['tree'], 'archive': archive['commit'], 'refs_before': before, 'force_push': False})
argv = ['/usr/bin/git', '--git-dir=' + str(c.task.GD), '--work-tree=' + str(c.task.W), 'push', '--atomic', '--porcelain',
        'origin', final['commit'] + ':' + BRANCH, archive['commit'] + ':' + c.ARCHIVE_REF]
with (D / 'push.stdout').open('xb') as out, (D / 'push.stderr').open('xb') as err:
    run = subprocess.run(argv, env=c.env(), stdout=out, stderr=err)
assert run.returncode == 0, 'Inspect retained push output and actual refs; do not blindly repeat'
after = remote_refs(refs)
assert after == {BRANCH: final['commit'], c.ARCHIVE_REF: archive['commit'], 'refs/heads/main': c.BASE}, after
with (D / 'pr-create.stdout').open('xb') as out, (D / 'pr-create.stderr').open('xb') as err:
    made = subprocess.run(['gh', 'pr', 'create', '--repo', REPO, '--base', 'main', '--head', BRANCH.removeprefix('refs/heads/'),
                           '--title', TITLE, '--body-file', str(D / 'pr-body.final.md')], env=c.env(), stdout=out, stderr=err)
assert made.returncode == 0, 'Read pr-create.stderr'
url = (D / 'pr-create.stdout').read_text().strip().splitlines()[-1]
assert re.fullmatch(r'https://github.com/BucketSran/vaEVAS/pull/\d+', url), url
view = json.loads(gh('pr', 'view', url, '--repo', REPO, '--json', 'state,headRefOid,baseRefName,body,title,number'))
assert view['state'] == 'OPEN' and view['headRefOid'] == final['commit'] and view['baseRefName'] == 'main'
assert view['body'].replace('\r\n', '\n').strip() == body.strip()
c.invariant()
write(D / 'publication.json', {'published_at_utc': datetime.now(timezone.utc).isoformat(), 'PR': url, 'number': view['number'], 'title': TITLE,
      'candidate': final['commit'], 'tree': final['tree'], 'base': c.BASE, 'bundle_archive': bundle['commit'],
      'construction_archive': construction['commit'], 'publication_archive': archive['commit'], 'refs_before': before, 'refs_after': after,
      'body_sha256': sha(body.encode()), 'public': True, 'pushed': True, 'force_push': False, 'independent_review': 'pending',
      'necessary_CI': 'pending', 'merged': False, 'local_checks': 'precheck and inventory run against this head in parallel with CI',
      'old20_real_HEAD_index_config_preserved': True, 'scientific_qualification': False})
print(json.dumps({'PR': url, 'head': final['commit'], 'tree': final['tree'], 'archive': archive['commit'], 'published': True,
                  'action_required': 'link and watch this PR in T3'}), flush=True)
