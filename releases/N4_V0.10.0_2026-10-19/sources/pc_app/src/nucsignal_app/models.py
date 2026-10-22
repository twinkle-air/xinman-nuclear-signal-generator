from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class PulseShape(str, Enum):
    SINGLE = "单指数"
    DOUBLE = "双指数"


class ArrivalMode(str, Enum):
    PERIODIC = "固定周期"
    POISSON = "泊松到达"


class PileupMode(str, Enum):
    PILEUP = "PILEUP"
    NON_OVERLAP = "NON_OVERLAP"


class NoiseType(str, Enum):
    WHITE = "高斯白噪声"
    BAND_LIMITED = "带限噪声"


@dataclass(slots=True)
class ChannelConfig:
    enabled: bool = True
    pulse_shape: PulseShape = PulseShape.DOUBLE
    amplitude_v: float = 1.5
    rise_us: float = 1.0
    decay_us: float = 10.0
    mean_interval_us: float = 20.0
    arrival_mode: ArrivalMode = ArrivalMode.POISSON
    pileup_mode: PileupMode = PileupMode.PILEUP
    noise_type: NoiseType = NoiseType.BAND_LIMITED
    noise_rms_percent: float = 2.0
    baseline_v: float = 0.25
    drift_mv: float = 2.0
    seed: int = 20260817

    def validate(self) -> None:
        if not 0 <= self.amplitude_v <= 5:
            raise ValueError("幅度必须在 0–5 V 范围内")
        if self.rise_us <= 0 or self.decay_us <= 0:
            raise ValueError("时间常数必须大于 0")
        if self.pulse_shape == PulseShape.DOUBLE and self.rise_us >= self.decay_us:
            raise ValueError("双指数脉冲要求上升时间常数小于衰减时间常数")
        if self.mean_interval_us <= 0:
            raise ValueError("周期/平均间隔必须大于 0")
        if not 0 <= self.noise_rms_percent <= 20:
            raise ValueError("噪声必须在 0–20%FS 范围内")
        if not 0 <= self.baseline_v <= 5:
            raise ValueError("基线必须在 0–5 V 范围内")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key, value in result.items():
            if isinstance(value, Enum):
                result[key] = value.value
        return result


@dataclass(slots=True)
class SignalSource:
    name: str
    kind: str
    x: np.ndarray
    y: np.ndarray
    source_path: Path | None = None
    sha256: str | None = None
    full_scale_x: float | None = None
    reference_peaks: tuple[float, ...] = ()


@dataclass(slots=True)
class SimulationResult:
    time_us: np.ndarray
    voltage_v: np.ndarray
    ideal_v: np.ndarray
    event_times_us: np.ndarray
    event_amplitudes_v: np.ndarray
    rms_noise_v: float
    clip_count: int
    pileup_count: int
