from PySide6.QtWidgets import QFormLayout, QLabel, QSpinBox, QDoubleSpinBox, QWidget

from ..bench import BenchConfig


class BenchPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        form = QFormLayout(self)
        self.baseline = QSpinBox(); self.baseline.setRange(0, 255); self.baseline.setValue(16)
        self.amplitude = QSpinBox(); self.amplitude.setRange(0, 255); self.amplitude.setValue(224)
        self.period = QSpinBox(); self.period.setRange(128, 10000); self.period.setValue(1000); self.period.setSuffix(" μs")
        self.tau = QDoubleSpinBox(); self.tau.setRange(1, 100); self.tau.setValue(12); self.tau.setDecimals(2); self.tau.setSuffix(" μs")
        self.info = QLabel("单通道 · 固定周期 · 单指数\n基线码＋幅度码≤255；周期≥5τ\n未校准：仅使用DAC码值，不换算伏特")
        self.info.setWordWrap(True)
        form.addRow(self.info)
        form.addRow("基线码", self.baseline)
        form.addRow("幅度码差", self.amplitude)
        form.addRow("周期", self.period)
        form.addRow("衰减常数 τ", self.tau)
        self.readback = QLabel("尚未连接：等待设备活动参数回读")
        self.readback.setWordWrap(True)
        form.addRow("活动参数", self.readback)

    def config(self) -> BenchConfig:
        return BenchConfig(self.baseline.value(), self.amplitude.value(), self.period.value(), self.tau.value())
