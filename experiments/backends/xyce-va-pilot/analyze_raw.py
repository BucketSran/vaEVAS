#!/usr/bin/env python3
"""Standalone extraction of verify.py's tb_fft observables from a raw file.

Usage: python3 analyze_raw.py <raw file> [supply] -> JSON metrics row
Mirrors bench/tests/verify.py: parse_raw/sample/stored/average_source_power/analyze_fft.
"""
import bisect, cmath, json, math, sys
from pathlib import Path

POWER_START_S = 80e-9
POWER_STOP_S = 880e-9
FFT_POINTS = 80
FUNDAMENTAL_BIN = 4
INPUT_AMPLITUDE_EACH_SIDE_V = 0.4


def parse_raw(path):
    lines = Path(path).read_text(errors="replace").splitlines()
    variables = next(i for i, l in enumerate(lines) if l.startswith("Variables:"))
    count = int(next(l.split(":", 1)[1] for l in lines if l.startswith("No. Variables:")))
    points = int(next(l.split(":", 1)[1] for l in lines if l.startswith("No. Points:")))
    names = [lines[variables + i + 1].strip().split()[1].lower() for i in range(count)]
    cursor = next(i for i, l in enumerate(lines[variables:], variables) if l.startswith("Values:")) + 1
    vectors = {n: [] for n in names}
    for _ in range(points):
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        values = [float(lines[cursor].strip().split()[-1])]
        cursor += 1
        for _ in range(1, count):
            values.append(float(lines[cursor].strip().split()[-1]))
            cursor += 1
        for n, v in zip(names, values):
            vectors[n].append(v)
    return vectors


def sample(times, values, target):
    index = bisect.bisect_left(times, target)
    span = times[index] - times[index - 1]
    fraction = (target - times[index - 1]) / span
    return values[index - 1] + fraction * (values[index] - values[index - 1])


def stored(vectors, when):
    times = vectors["time"]
    positive = sample(times, vectors["v(vsp)"], when) - sample(times, vectors["v(vtopp)"], when)
    negative = sample(times, vectors["v(vsn)"], when) - sample(times, vectors["v(vtopn)"], when)
    return positive - negative, 0.5 * (positive + negative)


def average_source_power(vectors, voltage, current, start, stop):
    times = vectors["time"]
    window_times = [start]
    window_times.extend(times[bisect.bisect_right(times, start):bisect.bisect_left(times, stop)])
    window_times.append(stop)
    products = [
        -(float(voltage) if isinstance(voltage, float) else sample(times, vectors[voltage], when))
        * sample(times, vectors[current], when)
        for when in window_times
    ]
    energy = sum(
        0.5 * (products[i - 1] + products[i]) * (window_times[i] - window_times[i - 1])
        for i in range(1, len(window_times))
    )
    return max(0.0, energy / (stop - start))


def analyze_fft(vectors, supply):
    held, common_mode = [], []
    for cycle in range(8, 8 + FFT_POINTS):
        differential, common = stored(vectors, 9e-9 + cycle * 10e-9)
        held.append(differential)
        common_mode.append(common)
    spectrum = [
        sum(v * cmath.exp(-2j * math.pi * b * i / FFT_POINTS) for i, v in enumerate(held))
        for b in range(FFT_POINTS)
    ]
    signal = abs(spectrum[FUNDAMENTAL_BIN]) ** 2
    spur = max(abs(spectrum[i]) ** 2 for i in range(1, FFT_POINTS // 2) if i != FUNDAMENTAL_BIN)
    source_powers = {
        "vdd_source_power_w": average_source_power(vectors, supply, "i(vdd)", POWER_START_S, POWER_STOP_S),
        "vcm_source_power_w": average_source_power(vectors, "v(vcm)", "i(vcm)", POWER_START_S, POWER_STOP_S),
        "vinp_source_power_w": average_source_power(vectors, "v(vinp)", "i(vinp)", POWER_START_S, POWER_STOP_S),
        "vinn_source_power_w": average_source_power(vectors, "v(vinn)", "i(vinn)", POWER_START_S, POWER_STOP_S),
        "clock_source_power_w": average_source_power(vectors, "v(clk_src)", "i(vclk)", POWER_START_S, POWER_STOP_S),
    }
    row = {
        "sfdr_db": 10 * math.log10(signal / max(spur, 1e-300)),
        "gain_error": abs(abs(spectrum[FUNDAMENTAL_BIN]) / (FFT_POINTS * INPUT_AMPLITUDE_EACH_SIDE_V) - 1),
        "stored_common_mode_error_v": max(abs(v) for v in common_mode),
        **source_powers,
        "total_source_power_w": sum(source_powers.values()),
    }
    row["held_samples"] = held
    return row


if __name__ == "__main__":
    raw = sys.argv[1]
    supply = float(sys.argv[2]) if len(sys.argv) > 2 else 1.8
    vectors = parse_raw(raw)
    missing = [v for v in ("time", "v(vsp)", "v(vsn)", "v(vtopp)", "v(vtopn)", "v(clk_src)", "v(vcm)", "v(vinp)", "v(vinn)", "i(vdd)", "i(vcm)", "i(vinp)", "i(vinn)", "i(vclk)") if v not in vectors]
    if missing:
        sys.exit(f"missing vectors: {missing}\navailable: {sorted(vectors)}")
    print(json.dumps(analyze_fft(vectors, supply), indent=2))
