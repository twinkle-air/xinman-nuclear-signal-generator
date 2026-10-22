import math
from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QFormLayout, QLabel, QSpinBox, QDoubleSpinBox, QWidget, QCheckBox, QComboBox

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
        self.competition = False
        self.table = b""
        self.random = QCheckBox("随机到达（1 μs离散泊松近似）")
        self.spectrum = QCheckBox("按所选能谱分配幅度")
        self.noise = QSpinBox(); self.noise.setRange(0,32); self.noise.setSuffix(" 码（峰值）")
        self.seed = QSpinBox(); self.seed.setRange(1,2147483647); self.seed.setValue(1)
        self.noise_mode = QComboBox(); self.noise_mode.addItems(["均匀峰值码", "高斯 RMS %FS"])
        self.rms = QSpinBox(); self.rms.setRange(0,20); self.rms.setSuffix(" %FS RMS")
        self.pileup = QCheckBox("允许固定周期堆积（幅度可能改变/削顶）")
        self.fwhm = QDoubleSpinBox(); self.fwhm.setRange(.693,145*math.log(2)); self.fwhm.setDecimals(3); self.fwhm.setSingleStep(1); self.fwhm.setSuffix(" μs")
        self.fwhm.setValue(12 * math.log(2))
        self.fwhm.valueChanged.connect(self._width_changed)
        self.tau.valueChanged.connect(self._tau_changed)
        self.random.toggled.connect(self._period_range)
        self.noise_mode.currentIndexChanged.connect(self._noise_visibility)
        self.info = QLabel("单通道 · 固定周期 · 单指数\n基线码＋幅度码≤255；周期≥5τ\n未校准：仅使用DAC码值，不换算伏特")
        self.info.setWordWrap(True)
        form.addRow(self.info)
        form.addRow("基线码", self.baseline)
        form.addRow("幅度码差", self.amplitude)
        form.addRow("周期", self.period)
        form.addRow("衰减常数 τ", self.tau)
        form.addRow("半高宽 W=τln2", self.fwhm)
        form.addRow(self.random)
        form.addRow(self.spectrum)
        form.addRow("均匀噪声",self.noise)
        form.addRow("噪声模式", self.noise_mode)
        form.addRow("高斯噪声", self.rms)
        form.addRow(self.pileup)
        form.addRow("随机种子",self.seed)
        self.set_nuclear(False)
        self.readback = QLabel("尚未连接：等待设备活动参数回读")
        self.readback.setWordWrap(True)
        form.addRow("活动参数", self.readback)

    def set_nuclear(self, enabled, competition=False):
        self.nuclear = enabled
        self.competition = enabled and competition
        self.tau.setMaximum(145 if self.competition else 100)
        self._period_range()
        for control in (self.noise_mode, self.rms, self.fwhm, self.pileup):
            control.setVisible(self.competition)
            label = self.layout().labelForField(control)
            if label:
                label.setVisible(self.competition)
        for control in (self.random,self.spectrum,self.noise,self.seed):
            control.setVisible(enabled)
        for control in (self.noise,self.seed):
            self.layout().labelForField(control).setVisible(enabled)
        self.info.setText("单通道 · 单指数叠加 · 1 μs步进\n随机模式周期栏为平均间隔；均匀噪声为±峰值码\n能谱以满量程轴映射到最大幅度码；未校准电压" if enabled else
                          "单通道 · 固定周期 · 单指数\n基线码＋幅度码≤255；周期≥5τ\n未校准：仅使用DAC码值，不换算伏特")
        if self.competition:
            self.info.setText("N4 · 单指数 · 1 μs更新\n固定10–10000 μs；随机平均≥128 μs\n高斯为有限尾部近似；%FS按255码，电压需校准")
        self._noise_visibility()

    def _period_range(self):
        self.period.setMinimum(10 if self.competition and not self.random.isChecked() else 128)

    def _noise_visibility(self):
        gaussian = self.competition and self.noise_mode.currentIndex() == 1
        self.noise.setVisible(self.nuclear and not gaussian)
        self.layout().labelForField(self.noise).setVisible(self.nuclear and not gaussian)
        self.rms.setVisible(gaussian)
        self.layout().labelForField(self.rms).setVisible(gaussian)

    def _width_changed(self, value):
        blocker = QSignalBlocker(self.tau)
        self.tau.setValue(value / math.log(2))
        del blocker
        self.tau.valueChanged.emit(self.tau.value())

    def _tau_changed(self, value):
        blocker = QSignalBlocker(self.fwhm)
        self.fwhm.setValue(value * math.log(2))
        del blocker

    def config(self) -> BenchConfig:
        if self.nuclear and self.spectrum.isChecked() and len(self.table)!=256:
            raise ValueError("尚无有效能谱分位表")
        return BenchConfig(self.baseline.value(), self.amplitude.value(), self.period.value(), self.tau.value(),
                           nuclear=self.nuclear, random_events=self.nuclear and self.random.isChecked(),
                           noise_peak_codes=self.noise.value() if self.nuclear and not (self.competition and self.noise_mode.currentIndex()==1) else 0,
                           seed=self.seed.value(), spectrum_table=self.table if self.nuclear and self.spectrum.isChecked() else b"",
                           competition=self.competition, noise_mode="gaussian" if self.competition and self.noise_mode.currentIndex()==1 else "uniform",
                           noise_rms_percent=self.rms.value() if self.competition and self.noise_mode.currentIndex()==1 else 0,
                           allow_pileup=self.competition and self.pileup.isChecked())
