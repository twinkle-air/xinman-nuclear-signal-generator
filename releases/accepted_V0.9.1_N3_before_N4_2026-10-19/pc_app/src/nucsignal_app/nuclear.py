"""Single-channel code-domain quantile table and integer reference generator."""
import math

import numpy as np


def spectrum_quantiles(source) -> bytes:
    if source.kind != "spectrum":
        raise ValueError("核信号模式需要能谱，不能使用逐点波形")
    x, weights = np.asarray(source.x, dtype=float), np.asarray(source.y, dtype=float)
    if (x.ndim != 1 or weights.shape != x.shape or x.size < 2
            or not np.isfinite(x).all() or not np.isfinite(weights).all()
            or (x < 0).any() or (np.diff(x) <= 0).any() or (weights < 0).any()
            or not math.isfinite(float(weights.sum())) or weights.sum() <= 0):
        raise ValueError("能谱轴须递增非负，计数须非负有限且总和大于0")
    scale = source.full_scale_x if source.full_scale_x is not None else float(x[-1])
    if not math.isfinite(scale) or scale <= 0 or x[-1] > scale:
        raise ValueError("能谱满量程无效")
    cdf = np.cumsum(weights / weights.sum())
    indices = np.searchsorted(cdf, (np.arange(256) + 0.5) / 256, side="left")
    return np.floor(x[np.minimum(indices, x.size - 1)] / scale * 255 + 0.5).astype(np.uint8).tobytes()


def advance(x: int) -> int:
    x ^= (x << 13) & 0xffffffff
    x ^= x >> 17
    return (x ^ (x << 5)) & 0xffffffff


def reference(config, samples: int):
    """1us updates; geometric arrivals, additive exponential pileup, bounded uniform noise."""
    config.validate()
    event_rng = config.seed
    amp_rng = (config.seed ^ 0x6a09e667) or 1
    noise_rng = (config.seed ^ 0xbb67ae85) or 1
    probability = math.floor(2**32 / config.period_us + 0.5)
    alpha = math.floor(math.exp(-1 / config.tau_us) * 65536 + 0.5)
    level = 0
    codes = np.empty(samples, dtype=np.uint8)
    events, amplitudes, clips = [], [], 0
    for i in range(samples):
        event_rng, amp_rng, noise_rng = advance(event_rng), advance(amp_rng), advance(noise_rng)
        fire = event_rng < probability if config.random_events else i % config.period_us == 0
        if fire:
            amp = config.amplitude_code
            if config.spectrum_table:
                amp = (amp * config.spectrum_table[amp_rng & 255] + 127) // 255
            level += amp << 16
            events.append(i)
            amplitudes.append(amp)
        overflow = level > (255 << 16)
        level = min(level, 255 << 16)
        noise = (((noise_rng >> 8) & 255) * (2 * config.noise_peak_codes + 1) >> 8) - config.noise_peak_codes
        value = config.baseline_code + ((level + 32768) >> 16) + noise
        clips += int(overflow or value < 0 or value > 255)
        codes[i] = min(255, max(0, value))
        level = (level * alpha) >> 16
    return codes, np.asarray(events), np.asarray(amplitudes), clips
