"""F405-B2.0.0台架契约：只使用DAC码域，不隐含电压校准。"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class BenchConfig:
    baseline_code: int = 16
    amplitude_code: int = 224
    period_us: int = 1000
    tau_us: float = 12.0

    def validate(self) -> None:
        if any(type(value) is not int for value in (self.baseline_code, self.amplitude_code, self.period_us)):
            raise ValueError("基线码、幅度码及周期必须是整数")
        if not (0 <= self.baseline_code <= 255 and 0 <= self.amplitude_code <= 255):
            raise ValueError("DAC码必须在0–255范围内")
        if self.baseline_code + self.amplitude_code > 255:
            raise ValueError("基线码＋幅度码必须≤255")
        if not math.isfinite(self.tau_us) or not 1 <= self.tau_us <= 100:
            raise ValueError("τ必须在1–100 μs范围内")
        if not 128 <= self.period_us <= 10000 or self.period_us < 5 * self.tau_us:
            raise ValueError("周期须为128–10000 μs，且不小于5τ")

    def payload(self) -> dict:
        self.validate()
        return {
            "channel": 1, "enabled": True,
            "dac_baseline_code": self.baseline_code,
            "dac_amplitude_code": self.amplitude_code,
            "mean_interval_us": self.period_us, "decay_us": self.tau_us,
        }

    def matches(self, status: dict) -> bool:
        return (
            status.get("dac_baseline_code") == self.baseline_code
            and status.get("dac_amplitude_code") == self.amplitude_code
            and status.get("period_us") == self.period_us
            and isinstance(status.get("decay_us"), (int, float))
            and abs(status["decay_us"] - self.tau_us) <= 0.011
        )

    def preview(self) -> tuple[np.ndarray, np.ndarray]:
        self.validate()
        time_us = np.arange(0, self.period_us * 3, dtype=float)
        # 与FPGA一致：1μs更新，Q16 alpha，整数递推舍入。
        alpha = math.floor(math.exp(-1.0 / self.tau_us) * 65536 + 0.5)
        level = self.amplitude_code << 16
        codes = np.empty(time_us.size, dtype=float)
        for index in range(time_us.size):
            if index % self.period_us == 0:
                level = self.amplitude_code << 16
            codes[index] = min(255, self.baseline_code + ((level + 32768) >> 16))
            level = (level * alpha) >> 16
        return time_us, codes
