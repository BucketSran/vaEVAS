"""Final-evaluation cases added to the public ones (kept out of the solver image)."""

F_K = [4.5e9 + k * 3e9 / 7 for k in range(8)]     # the eight seed carriers


def final_cases():
    # other carriers and parameters, four instances on the same inputs; VIN 0.9 V
    params = dict(
        name='carriers_params', vin=0.9, stop=5.5e-9,
        instances=[dict(name='lo', params=dict(f_rf=F_K[0], df_start=-0.02, t99_amp=100e-12, t99_freq=300e-12)),
                   dict(name='hi', params=dict(f_rf=F_K[7], phi0=1.0, a_ro=0.5, vth=0.35)),
                   dict(name='fstep', params=dict(f_rf=F_K[2], t99_amp=0.0, t99_freq=150e-12, df_start=0.03,
                                                  phi0=-2.0)),
                   dict(name='aonly', params=dict(f_rf=F_K[5], t99_amp=120e-12, t99_freq=0.0, df_start=0.02,
                                                  phi0=0.5))],
        pwr=[(0.4e-9, 1), (2.6e-9, 0), (3.0e-9, 1), (5.0e-9, 0)],
        pre=[(0.4e-9, 1), (0.6e-9, 0), (3.0e-9, 1), (3.2507e-9, 0)],
        rel=[(0.6e-9, 1), (2.4e-9, 0), (3.2507e-9, 1), (5.0e-9, 0)])
    # one release held for 5 ns: the phase continues without reset; VIN 1.2 V
    hold = dict(
        name='long_hold', vin=1.2, stop=6.2e-9,
        instances=[dict(name='seed', params={}),
                   dict(name='fast', params=dict(f_rf=F_K[7], df_start=-0.01, t99_amp=300e-12, t99_freq=100e-12,
                                                 vth=0.9))],
        pwr=[(0.3e-9, 1), (5.8e-9, 0)],
        pre=[(0.3e-9, 1), (0.5e-9, 0)],
        rel=[(0.5e-9, 1), (5.5e-9, 0)])
    # pwr falls while rel stays high; rel rises while pwr is low; pwr rises
    # while rel is already high; then a normal cold start
    stops = dict(
        name='stop_paths', vin=1.0, stop=5.0e-9,
        instances=[dict(name='seed', params={}),
                   dict(name='step', params=dict(f_rf=F_K[1], phi0=1.0, t99_amp=0.0))],
        pwr=[(0.3e-9, 1), (1.6e-9, 0), (2.6e-9, 1), (4.6e-9, 0)],
        pre=[(0.3e-9, 1), (0.5e-9, 0), (3.0e-9, 1), (3.3e-9, 0)],
        rel=[(0.5e-9, 1), (2.0e-9, 0), (2.3e-9, 1), (2.9e-9, 0), (3.3e-9, 1), (4.6e-9, 0)])
    # four cold starts of different lengths, minimum precharge, release times
    # off the 1 ps grid
    restarts = dict(
        name='restarts', vin=1.0, stop=5.2e-9,
        instances=[dict(name='seed', params={}),
                   dict(name='mid', params=dict(f_rf=F_K[4], phi0=-1.2, df_start=0.04, t99_freq=250e-12))],
        pwr=[(0.2e-9, 1), (1.6874e-9, 0), (1.9e-9, 1), (4.9e-9, 0)],
        pre=[(0.2e-9, 1), (0.35e-9, 0), (0.75e-9, 1), (0.85e-9, 0), (1.9e-9, 1), (2.0003e-9, 0),
             (3.6e-9, 1), (3.7e-9, 0)],
        rel=[(0.35e-9, 1), (0.65e-9, 0), (0.85e-9, 1), (1.6874e-9, 0), (2.0003e-9, 1), (3.5e-9, 0),
             (3.7e-9, 1), (4.9e-9, 0)])
    return [params, hold, stops, restarts]
