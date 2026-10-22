"""F405-B2.0.0台架契约：只使用DAC码域，不隐含电压校准。"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class BenchConfig:
    baseline_code: int = 16
    amplitude_code: int = 224
    period_us: int = 1000
    tau_us: float = 12.0

    nuclear: bool = False
    random_events: bool = False
    noise_peak_codes: int = 0
    seed: int = 1
    spectrum_table: bytes = b""

    def validate(self) -> None:
        if any(type(value) is not int for value in (self.baseline_code, self.amplitude_code, self.period_us)):
            raise ValueError("基线码、幅度码及周期必须是整数")
        if not (0 <= self.baseline_code <= 255 and 0 <= self.amplitude_code <= 255):
            raise ValueError("DAC码必须在0–255范围内")
        if self.baseline_code + self.amplitude_code > 255:
            raise ValueError("基线码＋幅度码必须≤255")
        if not math.isfinite(self.tau_us) or not 1 <= self.tau_us <= 100:
            raise ValueError("τ必须在1–100 μs范围内")
        if not 128 <= self.period_us <= 10000 or (not self.random_events and self.period_us < 5 * self.tau_us):
            raise ValueError("周期须为128–10000 μs，且不小于5τ")

        if type(self.seed) is not int or not 1 <= self.seed <= 0xffffffff:
            raise ValueError("随机种子必须为1–4294967295")
        if type(self.noise_peak_codes) is not int or not 0 <= self.noise_peak_codes <= 32:
            raise ValueError("均匀噪声峰值必须为0–32码")
        if self.baseline_code < self.noise_peak_codes or self.baseline_code+self.amplitude_code+self.noise_peak_codes > 255:
            raise ValueError("基线及幅度需为噪声保留上下余量")
        if not isinstance(self.spectrum_table, bytes) or len(self.spectrum_table) not in (0, 256):
            raise ValueError("能谱分位表必须为256字节")
        if not self.nuclear and (self.random_events or self.noise_peak_codes or self.spectrum_table):
            raise ValueError("随机/噪声/能谱需要N3固件")

    def payload(self) -> dict:
        self.validate()
        return {
            "channel": 1, "enabled": True,
            "dac_baseline_code": self.baseline_code,
            "dac_amplitude_code": self.amplitude_code,
            "mean_interval_us": self.period_us, "decay_us": self.tau_us,
            **({"random_events": int(self.random_events), "noise_peak_codes": self.noise_peak_codes,
                "spectrum_enabled": int(bool(self.spectrum_table)), "seed": self.seed} if self.nuclear else {}),
        }

    def matches(self, status: dict) -> bool:
        return (
            status.get("dac_baseline_code") == self.baseline_code
            and status.get("dac_amplitude_code") == self.amplitude_code
            and status.get("period_us") == self.period_us
            and isinstance(status.get("decay_us"), (int, float))
            and abs(status["decay_us"] - self.tau_us) <= 0.011
            and (not self.nuclear or (status.get("random_events") == int(self.random_events)
                and status.get("noise_peak_codes") == self.noise_peak_codes
                and status.get("spectrum_enabled") == int(bool(self.spectrum_table))
                and status.get("seed") == self.seed
                and (not self.spectrum_table or status.get("spectrum_crc32") == zlib.crc32(self.spectrum_table))))
        )

    def preview(self) -> tuple[np.ndarray, np.ndarray]:
        self.validate()
        if self.nuclear:
            from .nuclear import reference
            samples = min(60000, max(10000, self.period_us * 10))
            return np.arange(samples, dtype=float), reference(self, samples)[0].astype(float)
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
