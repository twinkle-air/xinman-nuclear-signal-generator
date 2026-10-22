"""Reproduce pulse-height checks from the six preserved scope CSVs.

Constant first column is the sample interval, verified against scope screenshots.
The 256 us pulse grid avoids threshold censoring of low-energy events.
This is a relative code-domain check, not a voltage/energy calibration.
"""
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from nucsignal_app.importers import builtin_spectrum
from nucsignal_app.nuclear import spectrum_quantiles

ROOT = Path(__file__).resolve().parent


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header[:2] == ['Time [s]', 'CH2 [V]'], header
        rows = np.asarray([[float(r[0]), float(r[1])] for r in reader if len(r) >= 2 and r[0].strip()])
    assert np.isfinite(rows).all() and len(rows) == 4000
    assert np.all(rows[:, 0] == 4e-6), 'Unexpected interval; review screenshot first'
    return rows[:, 1]


def segment(y):
    # Sum leading-edge drop over all cycles at each possible grid phase.
    drops = -np.diff(y)
    score = np.array([drops[(np.arange(len(drops)) + 1) % 64 == p].sum() for p in range(64)])
    phase = int(score.argmax())
    starts = np.arange(phase, len(y) - 63, 64)
    return phase, starts, np.stack([y[s:s+64] for s in starts])


def fit(cycles, tau):
    # OLS baseline and exponential coefficient; first two samples excluded to
    # avoid the edge. All scheduled cycles retained, even near zero amplitude.
    k = np.arange(2, 64)
    design = np.column_stack((np.ones(len(k)), -np.exp(-k*4/tau)))
    pars = np.linalg.lstsq(design, cycles[:, k].T, rcond=None)[0].T
    residual = cycles[:, k] - pars @ design.T
    return pars, np.sqrt(np.mean(residual**2, axis=1))


def main():
    # Independent noiseless fixture: recover known coefficients and grid.
    k = np.arange(64)
    fixture = np.stack([.82 - amplitude*np.exp(-k*4/48) for amplitude in (2., .7, .1)])
    recovered, error = fit(fixture, 48)
    assert np.allclose(recovered[:, 1], [2., .7, .1]) and np.max(error) < 1e-12
    fixture_y = np.tile(fixture[0], 8)
    phase, _, recovered_cycles = segment(fixture_y)
    assert phase == 0 and len(recovered_cycles) == 8
    signals = [read(ROOT/'raw'/f'scope_csv_99_{i}.csv') for i in range(9, 15)]
    segmented = [segment(y) for y in signals]
    ref = segmented[0][2]
    # Reference-only tau fit, frozen before fitting any spectrum captures.
    candidates = np.linspace(30, 65, 1401)
    tau = float(min(candidates, key=lambda t: np.mean(fit(ref, t)[1]**2)))
    ref_pars, ref_err = fit(ref, tau)
    scale = float(np.median(ref_pars[:, 1]))/84
    assert scale > 0
    table = spectrum_quantiles(builtin_spectrum('Cs-137'))
    table_path = ROOT/'target_quantiles_256.bin'
    if table_path.exists():
        assert table_path.read_bytes() == table, 'Template source changed; preserve original target'
    else:
        table_path.write_bytes(table)
    expected = (84*np.frombuffer(table, dtype=np.uint8).astype(int)+127)//255
    files, pulses = [], []
    for i, (y, (phase, starts, cycles)) in enumerate(zip(signals, segmented), 9):
        pars, err = fit(cycles, tau)
        code = pars[:, 1]/scale
        p = ROOT/'raw'/f'scope_csv_99_{i}.csv'
        files.append(dict(file=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest(), samples=len(y),
                          dt_us=4, duration_ms=16, grid_phase=phase, complete_cycles=len(cycles),
                          min_V=float(y.min()), max_V=float(y.max()), baseline_fit_median_V=float(np.median(pars[:, 0])),
                          relative_height_median_codes=float(np.median(code)),
                          relative_height_std_codes=float(np.std(code, ddof=1)), residual_rms_median_V=float(np.median(err))))
        for s, c, par, e in zip(starts, code, pars, err):
            pulses.append(dict(file=p.name, start_index=int(s), height_coefficient_V=float(par[1]),
                               baseline_V=float(par[0]), relative_height_codes=float(c), fit_rms_V=float(e)))
    assert len(set(f['sha256'] for f in files)) == 6, 'Duplicate source capture'
    obs = np.array([p['relative_height_codes'] for p in pulses if p['file'] != 'scope_csv_99_9.csv'])
    peak = obs[(obs>=23) & (obs<=33)]
    edges = np.array([-np.inf, 5, 12, 20, 23, 33, np.inf])
    bins = dict(observed=np.histogram(obs, edges)[0].tolist(), expected_probabilities=(np.histogram(expected, edges)[0]/256).tolist(),
                labels=['<5', '5..12', '12..20', '20..23', '23..33', '>=33'])
    summary = dict(status='RELATIVE_PULSE_HEIGHT_SCREENING_ONLY', config_user_confirmed=True, assumed_config=dict(baseline=96, amplitude=84, period_us=256, tau_us=48, random=False, noise=0,
                   reference='99_9 spectrum OFF', spectrum='99_10..14 Cs-137 ON'),
                   files=files, reference_tau_fit_us=tau, relative_scale_V_per_code=scale,
                   spectrum_cycles=len(obs), observed_quantiles=np.quantile(obs, [.05,.25,.5,.75,.95]).tolist(),
                   expected_code_quantiles=np.quantile(expected, [.05,.25,.5,.75,.95]).tolist(),
                   peak_window_codes=[23,33], peak_window_count=len(peak), peak_window_median_codes=float(np.median(peak)),
                   expected_peak_window_probability=float(np.mean((expected>=23)&(expected<=33))), coarse_bins=bins,
                   limitations=['4 us sample phase may differ between reference and spectrum captures.',
                                'OLS exponential is approximate; DAC quantization and analog response remain.',
                                'Grid extraction assumes fixed 256 us arrival; not a random-arrival test.',
                                'No calibrated energy conversion or FWHM accuracy claim.'])
    (ROOT/'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    with (ROOT/'pulses.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(pulses[0])); writer.writeheader(); writer.writerows(pulses)
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    x = np.arange(len(signals[0]))*.004
    ax[0].plot(x[:640], signals[0][:640], label='Fixed amplitude reference', linewidth=.9)
    ax[0].plot(x[:640], signals[1][:640], label='Cs-137 capture', linewidth=.9)
    ax[0].set(xlabel='Time (ms)', ylabel='CH2 (V)', title='Measured waveforms (first 2.56 ms)'); ax[0].legend(fontsize=8)
    hist_edges=np.arange(-2, 38, 2)
    ax[1].hist(obs,bins=hist_edges,weights=np.ones(len(obs))/len(obs),alpha=.65,label=f'Measured, n={len(obs)}')
    counts,_=np.histogram(expected,hist_edges)
    ax[1].stairs(counts/256,hist_edges,color='black',label='Uploaded quantile-table target')
    ax[1].set(xlabel='Relative pulse height (DAC codes; reference scaled)',ylabel='Fraction per bin',title='Coarse spectrum screening; uncalibrated')
    ax[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(ROOT/'pulse_height_check.png',dpi=180); plt.close(fig)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
