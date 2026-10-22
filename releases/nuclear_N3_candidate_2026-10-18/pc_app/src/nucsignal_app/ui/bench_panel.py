from PySide6.QtWidgets import QFormLayout, QLabel, QSpinBox, QDoubleSpinBox, QWidget, QCheckBox

from ..bench import BenchConfig


class BenchPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        form = QFormLayout(self)
        self.baseline = QSpinBox(); self.baseline.setRange(0, 255); self.baseline.setValue(16)
        self.amplitude = QSpinBox(); self.amplitude.setRange(0, 255); self.amplitude.setValue(224)
        self.period = QSpinBox(); self.period.setRange(128, 10000); self.period.setValue(1000); self.period.setSuffix(" μs")
        self.tau = QDoubleSpinBox(); self.tau.setRange(1, 100); self.tau.setValue(12); self.tau.setDecimals(2); self.tau.setSuffix(" μs")
        self.nuclear = False
        self.table = b""
        self.random = QCheckBox("随机到达（1 μs离散泊松近似）")
        self.spectrum = QCheckBox("按所选能谱分配幅度")
        self.noise = QSpinBox(); self.noise.setRange(0,32); self.noise.setSuffix(" 码（峰值）")
        self.seed = QSpinBox(); self.seed.setRange(1,2147483647); self.seed.setValue(1)
        self.info = QLabel("单通道 · 固定周期 · 单指数\n基线码＋幅度码≤255；周期≥5τ\n未校准：仅使用DAC码值，不换算伏特")
        self.info.setWordWrap(True)
        form.addRow(self.info)
        form.addRow("基线码", self.baseline)
        form.addRow("幅度码差", self.amplitude)
        form.addRow("周期", self.period)
        form.addRow("衰减常数 τ", self.tau)
        form.addRow(self.random)
        form.addRow(self.spectrum)
        form.addRow("均匀噪声",self.noise)
        form.addRow("随机种子",self.seed)
        self.set_nuclear(False)
        self.readback = QLabel("尚未连接：等待设备活动参数回读")
        self.readback.setWordWrap(True)
        form.addRow("活动参数", self.readback)

    def set_nuclear(self, enabled):
        self.nuclear = enabled
        for control in (self.random,self.spectrum,self.noise,self.seed):
            control.setVisible(enabled)
        for control in (self.noise,self.seed):
            self.layout().labelForField(control).setVisible(enabled)
        self.info.setText("单通道 · 单指数叠加 · 1 μs步进\n随机模式周期栏为平均间隔；均匀噪声为±峰值码\n能谱以满量程轴映射到最大幅度码；未校准电压" if enabled else
                          "单通道 · 固定周期 · 单指数\n基线码＋幅度码≤255；周期≥5τ\n未校准：仅使用DAC码值，不换算伏特")

    def config(self) -> BenchConfig:
        if self.nuclear and self.spectrum.isChecked() and len(self.table)!=256:
            raise ValueError("尚无有效能谱分位表")
        return BenchConfig(self.baseline.value(), self.amplitude.value(), self.period.value(), self.tau.value(),
                           nuclear=self.nuclear, random_events=self.nuclear and self.random.isChecked(),
                           noise_peak_codes=self.noise.value() if self.nuclear else 0,
                           seed=self.seed.value(), spectrum_table=self.table if self.nuclear and self.spectrum.isChecked() else b"")
