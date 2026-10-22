from __future__ import annotations

import numpy as np

from .models import (
    ArrivalMode,
    ChannelConfig,
    NoiseType,
    PileupMode,
    PulseShape,
    SignalSource,
    SimulationResult,
)


SAMPLE_RATE_HZ = 50_000_000
DT_US = 1e6 / SAMPLE_RATE_HZ


def _event_times(config: ChannelConfig, duration_us: float, rng: np.random.Generator) -> np.ndarray:
    if config.arrival_mode == ArrivalMode.PERIODIC:
        return np.arange(0, duration_us, config.mean_interval_us, dtype=np.float64)
    times: list[float] = []
    current = 0.0
    while current < duration_us:
        current += float(rng.exponential(config.mean_interval_us))
        if current < duration_us:
            times.append(current)
    return np.asarray(times, dtype=np.float64)


def _sample_amplitudes(
    config: ChannelConfig,
    source: SignalSource,
    count: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if count == 0:
        return np.empty(0, dtype=np.float64)
    if source.kind == "spectrum":
        indices = rng.choice(source.y.size, size=count, p=source.y / source.y.sum())
        energy = source.x[indices]
        energy_scale = max(source.full_scale_x or float(np.max(source.x)), 1.0)
        relative = np.clip(energy / energy_scale, 0.01, 1.0)
        return config.amplitude_v * relative
    return np.full(count, config.amplitude_v, dtype=np.float64)


def _pulse_kernel(
    config: ChannelConfig,
    source: SignalSource | None = None,
    max_duration_us: float = 500.0,
) -> np.ndarray:
    if source is not None and source.kind == "waveform":
        kernel = np.asarray(source.y, dtype=np.float64)
        peak = float(np.max(np.abs(kernel)))
        return kernel / peak if peak > 0 else np.zeros_like(kernel)
    t = np.arange(0, max_duration_us, DT_US)
    if config.pulse_shape == PulseShape.SINGLE:
        kernel = np.exp(-t / config.decay_us)
    else:
        kernel = np.exp(-t / config.decay_us) - np.exp(-t / config.rise_us)
        peak = float(kernel.max())
        if peak > 0:
            kernel /= peak
    cutoff = np.flatnonzero(kernel >= 1e-4)
    return kernel[: cutoff[-1] + 1] if cutoff.size else kernel[:1]


def pulse_fwhm_us(config: ChannelConfig) -> float:
    """返回量化到50 MSPS网格后的等效半高宽。"""
    kernel = _pulse_kernel(config)
    if kernel.size == 0 or float(kernel.max()) <= 0:
        return 0.0
    indices = np.flatnonzero(kernel >= float(kernel.max()) / 2)
    return float((indices[-1] - indices[0] + 1) * DT_US) if indices.size else 0.0


def _noise(config: ChannelConfig, size: int, rng: np.random.Generator) -> np.ndarray:
    target_rms = config.noise_rms_percent / 100.0 * 5.0
    if target_rms == 0:
        return np.zeros(size)
    noise = rng.normal(0, 1, size)
    if config.noise_type == NoiseType.BAND_LIMITED:
        # 简单一阶低通，模拟经前端带宽限制后的相关噪声。
        alpha = 0.22
        filtered = np.empty_like(noise)
        filtered[0] = noise[0]
        for index in range(1, size):
            filtered[index] = filtered[index - 1] + alpha * (noise[index] - filtered[index - 1])
        noise = filtered
    rms = float(np.sqrt(np.mean(noise**2)))
    return noise * (target_rms / rms) if rms else np.zeros(size)


def simulate_channel(
    config: ChannelConfig,
    source: SignalSource,
    duration_us: float = 200.0,
) -> SimulationResult:
    config.validate()
    sample_count = max(2, int(round(duration_us / DT_US)))
    time_us = np.arange(sample_count, dtype=np.float64) * DT_US
    rng = np.random.default_rng(config.seed)
    events = _event_times(config, duration_us, rng) if config.enabled else np.empty(0)
    amplitudes = _sample_amplitudes(config, source, events.size, rng)
    kernel = _pulse_kernel(config, source)
    ideal = np.zeros(sample_count, dtype=np.float64)
    pileup_count = 0
    occupied_until = -1

    for event_time, amplitude in zip(events, amplitudes, strict=True):
        start = int(round(event_time / DT_US))
        if config.pileup_mode == PileupMode.NON_OVERLAP and start < occupied_until:
            continue
        end = min(sample_count, start + kernel.size)
        if start < occupied_until:
            pileup_count += 1
        ideal[start:end] += amplitude * kernel[: end - start]
        occupied_until = max(occupied_until, end)

    random_noise = _noise(config, sample_count, rng)
    drift = config.drift_mv / 1000.0 * np.sin(2 * np.pi * time_us / max(duration_us, 1.0))
    raw = config.baseline_v + ideal + random_noise + drift
    clipped = np.clip(raw, 0, 5)
    return SimulationResult(
        time_us=time_us,
        voltage_v=clipped,
        ideal_v=config.baseline_v + ideal,
        event_times_us=events,
        event_amplitudes_v=amplitudes,
        rms_noise_v=float(np.sqrt(np.mean(random_noise**2))),
        clip_count=int(np.count_nonzero(raw != clipped)),
        pileup_count=pileup_count,
    )
