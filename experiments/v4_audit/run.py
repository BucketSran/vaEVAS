"""Prepare immutable family dossiers and run tool-disabled GLM static reviews.

Raw prompts/results stay under ignored runs/. No simulator or original asset writes.
An accepted report has validated structure/identity/citations, not verified findings.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / 'benchmark/reference/v4/release/benchmarkv4-r53'
PROVENANCE = ROOT / 'benchmark/reference/v4/provenance/dut-base-v3-exact-five-hash-bound-v2'
FORMS = {'dut', 'testbench', 'bugfix'}
CATEGORIES = {'spec-modeling', 'data-modeling', 'extension-integration',
              'diagnosis-repair', 'testing-characterization'}
CANCELLED = threading.Event()


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix=path.name+'.', suffix='.tmp', delete=False) as stream:
        temp = Path(stream.name)
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def bundle(path):
    return {str(p.relative_to(path)): digest(p.read_bytes())
            for p in sorted(path.rglob('*.va'))}


def represent(path, contents, full_bases):
    """Lossless repeated-line references for long metadata/decks; VA is always full."""
    lines = contents.splitlines()
    full = '\n'.join(f'{n}: {line}' for n, line in enumerate(lines, 1))
    if len(contents) < 10000 or Path(path).suffix not in {'.json', '.scs'}:
        return full, []
    candidates = []
    for base_path, base_lines in full_bases.items():
        if Path(base_path).suffix == Path(path).suffix and min(len(lines),len(base_lines))/max(len(lines),len(base_lines),1) > .3:
            matcher = difflib.SequenceMatcher(None, base_lines, lines, autojunk=False)
            candidates.append((matcher.quick_ratio(), base_path, matcher))
    best = (full, [])
    for _, base_path, matcher in sorted(candidates, key=lambda x:x[0], reverse=True)[:3]:
        parts, refs, reconstructed = [], [], []
        for tag, a, b, c, d in matcher.get_opcodes():
            if tag == 'equal' and d-c >= 8:
                parts.append(f'原行 {c+1}–{d} 等同于先前文件 {base_path} 的行 {a+1}–{b}，逐行相同。')
                refs.append(dict(line_start=c+1,line_end=d,source_path=base_path,source_line_start=a+1,source_line_end=b))
                reconstructed.extend(full_bases[base_path][a:b])
            else:
                parts.extend(f'{n}: {lines[n-1]}' for n in range(c+1,d+1))
                reconstructed.extend(lines[c:d])
        assert reconstructed == lines, 'Lossless input representation failed'
        encoded = '\n'.join(parts)
        if len(encoded) < len(best[0]):
            best = (encoded, refs)
    return best if len(best[0]) < len(full)*.8 else (full, [])


def json_fields(contents):
    """Return original top-level JSON field line spans and decoded values."""
    decoder = json.JSONDecoder()
    def skip(pos):
        while pos < len(contents) and contents[pos].isspace():
            pos += 1
        return pos
    pos = skip(0)
    if contents[pos] != '{':
        return []
    pos = skip(pos+1)
    result = []
    while contents[pos] != '}':
        key_start = pos
        key, pos = decoder.raw_decode(contents, pos)
        pos = skip(pos)
        assert contents[pos] == ':'
        value, end = decoder.raw_decode(contents, skip(pos+1))
        result.append((key, value, contents[:key_start].count('\n')+1,
                       contents[:end].count('\n')+1))
        pos = skip(end)
        if contents[pos] == ',':
            pos = skip(pos+1)
    return result


def represent_json(path, contents, semantic_bases):
    """Reuse equal JSON values, including when object-key order differs."""
    lines = contents.splitlines()
    fields = json_fields(contents)
    # Replacing a whole line must not hide a neighboring field on that line.
    if any(left[3] >= right[2] for left, right in zip(fields, fields[1:])):
        return '\n'.join(f'{n}: {line}' for n, line in enumerate(lines, 1)), []
    refs, parts, cursor = [], [], 1
    for key, value, start, end in fields:
        canonical = json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=False)
        identity = digest(canonical.encode())
        prior = semantic_bases.get(identity)
        if prior and len(canonical) > 500:
            parts.extend(f'{n}: {lines[n-1]}' for n in range(cursor,start))
            ref = dict(line_start=start,line_end=end,json_key=key,source_path=prior['path'],
                       source_line_start=prior['start'],source_line_end=prior['end'],
                       source_json_key=prior['key'],canonical_value_sha256=identity)
            refs.append(ref)
            parts.append(f'原行 {start}–{end} 的 JSON 字段 {key} 值与先前文件 {prior["path"]} 字段 {prior["key"]} 完全相等（对象键顺序可不同），原值见其行 {prior["start"]}–{prior["end"]}。')
            cursor = end+1
        else:
            semantic_bases.setdefault(identity, dict(path=path,key=key,start=start,end=end))
    parts.extend(f'{n}: {lines[n-1]}' for n in range(cursor,len(lines)+1))
    return '\n'.join(parts), refs


def prepare(run):
    if (run / 'manifest.json').exists():
        raise ValueError('Input run already exists; use run/status to resume frozen inputs')
    run.mkdir(parents=True, exist_ok=True)
    prompt_template = (Path(__file__).with_name('audit_prompt.md')).read_text()
    (run / 'audit_prompt.md').write_text(prompt_template)
    groups = defaultdict(list)
    for record in sorted((RELEASE / 'tasks').glob('*/task_record.json')):
        groups[json.loads(record.read_text())['family_id']].append(record.parent)
    assert len(groups) == 400
    manifest = dict(created_utc=now(), base_commit=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_snapshot='7b5616dc52195ec275ec6d21c71d7763613702cd',
        release='r53', family_count=400, package_count=1200,
        review_kind='static-model-draft', model_requested='glm-5.3',
        prompt_template_sha256=digest(prompt_template.encode()),
        runner_sha256=digest(Path(__file__).read_bytes()), families=[])
    for family_id, dirs in sorted(groups.items()):
        records = [json.loads((p / 'task_record.json').read_text()) for p in dirs]
        assert len(records) == 3 and {r['form'] for r in records} == FORMS
        by_form = {r['form']: p for p, r in zip(dirs, records)}
        files = sorted({p for d in dirs for p in d.rglob('*') if p.is_file()})
        provenance = PROVENANCE / records[0]['canonical_dut_source_slug'] / 'evaluator'
        files += [provenance / name for name in ['derivation_manifest.json',
                  'mutation_catalog.json', 'certification.json', 'task_record.json']
                  if (provenance / name).exists()]
        by_sha = defaultdict(list)
        file_index = {}
        for p in files:
            data = p.read_bytes()
            contents = data.decode('utf-8')
            rel = str(p.relative_to(ROOT))
            sha = digest(data)
            file_index[rel] = dict(sha256=sha, bytes=len(data), lines=len(contents.splitlines()))
            by_sha[sha].append((rel, contents))
        starter = bundle(by_form['bugfix'] / 'public/buggy_bundle')
        matches = [p.name for p in sorted((by_form['testbench'] / 'evaluator/mutation_bundles').glob('neg_*'))
                   if p.is_dir() and bundle(p) == starter and starter]
        seed = json.loads((provenance / 'derivation_manifest.json').read_text()).get('mutation_partition', {}).get('bugfix_seed', []) if (provenance / 'derivation_manifest.json').exists() else []
        static = dict(family_id=family_id, forms={r['form']: r['task_id'] for r in records},
                      bugfix_starter_sha256=starter, starter_matches_tb_mutant_bundles=matches,
                      provenance_claimed_bugfix_seed=seed,
                      provenance_seed_matches_actual=bool(set(seed) & set(matches)))
        required = [str((d / 'public/instruction.md').relative_to(ROOT)) for d in dirs]
        required += [str(p.relative_to(ROOT)) for p in (by_form['dut'] / 'evaluator/solution').rglob('*.va')]
        required += [str(p.relative_to(ROOT)) for p in (by_form['bugfix'] / 'public/buggy_bundle').rglob('*.va')]
        required += [str((by_form['testbench'] / 'evaluator/trusted_replay_suite.json').relative_to(ROOT))]
        assert all(p in file_index for p in required)
        sections = [prompt_template, '\n## 静态身份与字节比较\n', json.dumps(static, ensure_ascii=False, indent=2)]
        sections += ['\n以下文件必须明确列入 materials_reviewed，其他实读文件也可列入：\n'+'\n'.join(required)]
        full_bases = {}
        semantic_bases = {}
        for sha, aliases in by_sha.items():
            if Path(aliases[0][0]).suffix == '.json':
                encoded, semantic_refs = represent_json(aliases[0][0], aliases[0][1], semantic_bases)
                refs = []
            else:
                encoded, refs = represent(aliases[0][0], aliases[0][1], full_bases)
                semantic_refs = []
            if not refs:
                full_bases[aliases[0][0]] = aliases[0][1].splitlines()
            for alias, _ in aliases:
                file_index[alias]['line_references'] = refs
                file_index[alias]['semantic_references'] = semantic_refs
            sections += ['\n## 文件内容 SHA256 ' + sha,
                         '同字节路径：\n' + '\n'.join(p for p, _ in aliases),
                         '```text\n' + encoded + '\n```']
        work = run / 'families' / family_id
        work.mkdir(parents=True)
        text = '\n'.join(sections) + '\n'
        (work / 'prompt.md').write_text(text)
        save(work / 'input.json', dict(static=static, files=file_index, required_reviewed=required,
                                     prompt_sha256=digest(text.encode()), unique_files=len(by_sha)))
        manifest['families'].append(dict(family_id=family_id, forms=static['forms'],
                                        prompt_bytes=len(text.encode()), prompt_sha256=digest(text.encode())))
    save(run / 'manifest.json', manifest)
    summary(run)
    print(json.dumps({'families':400,'packages':1200,'prompt_bytes_total':sum(f['prompt_bytes'] for f in manifest['families']),
                      'prompt_bytes_max':max(f['prompt_bytes'] for f in manifest['families'])}))


def validate(report, inputs):
    if report.get('family_id') != inputs['static']['family_id']:
        raise ValueError('Wrong family identity')
    if not isinstance(report.get('circuit_summary'), str) or len(report['circuit_summary']) < 10:
        raise ValueError('Missing circuit explanation')
    if report.get('architecture_status') not in {'supported_in_assets','unverified'} or len(report.get('architecture_basis','')) < 10:
        raise ValueError('Missing architecture justification')
    forms = report.get('forms', [])
    if len(forms) != 3 or {f.get('form') for f in forms} != FORMS:
        raise ValueError('Missing/duplicate forms')
    reviewed = set(report.get('materials_reviewed', []))
    if not set(inputs['required_reviewed']) <= reviewed or not reviewed <= inputs['files'].keys():
        raise ValueError('Missing required reviewed materials or fabricated paths')
    findings = report.get('shared_findings', [])
    ids = {f['id'] for f in findings}
    if len(ids) != len(findings):
        raise ValueError('Duplicate finding IDs')
    for finding in findings:
        if finding.get('severity') not in {'high', 'medium', 'low'} or not finding.get('claim') or not finding.get('impact') or not finding.get('evidence'):
            raise ValueError('Incomplete finding')
        for ref in finding['evidence']:
            info = inputs['files'].get(ref.get('path'))
            start, end = ref.get('line_start'), ref.get('line_end')
            if not info or not isinstance(start, int) or not isinstance(end, int) or not 1 <= start <= end <= info['lines']:
                raise ValueError('Invalid evidence citation: ' + str(ref))
    for form in forms:
        if form.get('task_id') != inputs['static']['forms'][form['form']]:
            raise ValueError('Wrong task identity')
        if form.get('disposition') not in {'prefer', 'revise', 'defer', 'exclude'}:
            raise ValueError('Unknown disposition')
        for field in ['engineering_value', 'contract_assessment', 'reference_assessment', 'checker_assessment', 'rewrite_allowed_value', 'next_action']:
            if not isinstance(form.get(field), str) or len(form[field]) < 3:
                raise ValueError('Empty form analysis: ' + field)
        if not set(form.get('finding_ids', [])) <= ids:
            raise ValueError('Unknown finding ID')
    if not isinstance(report.get('uncertainties'), list) or not isinstance(report.get('migration_ideas'), list):
        raise ValueError('Missing uncertainty/migration fields')
    for idea in report['migration_ideas']:
        if idea.get('category') not in CATEGORIES or not idea.get('proposal') or not idea.get('rationale'):
            raise ValueError('Invalid migration idea')


def normalize_paths(report, inputs):
    """Repair only unambiguous path spelling, preserving a separate correction log."""
    corrections = []
    paths = set(inputs['files'])
    def canonical(path):
        normalized = os.path.normpath(path)
        if normalized in paths:
            replacement = normalized
        else:
            match = re.search(r'(.*/tasks/[^/]+/)', normalized)
            options = [p for p in paths if match and p.startswith(match[1]) and Path(p).name == Path(normalized).name]
            if len(options) != 1:
                return path
            replacement = options[0]
        if replacement != path:
            corrections.append(dict(original=path, corrected=replacement,
                                    method='normalize-or-unique-filename-within-the-same-task'))
        return replacement
    report['materials_reviewed'] = [canonical(p) for p in report.get('materials_reviewed', [])]
    for finding in report.get('shared_findings', []):
        for evidence in finding.get('evidence', []):
            evidence['path'] = canonical(evidence['path'])
    return corrections


def render(work, report):
    lines = [f"# family {report['family_id']}：GLM 静态审核草稿", '',
             '结构和引用范围已自动核对；发现尚待人类/主代理复核，未仿真。', '', report['circuit_summary'], '',
             '电路依据：'+report['architecture_status']+'；'+report['architecture_basis'], '']
    for form in report['forms']:
        lines += [f"## {form['task_id']} / {form['form']} / {form['disposition']}", '']
        for key, label in [('engineering_value','工程价值'), ('contract_assessment','规格'), ('reference_assessment','参考实现'), ('checker_assessment','验收'), ('rewrite_allowed_value','整体重写后的价值'), ('next_action','下一步')]:
            lines += [f"{label}：{form[key]}", '']
    lines += ['## 具体发现', '']
    for f in report['shared_findings']:
        lines += [f"### {f['id']} ({f['severity']})", '', f['claim'], '', f['impact'], '']
        lines += [f"- [{e['path']}:{e['line_start']}]({ROOT / e['path']}:{e['line_start']})" for e in f['evidence']]
        lines += ['']
    lines += ['## 改编建议', ''] + [f"- {i['category']}：{i['proposal']} {i['rationale']}" for i in report['migration_ideas']]
    lines += ['', '## 尚待确认', ''] + ['- '+s for s in report['uncertainties']]
    (work / 'review.md').write_text('\n'.join(lines) + '\n')


def attempt(run, family_id, budget, timeout, output_tokens):
    work = run / 'families' / family_id
    inputs = json.loads((work / 'input.json').read_text())
    prompt = (work / 'prompt.md').read_text()
    if digest(prompt.encode()) != inputs['prompt_sha256']:
        raise ValueError('Frozen prompt changed')
    number = len(list(work.glob('attempt-*'))) + 1
    out = work / f'attempt-{number:02d}'
    out.mkdir()
    meta = dict(family_id=family_id, started_utc=now(), model_requested='glm-5.3',
                budget_usd=budget, timeout_s=timeout, max_output_tokens=output_tokens,
                status='running', prompt_sha256=inputs['prompt_sha256'], attempt=number)
    save(out / 'execution.json', meta)
    save(work / 'status.json', meta)
    argv = ['claude', '--print', '--model', 'glm-5.3', '--effort', 'high', '--tools', '',
            '--safe-mode', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
            '--setting-sources', 'user', '--disable-slash-commands', '--no-session-persistence',
            '--max-budget-usd', str(budget), '--output-format', 'json']
    meta['argv'] = argv
    env = os.environ.copy()
    env['CLAUDE_CODE_MAX_OUTPUT_TOKENS'] = str(output_tokens)
    start = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix='v4-audit-') as temp, (out / 'stdout.json').open('w') as stdout, (out / 'stderr.log').open('w') as stderr:
            proc = subprocess.Popen(argv, cwd=temp, env=env, stdin=subprocess.PIPE,
                                    stdout=stdout, stderr=stderr, text=True, start_new_session=True)
            meta.update(child_pid=proc.pid, child_process_group=proc.pid)
            save(out / 'execution.json', meta)
            save(work / 'status.json', meta)
            try:
                pending = prompt
                while True:
                    try:
                        proc.communicate(input=pending, timeout=2)
                        break
                    except subprocess.TimeoutExpired:
                        pending = None
                        if CANCELLED.is_set() or (run / 'STOP').exists():
                            raise InterruptedError('STOP file or supervisor signal requested cancellation')
                        if time.monotonic() - start > timeout:
                            raise TimeoutError(f'CLI exceeded {timeout} seconds')
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
            meta['returncode'] = proc.returncode
        raw = json.loads((out / 'stdout.json').read_text())
        meta.update(cli_subtype=raw.get('subtype'), num_turns=raw.get('num_turns'),
                    terminal_reason=raw.get('terminal_reason'),
                    usage=raw.get('usage'), model_usage=raw.get('modelUsage'), total_cost_usd=raw.get('total_cost_usd'))
        if proc.returncode != 0:
            raise ValueError(f'CLI exited {proc.returncode}: '+str(raw.get('result',''))[:2000])
        if raw.get('is_error'):
            raise ValueError('CLI error: ' + str(raw.get('subtype')))
        # Do not label an aliased/default model response as GLM 5.3.
        if not any('glm-5.3' in str(k).lower() or 'glm-5.3' in str(v.get('canonicalModel','')).lower()
                   for k, v in (raw.get('modelUsage') or {}).items() if isinstance(v, dict)):
            raise ValueError('Response does not confirm glm-5.3 model identity')
        response = raw.get('result', '')
        (out / 'response.txt').write_text(response)
        stripped = re.sub(r'^```(?:json)?\s*\n|\n```\s*$', '', response.strip())
        report = json.loads(stripped)
        corrections = normalize_paths(report, inputs)
        save(out / 'path-corrections.json', corrections)
        validate(report, inputs)
        save(out / 'review.json', report)
        save(work / 'review.json', report)
        render(work, report)
        meta['status'] = 'accepted_draft'
    except Exception as exc:
        meta.update(status='cancelled' if isinstance(exc, InterruptedError) else 'failed',
                    error=f'{type(exc).__name__}: {exc}')
    meta.update(finished_utc=now(), elapsed_s=round(time.monotonic()-start, 3))
    save(out / 'execution.json', meta)
    save(work / 'status.json', meta)
    return meta


def summary(run):
    manifest = json.loads((run / 'manifest.json').read_text())
    counts = Counter()
    rows = []
    review_rows = []
    dispositions = Counter()
    reported_cost = 0.0
    for family in manifest['families']:
        work = run / 'families' / family['family_id']
        status = json.loads((work / 'status.json').read_text()) if (work / 'status.json').exists() else {'status':'pending'}
        counts[status['status']] += 1
        for p in work.glob('attempt-*/execution.json'):
            reported_cost += json.loads(p.read_text()).get('total_cost_usd') or 0
        rows.append(dict(family_id=family['family_id'], status=status['status'], error=status.get('error'),
                         elapsed_s=status.get('elapsed_s')))
        forms = {}
        if status['status'] == 'accepted_draft':
            report = json.loads((work/'review.json').read_text())
            forms = {f['form']:f for f in report['forms']}
        for form, task_id in sorted(family['forms'].items()):
            details = forms.get(form, {})
            if details:
                dispositions[(form, details['disposition'])] += 1
            review_rows.append([family['family_id'], task_id, form, status['status'],
                                details.get('disposition', ''), details.get('engineering_value', ''),
                                details.get('next_action', ''), f'families/{family["family_id"]}/review.md' if details else ''])
    value = dict(updated_utc=now(), family_total=400, package_total=1200,
                 counts=dict(counts), accepted_package_drafts=counts['accepted_draft']*3,
                 cli_reported_cost_usd=round(reported_cost, 4),
                 model_disposition_counts={f'{form}/{decision}':count for (form,decision),count in sorted(dispositions.items())},
                 cost_note='CLI estimate only; not provider billing; missing failed-call usage is not zero cost',
                 verified_findings=0, families=rows)
    save(run / 'status.json', value)
    lines = ['# v4 全量静态审核进度', '', f"更新时间 UTC：{value['updated_utc']}", '',
             f"范围：400 家族、1200 包。状态：{dict(counts)}。", '',
             'accepted_draft 仅指结构/身份/引用范围校验通过；内容未逐项复核，未运行仿真。', '',
             '| 家族 | 状态 | 报告 |', '| --- | --- | --- |']
    for row in rows:
        fid = row['family_id']
        link = f'[草稿](families/{fid}/review.md)' if row['status']=='accepted_draft' else ''
        lines.append(f"| {fid} | {row['status']} | {link} |")
    (run / 'INDEX.md').write_text('\n'.join(lines)+'\n')
    with (run/'reviews.tsv').open('w') as stream:
        writer = csv.writer(stream, delimiter='\t')
        writer.writerow(['family_id','task_id','form','status','model_disposition','engineering_value','next_action','report'])
        writer.writerows(review_rows)
    return value


def execute(run, selected, workers, budget, timeout, output_tokens):
    if (run / 'STOP').exists():
        raise ValueError('Remove STOP explicitly before resuming')
    lock = run / 'supervisor.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.write(fd, json.dumps(dict(pid=os.getpid(), started_utc=now())).encode())
    os.close(fd)
    previous_signals = {sig: signal.signal(sig, lambda *_: CANCELLED.set())
                        for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        manifest = json.loads((run / 'manifest.json').read_text())
        family_ids = [f['family_id'] for f in manifest['families']]
        if selected:
            wanted = set(selected.split(','))
            if not wanted <= set(family_ids):
                raise ValueError('Unknown family IDs')
            family_ids = [f for f in family_ids if f in wanted]
        def job(fid):
            if CANCELLED.is_set() or (run/'STOP').exists():
                return {'family_id':fid,'status':'not_started_cancelled'}
            work = run/'families'/fid
            if (work/'status.json').exists() and json.loads((work/'status.json').read_text())['status']=='accepted_draft':
                return {'family_id':fid,'status':'already_accepted_draft'}
            return attempt(run, fid, budget, timeout, output_tokens)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(job, fid) for fid in family_ids]
            for future in as_completed(futures):
                result = future.result()
                print(json.dumps(result, ensure_ascii=False), flush=True)
                summary(run)
        print(json.dumps(summary(run)['counts']), flush=True)
    finally:
        for sig, handler in previous_signals.items():
            signal.signal(sig, handler)
        lock.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare','run','status'])
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--families', help='Comma separated 3-digit IDs; omitted means all 400')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--budget-usd', type=float, default=5)
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--output-tokens', type=int, default=32000)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    if not run.is_relative_to(ROOT/'runs'):
        parser.error('Raw outputs must be under this checkout runs/')
    if args.command == 'prepare':
        prepare(run)
    elif args.command == 'status':
        print(json.dumps(summary(run)['counts']))
    else:
        execute(run, args.families, args.workers, args.budget_usd, args.timeout, args.output_tokens)
