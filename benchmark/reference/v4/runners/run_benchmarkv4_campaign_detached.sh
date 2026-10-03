#!/bin/sh
set -eu

usage() {
    echo "usage: $0 --log PATH --pid-file PATH -- [run_benchmarkv4_campaign.py arguments]" >&2
    exit 2
}

log_path=
pid_path=
while [ "$#" -gt 0 ]; do
    case "$1" in
        --log)
            [ "$#" -ge 2 ] || usage
            log_path=$2
            shift 2
            ;;
        --pid-file)
            [ "$#" -ge 2 ] || usage
            pid_path=$2
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            usage
            ;;
    esac
done

[ -n "$log_path" ] || usage
[ -n "$pid_path" ] || usage
[ "$#" -gt 0 ] || usage

runner_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python_command=${VABENCH_PYTHON:-python3}
mkdir -p -- "$(dirname -- "$log_path")" "$(dirname -- "$pid_path")"
umask 077

nohup "$python_command" "$runner_dir/run_benchmarkv4_campaign.py" "$@" \
    </dev/null >>"$log_path" 2>&1 &
runner_pid=$!
printf '%s\n' "$runner_pid" >"$pid_path"
printf 'Started vaBench campaign runner with PID %s; log: %s\n' "$runner_pid" "$log_path"
