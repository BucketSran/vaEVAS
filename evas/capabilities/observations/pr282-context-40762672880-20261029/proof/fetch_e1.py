"""Download the 14 artifacts of E1 (CI 40762672880 attempt 1) with read-only gh queries and check each one's bytes.

Every zip must equal the API digest (sha256) and size; members are extracted without links, absolute paths or '..',
each into a new directory, and listed with their own sha256. The run, attempt-1 jobs and artifact list are re-read
here (new files) and must match the earlier records. Nothing in an archive is executed.
Usage: python3 -B fetch_e1.py
"""
import stat
import subprocess
import zipfile
from pathlib import PurePosixPath

from common import *

OUT = F / 'e1'
ZIPS, ARTS = OUT / 'zips', OUT / 'artifacts'


def gh_json(path, name):
    target = OUT / 'api' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream, (OUT / 'api' / (name + '.stderr')).open('xb') as err:
        r = subprocess.run(['gh', 'api', '--paginate', path], env=clean_env(), stdout=stream, stderr=err)
    assert r.returncode == 0, (path, r.returncode)
    return load(target)


def main():
    started = utc()
    assert not ZIPS.exists() and not ARTS.exists()
    run = gh_json('repos/%s/actions/runs/%d' % (REPO, E1_RUN), 'run.json')
    assert (run['head_sha'], run['run_attempt'], run['event'], run['status']) == (HEAD282, 1, 'workflow_dispatch', 'completed'), run['head_sha']
    jobs = gh_json('repos/%s/actions/runs/%d/attempts/1/jobs?per_page=100' % (REPO, E1_RUN), 'jobs-attempt-1.json')
    artifacts = gh_json('repos/%s/actions/runs/%d/artifacts?per_page=100' % (REPO, E1_RUN), 'artifacts.json')
    rows = artifacts['artifacts']
    names = [a['name'] for a in rows]
    assert artifacts['total_count'] == len(rows) == 14 and len(set(names)) == 14, names
    expected = sorted(load(W / 'e1-registration-record.json')['issue_280_check']['artifacts'])
    assert sorted(names) == expected, (sorted(names), expected)
    ZIPS.mkdir(parents=True)
    ARTS.mkdir()
    manifest = []
    for a in sorted(rows, key=lambda x: x['name']):
        name = a['name']
        assert a['workflow_run']['id'] == E1_RUN and a['workflow_run']['head_sha'] == HEAD282 and not a['expired'], name
        path = ZIPS / (name + '.zip')
        with path.open('xb') as stream, (ZIPS / (name + '.stderr')).open('xb') as err:
            r = subprocess.run(['gh', 'api', 'repos/%s/actions/artifacts/%d/zip' % (REPO, a['id'])], env=clean_env(), stdout=stream, stderr=err)
        assert r.returncode == 0, (name, r.returncode)
        checksum, size = sha_file(path)
        assert 'sha256:' + checksum == a['digest'] and size == a['size_in_bytes'], (name, checksum, size)
        target = ARTS / name
        target.mkdir()
        members, seen = [], set()
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None, name
            for member in archive.infolist():
                rel = PurePosixPath(member.filename)
                mode = member.external_attr >> 16
                assert (not rel.is_absolute() and '..' not in rel.parts and '\\' not in member.filename
                        and member.filename not in seen), member.filename
                seen.add(member.filename)
                dest = target / member.filename
                assert dest.resolve().is_relative_to(target.resolve())
                if member.is_dir():
                    continue
                assert stat.S_IFMT(mode) in (0, stat.S_IFREG), (member.filename, oct(mode))
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as src, dest.open('xb') as dst:
                    for chunk in iter(lambda: src.read(1 << 20), b''):
                        dst.write(chunk)
                checksum_m, size_m = sha_file(dest)
                assert size_m == member.file_size
                members.append({'path': member.filename, 'bytes': size_m, 'sha256': checksum_m, 'archive_mode': mode})
        write_new(ZIPS / (name + '.members.json'), members)
        manifest.append({'name': name, 'id': a['id'], 'digest': a['digest'], 'bytes': size, 'created_at': a['created_at'],
                         'members': len(members), 'members_file': str(ZIPS / (name + '.members.json'))})
    regression_jobs = [j for j in jobs['jobs'] if j['name'].startswith('regression (')]
    write_new(OUT / 'download-manifest.json', {
        'started_at_utc': started, 'finished_at_utc': utc(), 'run': E1_RUN, 'run_url': E1_RUN_URL, 'event': run['event'],
        'head': run['head_sha'], 'run_attempt': run['run_attempt'], 'conclusion': run['conclusion'],
        'jobs': len(jobs['jobs']), 'job_attempts': sorted({j['run_attempt'] for j in jobs['jobs']}),
        'job_conclusions': {j['name']: j['conclusion'] for j in jobs['jobs']},
        'regression_jobs': [{'name': j['name'], 'id': j['id'], 'runner_name': j.get('runner_name'), 'labels': j.get('labels')} for j in regression_jobs],
        'artifacts': manifest, 'duplicate_names': [], 'method': 'gh api (GET) artifact zip; sha256 and size equal the API digest',
        'executed_archive_content': False})
    print(json.dumps({'artifacts': len(manifest), 'bytes': sum(m['bytes'] for m in manifest)}), flush=True)


if __name__ == '__main__':
    main()
