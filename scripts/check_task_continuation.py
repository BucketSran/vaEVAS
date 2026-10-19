"""Read the existing task scope/queue at Codex's Stop boundary; never mutate them.

This is a continuation check, not a scheduler or a simulator-result validator.
An opted-in main thread cannot end with unfinished runnable work. Other threads
and Interrupt are unaffected. Hook trust remains Codex's responsibility.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import sys


class StateError(ValueError):
    """The authoritative task state cannot support an end decision."""


def object_at(value, name):
    if not isinstance(value, dict):
        raise StateError(f'{name} must be an object')
    return value


def read_object(path):
    return object_at(json.loads(path.read_text()), str(path))


def timestamp(value):
    if not isinstance(value, str):
        raise StateError('deadline_utc must be an ISO8601 timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise StateError('deadline_utc must include a timezone')
    return result


def external_block(row, base):
    """An internal missing feature is work, not an external waiting condition."""
    block = row.get('continuation_block')
    if not isinstance(block, dict) or block.get('kind') not in (
            'external_dependency', 'human_decision'):
        return False
    evidence = block.get('evidence')
    if not isinstance(evidence, dict):
        return False
    try:
        path = base / evidence['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence['sha256']:
            return False
        receipt = read_object(path)
        return (receipt.get('case_id') == row['case_id']
                and receipt.get('blocker_kind') == block['kind']
                and isinstance(receipt.get('next_check'), str)
                and bool(receipt['next_check'].strip()))
    except (KeyError, OSError, ValueError):
        return False


def check_stop(scope_path, session_id, event, now=None):
    """Return Codex's native Stop decision, using only current task state."""
    event = object_at(event, 'hook event')
    if event.get('hook_event_name') != 'Stop' or event.get('session_id') != session_id:
        return {}
    scope_path = Path(scope_path).resolve()
    scope = read_object(scope_path)
    workspace = object_at(scope.get('workspace'), 'workspace')
    if workspace.get('main_thread') != session_id:
        raise StateError('hook binding differs from workspace.main_thread')
    workspace_root = Path(workspace['root']).resolve()
    cwd = Path(event['cwd']).resolve()
    if cwd != workspace_root and workspace_root not in cwd.parents:
        raise StateError('bound main thread cwd is outside workspace.root')
    current = object_at(scope.get('current'), 'current')
    policy = object_at(current.get('continuation', {}), 'current.continuation')
    status = policy.get('status', 'active')
    if status not in ('active', 'paused', 'waiting'):
        raise StateError('unknown continuation status')
    if status == 'paused':
        pause = object_at(policy.get('user_pause'), 'continuation.user_pause')
        if not isinstance(pause.get('message_ref'), str) or not pause['message_ref'].strip():
            raise StateError('pause requires a recorded human message_ref')
        return {}
    now = now or datetime.now(timezone.utc)
    # The old objective.morning_review_at and candidate freeze are historical
    # milestones. Only this execution window's explicit deadline can end it.
    if policy.get('deadline_utc') is not None and now >= timestamp(policy['deadline_utc']):
        return {}
    target = object_at(scope.get('objective'), 'objective').get('target')
    if type(target) is not int or target <= 0:
        raise StateError('objective.target must be a positive integer')
    queue_name = current.get('remaining_closure_ledger')
    if not isinstance(queue_name, str) or not queue_name:
        raise StateError('current.remaining_closure_ledger must name the existing queue')
    queue_path = scope_path.parent / queue_name
    queue = read_object(queue_path)
    rows = queue.get('cases')
    if not isinstance(rows, list) or len(rows) != target:
        raise StateError('existing queue must contain every fixed target ID')
    seen = set()
    remaining = []
    for row in rows:
        row = object_at(row, 'case')
        case_id = row.get('case_id')
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise StateError('case_id must be unique and nonempty')
        seen.add(case_id)
        verdict = row.get('revised_result')
        if verdict not in ('PASS', 'FAIL', 'REJECTED', 'TIMEOUT'):
            raise StateError(f'{case_id}: unknown revised_result')
        if verdict != 'PASS':
            remaining.append(row)
    # This task's existing queue is numbered 001..target. Cardinality alone
    # must not let a different task's equally sized roster satisfy this one.
    if seen != {f'{index:03d}' for index in range(1, target + 1)}:
        raise StateError('existing queue differs from the fixed numbered target IDs')
    passed = target - len(remaining)
    result_state = object_at(current.get('revised400'), 'current.revised400')
    recorded = result_state.get('passed')
    if type(recorded) is not int or recorded != passed:
        raise StateError('current.revised400.passed disagrees with the existing queue')
    if not remaining:
        acceptance = object_at(queue.get('acceptance_summary', {}), 'acceptance_summary')
        delivery = object_at(current.get('delivery_checks', {}), 'delivery_checks')
        if (result_state.get('target400_complete') is True
                and acceptance.get('target400_complete') is True
                and delivery.get('status') in ('closed', 'closed and draft publication verified')
                and not current.get('running_original_or_full_python_jobs')):
            return {}
        return {'decision': 'block', 'reason': (
            f'{passed}/{target}项已通过，但总体验收仍未闭合。'
            '收取并完成现有delivery_checks及运行中的验证，不能只凭通过计数结束。')}
    ready = [row for row in remaining if not external_block(row, queue_path.parent)]
    if not ready:
        return {}
    for row in ready:
        if not isinstance(row.get('next_action'), str) or not row['next_action'].strip():
            raise StateError(f"{row['case_id']}: missing next_action; repair the existing queue")
    examples = '; '.join(f"{row['case_id']}: {row['next_action']}" for row in ready[:3])
    # stop_hook_active intentionally does not waive an unchanged failed check.
    # A repeated attempt to stop is the same regression, not progress.
    return {'decision': 'block', 'reason': (
        f'总体目标未完成：{passed}/{target}，仍有{len(remaining)}项未通过，'
        f'其中{len(ready)}项有可继续动作。冻结候选或验收阶段完成不结束总体任务。'
        '收取现有执行结果，按current.next_actions选择并执行独立工作；'
        '只有真实外部阻塞、明确暂停或当前执行截止才可等待/结束。'
        f'现有队列示例：{examples}')}


def hook_config(scope_path, session_id):
    command = shlex.join([sys.executable, '-B', str(Path(__file__).resolve()),
                          '--scope', str(Path(scope_path).resolve()),
                          '--session-id', session_id])
    return {'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': command,
                                          'timeout': 5,
                                          'statusMessage': 'Checking task continuation'}]}]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', type=Path, required=True)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--print-hook-config', action='store_true')
    args = parser.parse_args()
    if args.print_hook_config:
        result = hook_config(args.scope, args.session_id)
    else:
        try:
            result = check_stop(args.scope, args.session_id, json.load(sys.stdin))
        except (OSError, ValueError, KeyError, TypeError) as error:
            result = {'decision': 'block', 'reason': (
                f'持续推进检查无法读取有效任务状态：{error}。'
                '修复现有scope/queue后重查；状态错误不是目标完成。')}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
