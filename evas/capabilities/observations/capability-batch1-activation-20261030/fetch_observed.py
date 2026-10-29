"""Download the asset observation (OBSERVED) for the activation: main 0ad80828's push CI catalog-inventory.

Brief (2026-10-30): use the catalog-inventory observation of main's push CI on 0ad80828 (run 40944364517); if that run did
not succeed, use the most recent successful run whose tree equals main's, and say which. Read-only gh: run, jobs and
artifact list; the catalog-inventory zip must equal the listed size and digest; safe extraction; assets-before.json must
name source_tree b4a07295's tree b0fa321b... (source_commit 0ad80828 for the push run) and no dirty paths.
Writes W/observed/ (new): api records, the zip, the extracted files and fetch-receipt.json. Exit 3 when not accepted.
Usage: python3 -B fetch_observed.py [RUN_ID]
"""
from pathlib import PurePosixPath
import stat
import zipfile

from common_act import *

OUT = W / 'observed'


def main():
    run_id = int(sys.argv[1]) if len(sys.argv) > 1 else PUSH_RUN
    assert not OUT.exists()
    (OUT / 'api').mkdir(parents=True)
    run = gh_json('repos/%s/actions/runs/%d' % (REPO, run_id), OUT / 'api/run.json')
    jobs = gh_json('repos/%s/actions/runs/%d/attempts/%d/jobs?per_page=100' % (REPO, run_id, run['run_attempt']), OUT / 'api/jobs.json')
    conclusions = {j['name']: j['conclusion'] for j in jobs['jobs']}
    artifacts = gh_json('repos/%s/actions/runs/%d/artifacts?per_page=100' % (REPO, run_id), OUT / 'api/artifacts.json')
    receipt = {'run': run_id, 'event': run['event'], 'head_sha': run['head_sha'], 'run_attempt': run['run_attempt'], 'status': run['status'],
               'conclusion': run['conclusion'], 'jobs': conclusions,
               'counts': {c: sum(1 for v in conclusions.values() if v == c) for c in sorted(set(map(str, conclusions.values())))},
               'started_at_utc': utc()}
    rows = [a for a in artifacts['artifacts'] if a['name'] == 'catalog-inventory' and not a['expired']]
    ok = (run['status'] == 'completed' and run['conclusion'] == 'success' and conclusions.get('catalog-inventory') == 'success'
          and all(c in ('success', 'skipped') for c in conclusions.values()) and len(rows) == 1)
    if not ok:
        write_new(OUT / 'fetch-receipt.json', dict(receipt, accepted=False, reason='run not successful or no unique catalog-inventory artifact'))
        print(json.dumps({'accepted': False, 'run': run_id, 'conclusion': run['conclusion']}), flush=True)
        return 3
    a = rows[0]
    zpath = OUT / 'catalog-inventory.zip'
    with zpath.open('xb') as stream, (OUT / 'catalog-inventory.stderr').open('xb') as err:
        r = subprocess.run(['gh', 'api', 'repos/%s/actions/artifacts/%d/zip' % (REPO, a['id'])], env=clean_env(), stdout=stream, stderr=err)
    assert r.returncode == 0
    checksum, size = sha_file(zpath)
    target = OUT / 'catalog-inventory'
    target.mkdir()
    members = []
    with zipfile.ZipFile(zpath) as archive:
        assert archive.testzip() is None
        for member in archive.infolist():
            rel = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            assert not rel.is_absolute() and '..' not in rel.parts and '\\' not in member.filename, member.filename
            if member.is_dir():
                continue
            assert stat.S_IFMT(mode) in (0, stat.S_IFREG), member.filename
            dest = target / member.filename
            assert dest.resolve().is_relative_to(target.resolve())
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, dest.open('xb') as dst:
                for chunk in iter(lambda: src.read(1 << 20), b''):
                    dst.write(chunk)
            members.append({'path': member.filename, 'bytes': member.file_size, 'sha256': sha_file(dest)[0]})
    before = target / 'assets-before.json'
    observed = load(before)
    summary = load(target / 'summary.json') if (target / 'summary.json').exists() else {}
    checks = {'zip_digest_equals_listing': 'sha256:' + checksum == a['digest'], 'zip_bytes_equal_listing': size == a['size_in_bytes'],
              'artifact_from_run_head': a['workflow_run']['head_sha'] == run['head_sha'],
              'source_tree_is_main_tree': observed['source_tree'] == BASE_TREE, 'no_dirty_paths': observed['dirty_paths'] == [],
              'source_commit': observed['source_commit'], 'push_run_on_main': run['event'] != 'push' or observed['source_commit'] == BASE,
              'ci_inventory_success_and_reconciled': bool(summary.get('success')) and bool(summary.get('reconciled'))}
    accepted = all(v for k, v in checks.items() if k != 'source_commit')
    write_new(OUT / 'fetch-receipt.json', dict(receipt, accepted=accepted, artifact={'id': a['id'], 'digest': a['digest'], 'bytes': a['size_in_bytes'],
              'created_at': a['created_at']}, downloaded={'bytes': size, 'sha256': checksum}, members=members,
              assets_before=str(before), assets_before_sha256=sha_file(before)[0], assets=len(observed['assets']), checks=checks,
              summary={k: summary.get(k) for k in ('success', 'reconciled', 'construction_complete', 'entry_count', 'denominators')},
              choice='main push CI on 0ad80828 (the brief\'s first choice)' if run_id == PUSH_RUN else 'fallback run with the main tree',
              finished_at_utc=utc()))
    print(json.dumps({'accepted': accepted, 'run': run_id, 'assets': len(observed['assets']), 'checks': checks}), flush=True)
    return 0 if accepted else 3


if __name__ == '__main__':
    raise SystemExit(main())
